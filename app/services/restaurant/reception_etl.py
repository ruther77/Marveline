"""Service reception facture ETL — chaîne ingrédients restaurant (tenant_id=3).

Équivalent minimal de `app/services/epicerie/reception_etl.py` mais adapté au
modèle restaurant :
  - Pas de catalogue centralisé ni de déduplication TF-IDF.
  - Match ingrédient par nom normalisé (lower + strip accents + collapse).
  - Si match : update `cout_unitaire_cts` (prix d'achat) + mouvement `entree`.
  - Sinon : création d'un nouvel IngredientRestaurant puis mouvement.
  - Création FinanceInvoice FOURNISSEUR (symétrie épicerie).

Workflow appelé par `admin/etl_imports.py::validate_import` quand
`EtlImport.target_tenant_id == 3` (factures TAIYAT INCONTOURNABLE).

Invariants :
  - `tenant_id` doit être 3.
  - `etl_import.lignes_data` non vide.
  - `stock_actuel` mis à jour atomiquement (SELECT FOR UPDATE via repo).

Références :
    ADR-08 : pipeline ETL fournisseurs
    ADR-09 : 2 niveaux stock restaurant
    ADR-14 : stock_actuel lecture directe DB
    ADR-25 : workflow preview/validation facture
"""
from __future__ import annotations

import dataclasses
import logging
import re
import unicodedata
from datetime import date as date_cls, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.etl_types import LigneParsee
from app.models.catalogue.etl_import import EtlImport
from app.models.finance.invoice import FinanceInvoice
from app.models.restaurant.ingredient_restaurant import IngredientRestaurant
from app.models.restaurant.mouvement_stock_restaurant import MouvementStockRestaurant
from app.repositories.finance.invoice import AsyncFinanceInvoiceRepository
from app.repositories.finance.vendor import AsyncFinanceVendorRepository

logger = logging.getLogger(__name__)

_TENANT_RESTAURANT = 3
_TYPE_ENTREE = "entree"
_TYPE_FOURNISSEUR = "FOURNISSEUR"

# Mapping unité_base parser → unite_stock ingrédient
# Le parser TAIYAT renvoie colis/piece/kg/... ; le modèle ingrédient attend kg/L/piece
_UNITE_MAP: dict[str, str] = {
    "colis": "colis",
    "piece": "piece",
    "kg": "kg",
    "l": "L",
}


class ReceptionEtlRestaurantResult:
    """Résultat de la réception ETL restaurant."""

    def __init__(self) -> None:
        self.ingredients_crees: int = 0
        self.ingredients_updated: int = 0
        self.mouvements_crees: int = 0
        self.lignes_sans_quantite: int = 0
        self.invoice: Optional[FinanceInvoice] = None
        # Les factures restaurant n'utilisent pas de dédup catalogue — pas de conflits
        self.has_conflicts: bool = False
        self.pending_conflicts: int = 0
        # Champs présents pour compat avec epicerie.ReceptionEtlResult
        self.produits_synced: int = 0


def _normalize_nom(raw: str) -> str:
    """Normalisation pour matching : lowercase + strip accents + collapse spaces."""
    if not raw:
        return ""
    nfkd = unicodedata.normalize("NFKD", raw)
    no_accents = "".join(c for c in nfkd if not unicodedata.combining(c))
    lowered = no_accents.lower()
    cleaned = re.sub(r"[^a-z0-9]+", " ", lowered)
    return " ".join(cleaned.split())


async def _find_ingredient_by_nom(
    db: AsyncSession, nom_norm: str,
) -> Optional[IngredientRestaurant]:
    """Cherche un ingrédient dont le nom normalisé match exactement."""
    if not nom_norm:
        return None
    stmt = select(IngredientRestaurant).where(
        IngredientRestaurant.tenant_id == _TENANT_RESTAURANT,
        IngredientRestaurant.is_active.is_(True),
    )
    rows = (await db.execute(stmt)).scalars().all()
    for ing in rows:
        if _normalize_nom(ing.nom) == nom_norm:
            return ing
    return None


def _map_unite(unite_base: Optional[str]) -> str:
    if not unite_base:
        return "piece"
    return _UNITE_MAP.get(unite_base.lower(), unite_base.lower()[:10])


async def _upsert_ingredient(
    db: AsyncSession, ligne: LigneParsee,
) -> tuple[IngredientRestaurant, bool]:
    """Retourne (ingrédient, est_nouveau). Match par nom normalisé, sinon crée.

    La catégorisation utilise la taxonomie unifiée (91 codes METRO) via
    `ligne.categorie_code` déjà rempli par le parser TAIYAT. Le champ
    `categorie_id` (15 cats resto) reste NULL : il est réservé au classement
    manuel côté UI restaurant.
    """
    nom_norm = _normalize_nom(ligne.designation)
    existing = await _find_ingredient_by_nom(db, nom_norm)
    if existing is not None:
        # Mise à jour cout_unitaire si on a un nouveau prix
        if ligne.prix_unitaire_cts is not None and ligne.prix_unitaire_cts > 0:
            existing.cout_unitaire_cts = ligne.prix_unitaire_cts
        # Enrichit categorie_code si absent (backfill sur ingrédients existants)
        if not existing.categorie_code and ligne.categorie_code:
            existing.categorie_code = ligne.categorie_code
        return existing, False

    new = IngredientRestaurant(
        tenant_id=_TENANT_RESTAURANT,
        nom=ligne.designation[:200],
        unite_stock=_map_unite(ligne.unite_base),
        stock_actuel=Decimal("0"),
        stock_alerte=Decimal("0"),
        cout_unitaire_cts=ligne.prix_unitaire_cts,
        categorie_id=None,
        categorie_code=ligne.categorie_code,
    )
    db.add(new)
    await db.flush()
    await db.refresh(new)
    return new, True


async def _create_entree_movement(
    db: AsyncSession,
    ingredient: IngredientRestaurant,
    ligne: LigneParsee,
    etl_import_id: int,
    user_id: int,
    numero_facture: Optional[str],
) -> bool:
    """Crée un mouvement ENTREE et met à jour stock_actuel atomiquement."""
    if ligne.quantite is None or ligne.quantite == 0:
        return False

    # Verrou SELECT FOR UPDATE sur l'ingrédient (ADR-14)
    stmt = (
        select(IngredientRestaurant)
        .where(
            IngredientRestaurant.id == ingredient.id,
            IngredientRestaurant.tenant_id == _TENANT_RESTAURANT,
        )
        .with_for_update()
    )
    locked = (await db.execute(stmt)).scalar_one()
    quantite = Decimal(str(ligne.quantite))
    locked.stock_actuel = (locked.stock_actuel or Decimal("0")) + quantite
    stock_apres = locked.stock_actuel

    mvt = MouvementStockRestaurant(
        tenant_id=_TENANT_RESTAURANT,
        ingredient_id=ingredient.id,
        type_mouvement=_TYPE_ENTREE,
        quantite=quantite,
        stock_apres=stock_apres,
        date_mouvement=datetime.utcnow(),
        notes=f"ETL {numero_facture}" if numero_facture else f"ETL #{etl_import_id}",
        created_by_id=user_id,
        etl_import_id=etl_import_id,
    )
    db.add(mvt)
    await db.flush()
    return True


async def _resolve_vendor_id(
    db: AsyncSession, vendor_code: Optional[str],
) -> Optional[int]:
    """Resout vendor_id depuis vendor_code via finance_vendors.

    Auto-crée un FinanceVendor si vendor_code est présent mais absent du
    référentiel — symétrique côté épicerie, évite les factures restaurant
    orphelines (vendor_id NULL).
    """
    if not vendor_code:
        return None
    vendor_repo = AsyncFinanceVendorRepository(db)
    vendor = await vendor_repo.get_by_code(vendor_code)
    if vendor is None:
        vendor = await vendor_repo.create(name=vendor_code, code=vendor_code)
    return vendor.id


async def recevoir_facture_etl_restaurant(
    db: AsyncSession,
    etl_import: EtlImport,
    tenant_id: int,
    user_id: int,
) -> ReceptionEtlRestaurantResult:
    """Réception complète d'une facture ETL côté restaurant.

    Args:
        db: Session async (commit à la charge de l'appelant).
        etl_import: EtlImport en statut PREVIEW/RUNNING avec lignes_data.
        tenant_id: Doit être 3 (restaurant).
        user_id: ID du compte validant (audit trail).

    Returns:
        ReceptionEtlRestaurantResult avec stats et FinanceInvoice.

    Raises:
        ValueError: Si lignes_data vide ou tenant_id ≠ 3.
    """
    if tenant_id != _TENANT_RESTAURANT:
        raise ValueError(
            f"recevoir_facture_etl_restaurant : tenant_id={tenant_id} invalide, attendu 3."
        )

    if not etl_import.lignes_data:
        raise ValueError(
            f"EtlImport {etl_import.id} : lignes_data vide, impossible de créer les mouvements."
        )

    result = ReceptionEtlRestaurantResult()

    _valid_fields = {f.name for f in dataclasses.fields(LigneParsee)}
    lignes = [
        LigneParsee(**{k: v for k, v in d.items() if k in _valid_fields})
        for d in etl_import.lignes_data
    ]

    etl_import.statut = "RUNNING"
    etl_import.validation_step = "ingredients"
    await db.flush()

    # 1. Upsert ingrédients + mouvements ENTREE
    for ligne in lignes:
        if not ligne.designation or not ligne.designation.strip():
            continue
        if ligne.quantite is None or ligne.quantite == 0:
            result.lignes_sans_quantite += 1
            continue
        # Lignes de remise (montant négatif ou quantité négative) : on skip
        if ligne.quantite < 0 or (ligne.montant_ttc_cts is not None and ligne.montant_ttc_cts < 0):
            continue

        ingredient, is_new = await _upsert_ingredient(db, ligne)
        if is_new:
            result.ingredients_crees += 1
        else:
            result.ingredients_updated += 1

        created = await _create_entree_movement(
            db=db,
            ingredient=ingredient,
            ligne=ligne,
            etl_import_id=etl_import.id,
            user_id=user_id,
            numero_facture=etl_import.numero_facture,
        )
        if created:
            result.mouvements_crees += 1

    # 2. FinanceInvoice FOURNISSEUR
    etl_import.validation_step = "invoice"
    await db.flush()

    vendor_id = await _resolve_vendor_id(db, etl_import.vendor_code)
    invoice_repo = AsyncFinanceInvoiceRepository(db)
    invoice = await invoice_repo.create(
        tenant_id=tenant_id,
        type=_TYPE_FOURNISSEUR,
        date_facture=etl_import.date_facture or date_cls.today(),
        montant_ht=etl_import.montant_ht_total or 0,
        montant_tva=etl_import.montant_tva_total or 0,
        montant_ttc=etl_import.montant_ttc_total or 0,
        vendor_id=vendor_id,
        reference=etl_import.numero_facture,
        etl_import_id=etl_import.id,
    )
    result.invoice = invoice

    etl_import.validation_step = None
    await db.flush()

    logger.info(
        "Réception ETL restaurant %d : %d ingrédients créés, %d updated, "
        "%d mouvements, invoice %s (id=%d)",
        etl_import.id,
        result.ingredients_crees,
        result.ingredients_updated,
        result.mouvements_crees,
        invoice.numero if invoice else "N/A",
        invoice.id if invoice else 0,
    )

    return result


async def revert_import_restaurant(
    db: AsyncSession,
    etl_import: EtlImport,
    tenant_id: int,
    user_id: int,
) -> dict:
    """Annule un import restaurant validé : mouvements compensatoires + facture annulée.

    Symétrique de epicerie.reception_etl.revert_import mais sans catalogue/prix
    (le restaurant n'a pas de catalogue centralisé ni de snapshot prix).

    Args:
        db: Session async (commit à la charge de l'appelant).
        etl_import: EtlImport en statut VALIDATED, target_tenant_id=3.
        tenant_id: Doit être 3 (restaurant).
        user_id: ID du compte qui déclenche le revert.

    Returns:
        dict {mouvements_annules, invoice_annulee, ingredients_touches}.

    Raises:
        ValueError: Si statut != VALIDATED ou tenant_id != 3.
    """
    from datetime import datetime, timezone

    if tenant_id != _TENANT_RESTAURANT:
        raise ValueError(
            f"revert_import_restaurant : tenant_id={tenant_id} invalide, attendu 3."
        )
    if etl_import.statut != "VALIDATED":
        raise ValueError(
            f"Impossible de reverter l'import {etl_import.id} : "
            f"statut={etl_import.statut!r}, attendu VALIDATED"
        )

    invoice_repo = AsyncFinanceInvoiceRepository(db)

    # 1. Mouvements compensatoires (type=inventaire, quantité négative)
    stmt = select(MouvementStockRestaurant).where(
        MouvementStockRestaurant.etl_import_id == etl_import.id,
        MouvementStockRestaurant.type_mouvement == _TYPE_ENTREE,
    )
    entree_movements = (await db.execute(stmt)).scalars().all()

    mouvements_annules = 0
    ingredients_touches: set[int] = set()
    for mvt in entree_movements:
        if mvt.ingredient_id is None:
            continue
        lock_stmt = (
            select(IngredientRestaurant)
            .where(
                IngredientRestaurant.id == mvt.ingredient_id,
                IngredientRestaurant.tenant_id == _TENANT_RESTAURANT,
            )
            .with_for_update()
        )
        ingredient = (await db.execute(lock_stmt)).scalar_one_or_none()
        if ingredient is None:
            continue

        delta = -mvt.quantite
        new_stock = (ingredient.stock_actuel or Decimal("0")) + delta
        # Évite de tomber en négatif (contrainte check_ingredient_stock_positif)
        if new_stock < 0:
            new_stock = Decimal("0")
        ingredient.stock_actuel = new_stock

        compensating = MouvementStockRestaurant(
            tenant_id=_TENANT_RESTAURANT,
            ingredient_id=mvt.ingredient_id,
            type_mouvement="inventaire",
            quantite=delta,
            stock_apres=new_stock,
            date_mouvement=datetime.utcnow(),
            notes=f"Revert import #{etl_import.id}",
            created_by_id=user_id,
            etl_import_id=etl_import.id,
        )
        db.add(compensating)
        mouvements_annules += 1
        ingredients_touches.add(mvt.ingredient_id)

    await db.flush()

    # 2. Facture → ANNULEE
    invoice_annulee = False
    invoice = await invoice_repo.get_by_etl_import_id(etl_import.id)
    if invoice and invoice.statut != "ANNULEE":
        invoice.statut = "ANNULEE"
        await db.flush()
        invoice_annulee = True

    # 3. Marquer import REVERTED
    etl_import.statut = "REVERTED"
    etl_import.reverted_at = datetime.now(timezone.utc)
    etl_import.reverted_by_id = user_id
    await db.flush()

    logger.info(
        "Revert ETL restaurant %d : %d mouvements compensés, invoice_annulee=%s, "
        "%d ingrédients touchés",
        etl_import.id, mouvements_annules, invoice_annulee, len(ingredients_touches),
    )

    return {
        "mouvements_annules": mouvements_annules,
        "invoice_annulee": invoice_annulee,
        "ingredients_touches": len(ingredients_touches),
        # Champs compat avec RevertImportResponse (epicerie) — non applicables resto
        "prix_restaures": 0,
    }
