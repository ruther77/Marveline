"""Service reception facture ETL — chaine catalogue -> epicerie -> stock.

Equivalent de recevoir_commande() (supply_order.py) mais pour les factures
importees via le pipeline ETL (ADR-25). Appele a la validation d'un EtlImport.

Chaine complete :
  1. Import catalogue (run_import classique)
  2. Sync catalogue -> epicerie_produits (upsert + stock creation)
  3. Mouvements ENTREE pour chaque ligne avec quantite
  4. Creation FinanceInvoice type FOURNISSEUR avec etl_import_id

References :
    ADR-08 : pipeline ETL fournisseurs
    ADR-25 : workflow preview/validation facture
    FC_EPICERIE_INVENTAIRE.md : mouvements stock
"""
import dataclasses
import logging
from datetime import date as date_cls
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.etl_types import LigneParsee
from app.models.catalogue.etl_import import EtlImport
from app.models.finance.invoice import FinanceInvoice
from app.repositories.epicerie.produit import AsyncEpicerieProduitRepository
from app.repositories.epicerie.stock import AsyncEpicerieStockRepository
from app.repositories.finance.invoice import AsyncFinanceInvoiceRepository
from app.repositories.finance.vendor import AsyncFinanceVendorRepository

logger = logging.getLogger(__name__)

_TYPE_ENTREE = "ENTREE"
_TYPE_FOURNISSEUR = "FOURNISSEUR"
_TYPE_AJUSTEMENT_PRE = "AJUSTEMENT"
_STATUT_VALIDATED = "VALIDATED"
_INVOICE_STATUT_PAYEE = "PAYEE"
_FINANCIAL_FIELDS = ("quantite", "prix_unitaire_cts", "taux_tva_centieme")
_NON_FINANCIAL_FIELDS = ("marque", "categorie_code")
_CODE_AUTRE = "AUTRE"
_DEFAULT_MARGE_CENTIEME = 3000
_DEFAULT_TVA_CENTIEME = 2000


class EtlValidationEditError(Exception):
    """Édition post-validation impossible — cause encodée dans `code`.

    Codes :
        NOT_VALIDATED   — statut de l'import ≠ VALIDATED
        NO_INVOICE      — aucune facture liée (intégrité data)
        WRONG_TENANT    — l'import appartient à un autre tenant
        INVOICE_LOCKED  — facture en statut PAYEE, blocage financier
        LIGNE_OUT_OF_RANGE — idx hors bornes ou lignes_data vide
    """

    def __init__(self, code: str, message: str, **extra):
        self.code = code
        self.message = message
        self.extra = extra
        super().__init__(message)


class EtlReopenError(Exception):
    """Reopen d'un import REJECTED/REVERTED impossible — cause dans `code`.

    Codes :
        NOT_REOPENABLE — statut n'est pas REJECTED ni REVERTED
        WRONG_TENANT   — REVERTED + facture d'un autre tenant
    """

    def __init__(self, code: str, message: str, **extra):
        self.code = code
        self.message = message
        self.extra = extra
        super().__init__(message)


class ValidatedLignesEditResult:
    """Résultat de edit_validated_lignes : import + warnings downstream.

    warnings est une list[dict] avec structure :
        {code, idx, produit_id, ean, stock_before, stock_after, delta, message}
    """

    def __init__(self, etl_import: "EtlImport") -> None:
        self.etl_import = etl_import
        self.warnings: list[dict] = []


class ReceptionEtlResult:
    """Resultat de la reception ETL."""

    def __init__(self) -> None:
        self.produits_synced: int = 0
        self.mouvements_crees: int = 0
        self.lignes_sans_produit: int = 0
        self.lignes_sans_quantite: int = 0
        self.invoice: Optional[FinanceInvoice] = None
        self.has_conflicts: bool = False
        self.pending_conflicts: int = 0


async def _resolve_vendor_id(
    db: AsyncSession,
    vendor_code: Optional[str],
) -> Optional[int]:
    """Resout vendor_id depuis vendor_code via finance_vendors.

    Auto-crée un FinanceVendor si vendor_code est présent mais absent du
    référentiel — évite les factures orphelines (vendor_id NULL) pour les
    fournisseurs connus du pipeline ETL mais pas encore seedés manuellement.
    L'opérateur peut ensuite éditer name/adresse/contact via l'UI admin.
    """
    if not vendor_code:
        return None
    vendor_repo = AsyncFinanceVendorRepository(db)
    vendor = await vendor_repo.get_by_code(vendor_code)
    if vendor is None:
        vendor = await vendor_repo.create(name=vendor_code, code=vendor_code)
    return vendor.id


async def _sync_catalogue_to_epicerie(
    db: AsyncSession,
    tenant_id: int,
    vendor_id: Optional[int],
    source: str,
) -> int:
    """Sync catalogue_produits -> epicerie_produits. Retourne nb inseres."""
    from scripts.etl.sync_catalogue_to_epicerie import sync

    stats = await sync(
        db=db,
        tenant_id=tenant_id,
        vendor_id=vendor_id,
        source=source or "",
        dry_run=False,
    )
    total = stats.inseres + stats.mis_a_jour
    logger.info(
        "Sync catalogue->epicerie : %d inseres, %d maj, %d stock crees",
        stats.inseres, stats.mis_a_jour, stats.stock_crees,
    )
    return total


def _build_designation_index(produits: list) -> dict[str, object]:
    """Index produit épicerie par désignation normalisée pour match O(1).

    Utilise normalize_designation (même fonction que le catalogue) pour neutraliser
    casse/accents/ponctuation. Les doublons de normalisation sont tolérés (last wins).
    """
    from app.services.catalogue.etl_deduplication import normalize_designation
    index: dict[str, object] = {}
    for p in produits:
        key = normalize_designation(p.designation_clean or "")
        if key:
            index[key] = p
    return index


async def _create_entree_movements(
    db: AsyncSession,
    lignes: list[LigneParsee],
    tenant_id: int,
    etl_import_id: int,
    user_id: int,
    numero_facture: Optional[str],
) -> tuple[int, int, int]:
    """Cree les mouvements ENTREE pour chaque ligne avec quantite.

    Stratégie match :
      1. EAN (multi-EAN) si présent.
      2. Désignation normalisée (match exact via index en mémoire).
      3. Fallback token-based (ilike le plus long mot distinctif).

    Retourne (nb_mouvements, nb_sans_produit, nb_sans_quantite).
    """
    from app.services.catalogue.etl_deduplication import normalize_designation

    produit_repo = AsyncEpicerieProduitRepository(db)
    stock_repo = AsyncEpicerieStockRepository(db)

    # Index normalisé en mémoire pour match rapide (tenant ~1500 produits max)
    all_produits, _ = await produit_repo.list_paginated(
        tenant_id=tenant_id, per_page=5000,
    )
    desig_index = _build_designation_index(all_produits)

    nb_mouvements = 0
    nb_sans_produit = 0
    nb_sans_quantite = 0

    for ligne in lignes:
        if not ligne.quantite or ligne.quantite <= 0:
            nb_sans_quantite += 1
            continue

        # 1. EAN
        produit = None
        if ligne.ean:
            produit = await produit_repo.get_by_ean_multi(ligne.ean, tenant_id)

        # 2. Match désignation normalisée (exact)
        if produit is None and ligne.designation:
            key = normalize_designation(ligne.designation)
            produit = desig_index.get(key)

        # 3. Fallback : longest significant token via ilike
        if produit is None and ligne.designation:
            tokens = [t for t in normalize_designation(ligne.designation).split() if len(t) >= 4]
            if tokens:
                best_token = max(tokens, key=len)
                results, _ = await produit_repo.list_paginated(
                    tenant_id=tenant_id, search=best_token, per_page=5,
                )
                if results:
                    # Choisir le meilleur match par similarité de tokens
                    ligne_tokens = set(normalize_designation(ligne.designation).split())
                    best = max(
                        results,
                        key=lambda p: len(
                            ligne_tokens & set(normalize_designation(p.designation_clean or "").split())
                        ),
                    )
                    # Au moins 2 tokens communs pour valider le match
                    best_tokens = set(normalize_designation(best.designation_clean or "").split())
                    if len(ligne_tokens & best_tokens) >= 2:
                        produit = best

        if produit is None:
            nb_sans_produit += 1
            logger.warning(
                "Ligne ETL sans produit epicerie : ean=%s designation=%r",
                ligne.ean, ligne.designation,
            )
            continue

        # Get or create stock + mouvement ENTREE
        stock = await stock_repo.get_or_create(produit.id, tenant_id)
        nouvelle_qte = float(stock.quantite) + ligne.quantite
        await stock_repo.update_quantite(stock, ligne.quantite)
        await stock_repo.create_movement(
            tenant_id=tenant_id,
            produit_id=produit.id,
            type=_TYPE_ENTREE,
            quantite=ligne.quantite,
            stock_apres=nouvelle_qte,
            etl_import_id=etl_import_id,
            notes=f"Facture {numero_facture}" if numero_facture else None,
            created_by_id=user_id,
        )
        nb_mouvements += 1

    return nb_mouvements, nb_sans_produit, nb_sans_quantite


async def recevoir_facture_etl(
    db: AsyncSession,
    etl_import: EtlImport,
    tenant_id: int,
    user_id: int,
) -> ReceptionEtlResult:
    """Reception complete d'une facture ETL : catalogue + epicerie + stock + invoice.

    Args:
        db: Session async (commit a la charge de l'appelant).
        etl_import: EtlImport en statut PREVIEW avec lignes_data non-null.
        tenant_id: Tenant epicerie (2).
        user_id: ID du compte validant (audit trail).

    Returns:
        ReceptionEtlResult avec stats et FinanceInvoice creee.

    Raises:
        ValueError: Si lignes_data est vide ou absent.
    """
    result = ReceptionEtlResult()

    # 1. Deserialiser les lignes
    if not etl_import.lignes_data:
        raise ValueError(
            f"EtlImport {etl_import.id} : lignes_data vide, "
            "impossible de creer les mouvements de stock."
        )
    _valid_fields = {f.name for f in dataclasses.fields(LigneParsee)}
    lignes = [
        LigneParsee(**{k: v for k, v in d.items() if k in _valid_fields})
        for d in etl_import.lignes_data
    ]

    # 0. Marquer comme RUNNING
    etl_import.statut = "RUNNING"
    etl_import.validation_step = "preparation"
    await db.flush()

    # 1b. Snapshot prix catalogue AVANT import (pour revert futur)
    from app.repositories.catalogue.catalogue_produit import AsyncCatalogueProduitRepository
    cat_repo = AsyncCatalogueProduitRepository(db)
    prix_snapshot: dict[str, int] = {}
    for ligne in lignes:
        if ligne.ean:
            existing = await cat_repo.get_by_ean(ligne.ean)
            if existing and existing.prix_unitaire_cts is not None:
                prix_snapshot[str(existing.id)] = existing.prix_unitaire_cts
    etl_import.prix_snapshot = prix_snapshot if prix_snapshot else None
    await db.flush()

    # 2. Import catalogue (run_import classique, non-preview)
    # NB : run_import a déjà tourné en preview_mode=True lors de l'upload,
    # ce qui a créé les conflits de déduplication. Si l'utilisateur a résolu
    # ces conflits, les rejouer ici les recréerait à l'identique et bloquerait
    # la validation en boucle. On saute donc run_import dès qu'il existe déjà
    # des conflits (pending OU résolus) pour cet import — la table catalogue
    # reflète alors les décisions de l'opérateur.
    from app.repositories.catalogue.etl_conflict import AsyncEtlConflictRepository
    from sqlalchemy import func as _sa_func, select as _sa_select
    from app.models.catalogue.etl_conflict import EtlConflict as _EtlConflict

    etl_import.validation_step = "catalogue"
    await db.flush()

    existing_conflicts_q = await db.execute(
        _sa_select(_sa_func.count())
        .select_from(_EtlConflict)
        .where(_EtlConflict.etl_import_id == etl_import.id)
    )
    already_has_conflicts = (existing_conflicts_q.scalar() or 0) > 0

    if not already_has_conflicts:
        from app.services.catalogue.etl_import_service import run_import
        await run_import(db, lignes, etl_import.id)

    # 2b. Vérifier les conflits de déduplication — bloquer si PENDING
    conflict_repo = AsyncEtlConflictRepository(db)
    pending_count = await conflict_repo.count_pending_by_import(etl_import.id)
    if pending_count > 0:
        result.has_conflicts = True
        result.pending_conflicts = pending_count

        # Notification in-app pour les conflits
        try:
            from app.models.notification import Notification
            notif = Notification(
                tenant_id=tenant_id,
                user_id=user_id,
                type="warning",
                title=f"Import #{etl_import.id} : {pending_count} conflit{'s' if pending_count > 1 else ''} à résoudre",
                message=f"L'import de la facture {etl_import.numero_facture or f'#{etl_import.id}'} a détecté des produits similaires nécessitant une résolution manuelle.",
                link=f"/etl-conflits",
            )
            db.add(notif)
            await db.flush()
        except Exception as exc:
            logger.warning("Notification conflit ETL échouée : %s", exc)

        logger.info(
            "ETL import %d : %d conflits PENDING, validation bloquée",
            etl_import.id, pending_count,
        )
        return result

    # 3. Sync catalogue -> epicerie_produits
    etl_import.validation_step = "sync"
    await db.flush()
    vendor_id = await _resolve_vendor_id(db, etl_import.vendor_code)
    result.produits_synced = await _sync_catalogue_to_epicerie(
        db, tenant_id, vendor_id, etl_import.vendor_code or "",
    )

    # 4. Mouvements ENTREE
    etl_import.validation_step = "stock"
    await db.flush()
    mvts, sans_prod, sans_qte = await _create_entree_movements(
        db=db,
        lignes=lignes,
        tenant_id=tenant_id,
        etl_import_id=etl_import.id,
        user_id=user_id,
        numero_facture=etl_import.numero_facture,
    )
    result.mouvements_crees = mvts
    result.lignes_sans_produit = sans_prod
    result.lignes_sans_quantite = sans_qte

    # 5. FinanceInvoice FOURNISSEUR
    etl_import.validation_step = "invoice"
    await db.flush()
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

    logger.info(
        "Reception ETL %d : %d mouvements ENTREE, %d produits synced, "
        "invoice %s (id=%d), %d lignes sans produit, %d sans quantite",
        etl_import.id, mvts, result.produits_synced,
        invoice.numero, invoice.id, sans_prod, sans_qte,
    )

    # 6. Recalculer les prix de vente — uniquement pour les produits touchés
    #    par cet import, et historique seulement si le prix a effectivement changé.
    etl_import.validation_step = "prix"
    await db.flush()
    try:
        async with db.begin_nested():
            from app.repositories.epicerie.marge import AsyncEpicerieMargeRepository
            from sqlalchemy import text as _text
            marge_repo = AsyncEpicerieMargeRepository(db)
            marges = await marge_repo.get_marges_dict(tenant_id)
            if marges:
                default_marge = marges.get("AUTRE", _DEFAULT_MARGE_CENTIEME)
                # Produits touchés par CET import (mouvements ENTREE rattachés).
                touched_ids_q = await db.execute(
                    _text(
                        "SELECT DISTINCT produit_id FROM epicerie_stock_movements "
                        "WHERE tenant_id = :tid AND etl_import_id = :eid"
                    ),
                    {"tid": tenant_id, "eid": etl_import.id},
                )
                touched_ids = [r[0] for r in touched_ids_q.fetchall()]
                if not touched_ids:
                    logger.info("Aucun produit touché par l'import %d, recalcul prix sauté", etl_import.id)
                else:
                    prods = await db.execute(
                        _text(
                            "SELECT id, categorie, prix_achat_cts, prix_unitaire_cts, taux_tva "
                            "FROM epicerie_produits "
                            "WHERE tenant_id = :tid AND actif = true AND prix_achat_cts > 0 "
                            "AND id = ANY(:ids)"
                        ),
                        {"tid": tenant_id, "ids": touched_ids},
                    )
                    # Journal d'événements : 1 entrée par produit × import, même si
                    # prix identique au dernier point (permet de tracer fréquence d'appro,
                    # changements de fournisseur, progression temporelle complète).
                    eff_date = etl_import.date_facture
                    ref = etl_import.numero_facture or f"ETL #{etl_import.id}"
                    vendor = etl_import.vendor_code
                    if eff_date is None:
                        logger.warning(
                            "Import %d sans date_facture → prix_historique sauté (évite pollution chrono)",
                            etl_import.id,
                        )
                    else:
                        nb_logged = 0
                        for row in prods.fetchall():
                            pid, cat, achat, ancien_vente, tva = row
                            marge_taux = marges.get(cat or _CODE_AUTRE, default_marge)
                            prix_ht = int(achat * (1 + marge_taux / 10000))
                            prix_ttc = int(prix_ht * (1 + (tva or _DEFAULT_TVA_CENTIEME) / 10000))
                            if prix_ttc != ancien_vente:
                                await db.execute(
                                    _text("UPDATE epicerie_produits SET prix_unitaire_cts = :prix WHERE id = :id"),
                                    {"prix": prix_ttc, "id": pid},
                                )
                            await db.execute(
                                _text(
                                    "INSERT INTO epicerie_prix_historique "
                                    "(tenant_id, produit_id, prix_achat_cts, prix_vente_cts, "
                                    "taux_marge_centieme, source, source_fournisseur, "
                                    "etl_import_id, reference, effective_date) "
                                    "VALUES (:tid, :pid, :achat, :vente, :marge, 'etl', "
                                    ":vendor, :eid, :ref, :eff)"
                                ),
                                {"tid": tenant_id, "pid": pid, "achat": achat, "vente": prix_ttc,
                                 "marge": marge_taux, "vendor": vendor, "eid": etl_import.id,
                                 "ref": ref, "eff": eff_date},
                            )
                            nb_logged += 1
                        await db.flush()
                        logger.info(
                            "Prix recalculés pour %d produits touchés, %d entrées d'historique (journal)",
                            len(touched_ids), nb_logged,
                        )
    except Exception as exc:
        logger.warning("Recalcul prix échoué (savepoint rollback): %s", exc)

    # 7. Fetch images produits en background (ne bloque pas la validation)
    try:
        from app.tasks.etl_tasks import fetch_product_images_task
        produit_repo = AsyncEpicerieProduitRepository(db)
        all_prods = await produit_repo.list_without_image(tenant_id)
        if all_prods:
            fetch_product_images_task.delay([
                {"id": p.id, "ean": p.ean, "designation": p.designation_clean, "marque": None}
                for p in all_prods
            ])
            logger.info("Image fetch task queued for %d products", len(all_prods))
    except Exception as exc:
        logger.warning("Image fetch task scheduling failed: %s", exc)

    etl_import.validation_step = None
    await db.flush()
    return result


_TYPE_AJUSTEMENT = "AJUSTEMENT"


async def edit_validated_invoice_meta(
    db: AsyncSession,
    etl_import: EtlImport,
    updates: dict,
    tenant_id: int,
    user_id: int,
    request_context: Optional[dict] = None,
) -> EtlImport:
    """Édite les métadonnées facture d'un import VALIDATED (non-financier).

    Champs : numero_facture, date_facture, vendor_code.
    Répercute sur FinanceInvoice.reference et FinanceInvoice.date_facture.
    Pas de gate PAYEE (modification non-financière).

    Raises:
        EtlValidationEditError: NOT_VALIDATED, NO_INVOICE, WRONG_TENANT.
    """
    if etl_import.statut != _STATUT_VALIDATED:
        raise EtlValidationEditError(
            "NOT_VALIDATED",
            f"Édition impossible : statut={etl_import.statut!r}, attendu VALIDATED.",
            statut=etl_import.statut,
        )

    invoice_repo = AsyncFinanceInvoiceRepository(db)
    invoice = await invoice_repo.get_by_etl_import_id(etl_import.id)
    if invoice is None:
        raise EtlValidationEditError("NO_INVOICE", "Aucune facture liée.")
    if invoice.tenant_id != tenant_id:
        raise EtlValidationEditError("WRONG_TENANT", "Import d'un autre tenant.")

    changed: dict[str, dict] = {}
    for field in ("numero_facture", "date_facture", "vendor_code"):
        if field not in updates or updates[field] is None:
            continue
        old_val = getattr(etl_import, field)
        new_val = updates[field]
        if old_val != new_val:
            changed[field] = {
                "before": str(old_val) if old_val is not None else None,
                "after": str(new_val),
            }
            setattr(etl_import, field, new_val)

    if not changed:
        return etl_import

    if "numero_facture" in changed:
        invoice.reference = etl_import.numero_facture
    if "date_facture" in changed and etl_import.date_facture is not None:
        invoice.date_facture = etl_import.date_facture

    from app.services.audit import AuditService
    audit_service = AuditService(db)
    ctx = request_context or {}
    await audit_service.log_action(
        action="UPDATE",
        tenant_id=tenant_id,
        user_id=user_id,
        entity_type="EtlImport",
        entity_id=etl_import.id,
        changes=changed,
        description=f"EtlImport #{etl_import.id} invoice-meta: {', '.join(changed.keys())}",
        ip_address=ctx.get("ip_address"),
        user_agent=ctx.get("user_agent"),
        request_id=ctx.get("request_id"),
    )

    await db.flush()
    logger.info(
        "ETL import %d invoice-meta edited : %s",
        etl_import.id, ", ".join(changed.keys()),
    )
    return etl_import


# ── Édition granulaire post-validation (Option B — P1) ──────────────────────
# Cascades : recalcul ligne → recalcul totaux EtlImport → delta stock (AJUSTEMENT)
# → recalcul FinanceInvoice → update prix achat produit → audit par champ modifié.


def _recompute_ligne_amounts_dict(ligne: dict) -> None:
    """Recalcule HT/TTC d'une ligne dict depuis qte/pu/tva (in-place).

    Formule identique à etl_imports.py::_recompute_ligne_amounts pour cohérence
    avec le workflow PREVIEW : ht = int(qte * pu); ttc = int(ht * (1 + tva/10000)).
    """
    qte = ligne.get("quantite") or 0
    pu = ligne.get("prix_unitaire_cts") or 0
    tva = ligne.get("taux_tva_centieme") or 0
    ht = int(qte * pu)
    ttc = int(ht * (1 + tva / 10000))
    ligne["montant_ht_cts"] = ht
    ligne["montant_ttc_cts"] = ttc


def _compute_totals_dict(lignes: list[dict]) -> tuple[int, int, int]:
    """Somme HT, TTC et TVA (TVA = TTC - HT). Retourne (ht, tva, ttc)."""
    ht = sum(int(l.get("montant_ht_cts") or 0) for l in lignes)
    ttc = sum(int(l.get("montant_ttc_cts") or 0) for l in lignes)
    return ht, ttc - ht, ttc


def _reindex_lignes_dict(lignes: list[dict]) -> list[dict]:
    """Injecte idx séquentiel (alignement sur etl_imports.py::_index_lignes)."""
    for i, l in enumerate(lignes):
        l["idx"] = i
    return lignes


def _extract_changed_fields(
    old_ligne: dict, update: dict, tracked: tuple,
) -> dict[str, dict]:
    """Retourne {field: {before, after}} pour chaque champ tracked qui change."""
    changed: dict[str, dict] = {}
    for field in tracked:
        if field not in update or update[field] is None:
            continue
        old_val = old_ligne.get(field)
        new_val = update[field]
        if old_val != new_val:
            changed[field] = {"before": old_val, "after": new_val}
    return changed


def _extract_changed_financial_fields(
    old_ligne: dict, update: dict,
) -> dict[str, dict]:
    """Retourne les champs financiers qui changent (quantite/prix/tva)."""
    return _extract_changed_fields(old_ligne, update, _FINANCIAL_FIELDS)


def _extract_changed_non_financial_fields(
    old_ligne: dict, update: dict,
) -> dict[str, dict]:
    """Retourne les champs non-financiers qui changent (marque/cat)."""
    return _extract_changed_fields(old_ligne, update, _NON_FINANCIAL_FIELDS)


def _has_financial_change(updates: list[dict]) -> bool:
    """True si au moins un update contient un champ financier non-null."""
    for u in updates:
        for field in _FINANCIAL_FIELDS:
            if field in u and u[field] is not None:
                return True
    return False


async def _resolve_produit_for_ligne(
    produit_repo: "AsyncEpicerieProduitRepository",
    ligne: dict,
    tenant_id: int,
):
    """Retrouve un produit par EAN multi puis fallback désignation (≤50 chars)."""
    ean = ligne.get("ean")
    if ean:
        produit = await produit_repo.get_by_ean_multi(ean, tenant_id)
        if produit is not None:
            return produit
    designation = ligne.get("designation") or ""
    if designation:
        results, _ = await produit_repo.list_paginated(
            tenant_id=tenant_id, search=designation[:50], per_page=1,
        )
        if results:
            return results[0]
    return None


async def _apply_stock_delta(
    stock_repo: "AsyncEpicerieStockRepository",
    produit_id: int,
    delta: float,
    tenant_id: int,
    etl_import_id: int,
    ligne_idx: int,
    numero_facture: Optional[str],
    user_id: int,
    ean: Optional[str] = None,
) -> Optional[dict]:
    """Crée un mouvement AJUSTEMENT et met à jour le stock (delta peut être ±).

    Cas downstream (BUG:ETL-STOCK-01) : si des ventes ont consommé le stock
    entre validation et correction, un delta négatif peut pousser le stock
    sous zéro. La contrainte DB `check_epicerie_stock_quantite_positive`
    empêche ça. On **clippe à 0** : on ne retire que ce qui reste réellement,
    et on retourne un warning STOCK_CLIPPED avec le diff demandé vs appliqué.

    La valeur `lignes_data.quantite` reflète la correction logique de
    l'opérateur (indépendante du stock physique). Le warning informe que
    la cascade stock n'est pas fidèle à 100%.
    """
    if delta == 0:
        return None
    stock = await stock_repo.get_or_create(produit_id, tenant_id)
    stock_before = float(stock.quantite)
    delta_requested = float(delta)
    stock_after_raw = stock_before + delta_requested

    if stock_after_raw < 0:
        delta_applied = -stock_before
        stock_after = 0.0
        clipped = True
    else:
        delta_applied = delta_requested
        stock_after = stock_after_raw
        clipped = False

    await stock_repo.update_quantite(stock, delta_applied)

    warning: Optional[dict] = None
    note_fact = f"facture {numero_facture}" if numero_facture else f"import #{etl_import_id}"
    note = f"Correction ligne #{ligne_idx} — {note_fact}"
    if clipped:
        note += f" — ⚠ delta clippé ({delta_requested:+.2f} → {delta_applied:+.2f})"
        warning = {
            "code": "STOCK_CLIPPED",
            "idx": ligne_idx,
            "produit_id": produit_id,
            "ean": ean,
            "stock_before": stock_before,
            "stock_after": stock_after,
            "delta_requested": delta_requested,
            "delta_applied": delta_applied,
            "message": (
                f"Ligne #{ligne_idx} : stock produit {ean or produit_id} "
                f"clippé à 0. Delta demandé {delta_requested:+.2f}, "
                f"appliqué {delta_applied:+.2f}. Ventes downstream ont "
                "consommé plus que la correction ne retire."
            ),
        }
        logger.warning(
            "Édition post-validation → stock clippé : produit_id=%d ean=%s "
            "before=%.2f requested=%+.2f applied=%+.2f",
            produit_id, ean, stock_before, delta_requested, delta_applied,
        )

    await stock_repo.create_movement(
        tenant_id=tenant_id,
        produit_id=produit_id,
        type=_TYPE_AJUSTEMENT,
        quantite=delta_applied,
        stock_apres=stock_after,
        etl_import_id=etl_import_id,
        notes=note,
        created_by_id=user_id,
    )
    return warning


async def _apply_price_update(
    produit_repo: "AsyncEpicerieProduitRepository",
    ligne: dict,
    tenant_id: int,
    marges: dict[str, int],
) -> None:
    """Met à jour prix_achat_cts du produit épicerie + recalcul prix vente TTC.

    Formule identique à recevoir_facture_etl phase 6 (reception_etl.py:322-325) :
    prix_ht_vente = int(achat * (1 + taux_marge / 10000))
    prix_ttc = int(prix_ht_vente * (1 + taux_tva / 10000))
    """
    new_prix = ligne.get("prix_unitaire_cts")
    if new_prix is None:
        return
    produit = await _resolve_produit_for_ligne(produit_repo, ligne, tenant_id)
    if produit is None:
        logger.warning(
            "Édition prix ligne : produit introuvable pour ean=%s",
            ligne.get("ean"),
        )
        return
    produit.prix_achat_cts = int(new_prix)
    await _recompute_prix_vente(produit, marges)


async def _recompute_prix_vente(
    produit, marges: dict[str, int],
) -> None:
    """Recalcule prix_unitaire_cts (TTC vente) depuis prix_achat + marge cat + TVA."""
    if produit.prix_achat_cts <= 0:
        return
    cat = produit.categorie or _CODE_AUTRE
    marge_taux = marges.get(cat, marges.get(_CODE_AUTRE, _DEFAULT_MARGE_CENTIEME))
    tva = produit.taux_tva or _DEFAULT_TVA_CENTIEME
    prix_ht = int(produit.prix_achat_cts * (1 + marge_taux / 10000))
    produit.prix_unitaire_cts = int(prix_ht * (1 + tva / 10000))


async def _apply_non_financial_cascade(
    cat_repo: "AsyncCatalogueProduitRepository",
    produit_repo: "AsyncEpicerieProduitRepository",
    ligne: dict,
    changed: dict[str, dict],
    tenant_id: int,
    marges: dict[str, int],
) -> None:
    """Cascade marque/catégorie sur catalogue + epicerie (+ recalcul prix vente sur cat)."""
    ean = ligne.get("ean")
    if not ean:
        return
    cat_prod = await cat_repo.get_by_ean(ean)
    ep_prod = await produit_repo.get_by_ean_multi(ean, tenant_id)

    if "marque" in changed:
        new_marque = changed["marque"]["after"]
        if cat_prod:
            cat_prod.marque = new_marque
        # EpicerieProduit n'a pas de champ `marque` — cascade catalogue seul.

    if "categorie_code" in changed:
        new_cat = changed["categorie_code"]["after"]
        if cat_prod:
            cat_prod.categorie_code = new_cat
        if ep_prod:
            ep_prod.categorie = new_cat
            await _recompute_prix_vente(ep_prod, marges)


async def _apply_single_edit(
    *,
    etl_import_id: int,
    numero_facture: Optional[str],
    lignes: list[dict],
    idx: int,
    raw_update: dict,
    tenant_id: int,
    user_id: int,
    stock_repo: "AsyncEpicerieStockRepository",
    produit_repo: "AsyncEpicerieProduitRepository",
    cat_repo: "AsyncCatalogueProduitRepository",
    marges: dict[str, int],
) -> tuple[dict[str, dict], list[dict]]:
    """Applique une seule édition (financier + non-financier).

    Retourne (diff_audit, warnings). warnings contient les alertes downstream
    (ex: STOCK_NEGATIVE) collectées lors de l'application du delta stock.
    """
    if idx < 0 or idx >= len(lignes):
        raise EtlValidationEditError(
            "LIGNE_OUT_OF_RANGE",
            f"Index ligne {idx} hors bornes (0-{len(lignes) - 1}).",
            idx=idx,
        )

    old_ligne = dict(lignes[idx])
    fin_changed = _extract_changed_financial_fields(old_ligne, raw_update)
    non_fin_changed = _extract_changed_non_financial_fields(old_ligne, raw_update)
    changed = {**fin_changed, **non_fin_changed}
    if not changed:
        return {}, []

    new_ligne = dict(old_ligne)
    for field, diff in changed.items():
        new_ligne[field] = diff["after"]
    if fin_changed:
        _recompute_ligne_amounts_dict(new_ligne)
    lignes[idx] = new_ligne

    warnings: list[dict] = []
    if "quantite" in fin_changed:
        old_qte = float(old_ligne.get("quantite") or 0)
        new_qte = float(new_ligne.get("quantite") or 0)
        delta = new_qte - old_qte
        produit = await _resolve_produit_for_ligne(produit_repo, new_ligne, tenant_id)
        if produit is not None:
            warning = await _apply_stock_delta(
                stock_repo=stock_repo, produit_id=produit.id, delta=delta,
                tenant_id=tenant_id, etl_import_id=etl_import_id, ligne_idx=idx,
                numero_facture=numero_facture, user_id=user_id,
                ean=new_ligne.get("ean"),
            )
            if warning:
                warnings.append(warning)
        else:
            logger.warning(
                "Édition qte ligne idx=%d : produit introuvable, delta stock ignoré", idx,
            )

    if "prix_unitaire_cts" in fin_changed:
        await _apply_price_update(produit_repo, new_ligne, tenant_id, marges)

    if non_fin_changed:
        await _apply_non_financial_cascade(
            cat_repo=cat_repo, produit_repo=produit_repo, ligne=new_ligne,
            changed=non_fin_changed, tenant_id=tenant_id, marges=marges,
        )

    return changed, warnings


async def _audit_edit_entries(
    audit_service,
    etl_import_id: int,
    tenant_id: int,
    user_id: int,
    request_context: Optional[dict],
    entries: list[tuple[int, dict[str, dict]]],
) -> None:
    """Log un AuditLog UPDATE par champ modifié (format {field: {before, after}})."""
    ctx = request_context or {}
    for idx, changed in entries:
        for field, diff in changed.items():
            await audit_service.log_action(
                action="UPDATE",
                tenant_id=tenant_id,
                user_id=user_id,
                entity_type="EtlImport",
                entity_id=etl_import_id,
                changes={f"ligne_{idx}.{field}": diff},
                description=(
                    f"EtlImport #{etl_import_id} ligne {idx} {field}: "
                    f"{diff['before']} → {diff['after']}"
                ),
                ip_address=ctx.get("ip_address"),
                user_agent=ctx.get("user_agent"),
                request_id=ctx.get("request_id"),
            )


async def _find_original_validator_id(
    db: AsyncSession, etl_import_id: int,
) -> Optional[int]:
    """Retrouve l'ID du compte qui a validé initialement l'import.

    Stratégie : premier mouvement ENTREE créé pour cet import → created_by_id.
    Pas besoin d'une nouvelle colonne `validated_by_id` sur EtlImport — l'info
    est déjà persistée dans `epicerie_stock_movements` par `recevoir_facture_etl`.
    """
    from sqlalchemy import select as _sa_select
    from app.models.epicerie.stock_movement import EpicerieStockMovement

    stmt = (
        _sa_select(EpicerieStockMovement.created_by_id)
        .where(
            EpicerieStockMovement.etl_import_id == etl_import_id,
            EpicerieStockMovement.type == _TYPE_ENTREE,
        )
        .order_by(EpicerieStockMovement.created_at.asc())
        .limit(1)
    )
    res = await db.execute(stmt)
    return res.scalar_one_or_none()


def _format_correction_notification_body(
    etl_import_id: int,
    numero_facture: Optional[str],
    audit_entries: list[tuple[int, dict[str, dict]]],
) -> tuple[str, str]:
    """Formate (title, message) d'une notification de correction post-validation.

    Message détaillé : liste chaque champ modifié `ligne #X field: avant → après`.
    """
    ref = numero_facture or f"#{etl_import_id}"
    total_fields = sum(len(changed) for _, changed in audit_entries)
    title = f"Import {ref} corrigé — {total_fields} champ{'s' if total_fields > 1 else ''}"
    lines: list[str] = []
    for idx, changed in audit_entries:
        for field, diff in changed.items():
            lines.append(f"ligne #{idx} {field} : {diff['before']} → {diff['after']}")
    message = "\n".join(lines[:10])  # cap à 10 lignes pour éviter notifs géantes
    if len(lines) > 10:
        message += f"\n… et {len(lines) - 10} autre{'s' if len(lines) - 10 > 1 else ''}"
    return title, message


async def _notify_original_validator(
    db: AsyncSession,
    etl_import: EtlImport,
    tenant_id: int,
    corrector_user_id: int,
    audit_entries: list[tuple[int, dict[str, dict]]],
) -> None:
    """Crée une Notification in-app au validateur original (si différent du correcteur).

    Audience P5 (décision 4C) : uniquement le validateur initial de l'import.
    Pas de notification s'il est l'auteur de la correction (pas d'auto-notif).
    """
    if not audit_entries:
        return
    validator_id = await _find_original_validator_id(db, etl_import.id)
    if validator_id is None or validator_id == corrector_user_id:
        return

    from app.models.notification import Notification

    title, message = _format_correction_notification_body(
        etl_import.id, etl_import.numero_facture, audit_entries,
    )
    try:
        notif = Notification(
            tenant_id=tenant_id,
            user_id=validator_id,
            type="info",
            title=title,
            message=message,
            link=f"/etl-imports/{etl_import.id}",
        )
        db.add(notif)
        await db.flush()
        logger.info(
            "Notification correction ETL : import=%d validator=%d corrector=%d fields=%d",
            etl_import.id, validator_id, corrector_user_id,
            sum(len(c) for _, c in audit_entries),
        )
    except Exception as exc:
        logger.warning("Notification correction ETL échouée : %s", exc)


async def edit_validated_lignes(
    db: AsyncSession,
    etl_import: EtlImport,
    updates: list[dict],
    tenant_id: int,
    user_id: int,
    request_context: Optional[dict] = None,
) -> ValidatedLignesEditResult:
    """Édite les champs financiers d'un import VALIDATED avec cascades.

    Cascades (dans l'ordre) :
      1. Gate statut VALIDATED + facture liée + tenant + statut facture
      2. Pour chaque ligne : diff champs financiers → recalcul HT/TTC
      3. Delta stock → AJUSTEMENT + update quantité
      4. Update prix_achat produit si prix change
      5. Recalcul totaux EtlImport (HT/TVA/TTC)
      6. Update FinanceInvoice (HT/TVA/TTC alignés sur l'import)
      7. Audit : 1 entrée log_action par champ modifié

    Raises:
        EtlValidationEditError: gates échouées (NOT_VALIDATED, NO_INVOICE,
            WRONG_TENANT, INVOICE_LOCKED, LIGNE_OUT_OF_RANGE).
    """
    if etl_import.statut != _STATUT_VALIDATED:
        raise EtlValidationEditError(
            "NOT_VALIDATED",
            f"Édition impossible : statut={etl_import.statut!r}, attendu VALIDATED.",
            statut=etl_import.statut,
        )

    invoice_repo = AsyncFinanceInvoiceRepository(db)
    invoice = await invoice_repo.get_by_etl_import_id(etl_import.id)
    if invoice is None:
        raise EtlValidationEditError(
            "NO_INVOICE",
            f"Aucune facture liée à l'import {etl_import.id}.",
        )
    if invoice.tenant_id != tenant_id:
        raise EtlValidationEditError(
            "WRONG_TENANT",
            "Import appartient à un autre tenant.",
        )
    # Gate différenciée P2 : PAYEE bloque seulement les modifs financières.
    # Les modifs non-financières (marque/cat) restent autorisées sur facture payée.
    has_fin = _has_financial_change(updates)
    if has_fin and invoice.statut == _INVOICE_STATUT_PAYEE:
        raise EtlValidationEditError(
            "INVOICE_LOCKED",
            f"Facture {invoice.numero} payée, édition financière interdite.",
            invoice_statut=invoice.statut,
        )

    lignes = list(etl_import.lignes_data or [])
    if not lignes:
        raise EtlValidationEditError(
            "LIGNE_OUT_OF_RANGE", "Import sans lignes, édition impossible.",
        )

    from app.repositories.catalogue.catalogue_produit import AsyncCatalogueProduitRepository
    from app.repositories.epicerie.marge import AsyncEpicerieMargeRepository

    stock_repo = AsyncEpicerieStockRepository(db)
    produit_repo = AsyncEpicerieProduitRepository(db)
    cat_repo = AsyncCatalogueProduitRepository(db)
    marge_repo = AsyncEpicerieMargeRepository(db)
    marges = await marge_repo.get_marges_dict(tenant_id)

    result = ValidatedLignesEditResult(etl_import)
    audit_entries: list[tuple[int, dict[str, dict]]] = []
    for raw_update in updates:
        idx = int(raw_update["idx"])
        changed, warnings = await _apply_single_edit(
            etl_import_id=etl_import.id,
            numero_facture=etl_import.numero_facture,
            lignes=lignes,
            idx=idx,
            raw_update=raw_update,
            tenant_id=tenant_id,
            user_id=user_id,
            stock_repo=stock_repo,
            produit_repo=produit_repo,
            cat_repo=cat_repo,
            marges=marges,
        )
        if changed:
            audit_entries.append((idx, changed))
        if warnings:
            result.warnings.extend(warnings)

    etl_import.lignes_data = _reindex_lignes_dict(lignes)
    # Recalcul totaux seulement si au moins une modif financière a eu lieu
    if has_fin:
        new_ht, new_tva, new_ttc = _compute_totals_dict(lignes)
        etl_import.montant_ht_total = new_ht
        etl_import.montant_tva_total = new_tva
        etl_import.montant_ttc_total = new_ttc
        invoice.montant_ht = new_ht
        invoice.montant_tva = new_tva
        invoice.montant_ttc = new_ttc

    if audit_entries:
        from app.services.audit import AuditService
        audit_service = AuditService(db)
        await _audit_edit_entries(
            audit_service=audit_service,
            etl_import_id=etl_import.id,
            tenant_id=tenant_id,
            user_id=user_id,
            request_context=request_context,
            entries=audit_entries,
        )
        # P5 — notifier le validateur original si différent du correcteur
        await _notify_original_validator(
            db=db,
            etl_import=etl_import,
            tenant_id=tenant_id,
            corrector_user_id=user_id,
            audit_entries=audit_entries,
        )

    await db.flush()
    logger.info(
        "ETL import %d edited : %d lignes modifiées (financier=%s, HT=%d TTC=%d, warnings=%d)",
        etl_import.id, len(audit_entries), has_fin,
        etl_import.montant_ht_total or 0, etl_import.montant_ttc_total or 0,
        len(result.warnings),
    )
    return result


_STATUTS_REOPENABLE = ("REJECTED", "REVERTED")
_STATUT_PREVIEW = "PREVIEW"


async def _notify_reopen(
    db: AsyncSession,
    etl_import: EtlImport,
    tenant_id: int,
    reopener_id: int,
    reverter_id: Optional[int],
) -> None:
    """Notifie le validateur original + le reverteur (2 notifications distinctes).

    Chaque destinataire reçoit sa propre ligne `Notification` in-app.
    Skip le réouvreur lui-même (pas d'auto-notif).
    """
    from app.models.notification import Notification

    validator_id = await _find_original_validator_id(db, etl_import.id)
    ref = etl_import.numero_facture or f"#{etl_import.id}"
    link = f"/etl-imports/{etl_import.id}"

    targets: set[int] = set()
    if validator_id and validator_id != reopener_id:
        targets.add(validator_id)
    if reverter_id and reverter_id != reopener_id:
        targets.add(reverter_id)

    for target_user_id in targets:
        try:
            notif = Notification(
                tenant_id=tenant_id,
                user_id=target_user_id,
                type="info",
                title=f"Import {ref} réouvert",
                message=(
                    f"L'import {ref} a été remis en édition (statut PREVIEW) "
                    "pour correction. Une nouvelle validation est en attente."
                ),
                link=link,
            )
            db.add(notif)
        except Exception as exc:
            logger.warning(
                "Notification reopen échouée pour user %d : %s",
                target_user_id, exc,
            )
    if targets:
        await db.flush()
        logger.info(
            "Reopen notifications envoyées : import=%d targets=%s reopener=%d",
            etl_import.id, sorted(targets), reopener_id,
        )


async def reopen_import(
    db: AsyncSession,
    etl_import: EtlImport,
    tenant_id: int,
    user_id: int,
    request_context: Optional[dict] = None,
) -> EtlImport:
    """Rouvre un import REJECTED ou REVERTED en statut PREVIEW.

    Comportement par statut source :
      - REJECTED : simple changement de statut, aucune cascade DB. Pas de
        gate tenant possible (pas de facture créée).
      - REVERTED : gate tenant via la facture (ANNULEE), reset des champs
        `reverted_at`/`reverted_by_id`. Les mouvements AJUSTEMENT
        compensatoires ne sont PAS supprimés — la re-validation future
        créera de nouveaux ENTREE qui s'ajoutent, ce qui est comptablement
        cohérent (ENTREE₁ + AJUSTEMENT + ENTREE₂ = net +N).

    Audit : 1 entrée UPDATE `{statut: {before, after}}`.
    Notifications (REVERTED uniquement) : 1 à chaque destinataire parmi
    {validateur original, reverteur} s'ils diffèrent du réouvreur.

    Raises:
        EtlReopenError: NOT_REOPENABLE (statut non éligible) ou WRONG_TENANT.
    """
    if etl_import.statut not in _STATUTS_REOPENABLE:
        raise EtlReopenError(
            "NOT_REOPENABLE",
            f"Reopen impossible : statut={etl_import.statut!r}, "
            f"attendu parmi {_STATUTS_REOPENABLE}.",
            statut=etl_import.statut,
        )

    old_statut = etl_import.statut
    reverter_id: Optional[int] = None

    if old_statut == "REVERTED":
        invoice_repo = AsyncFinanceInvoiceRepository(db)
        invoice = await invoice_repo.get_by_etl_import_id(etl_import.id)
        if invoice is None:
            # Pas de facture = pas de source de vérité tenant ; on accepte
            # sur RBAC seul (cas bord extrême, import reverté sans facture).
            logger.warning(
                "Reopen REVERTED import %d sans facture liée — skip gate tenant",
                etl_import.id,
            )
        elif invoice.tenant_id != tenant_id:
            raise EtlReopenError(
                "WRONG_TENANT",
                "Import appartient à un autre tenant.",
            )
        reverter_id = etl_import.reverted_by_id
        etl_import.reverted_at = None
        etl_import.reverted_by_id = None

    etl_import.statut = _STATUT_PREVIEW
    etl_import.erreur_detail = None

    from app.services.audit import AuditService
    audit_service = AuditService(db)
    ctx = request_context or {}
    await audit_service.log_action(
        action="UPDATE",
        tenant_id=tenant_id,
        user_id=user_id,
        entity_type="EtlImport",
        entity_id=etl_import.id,
        changes={"statut": {"before": old_statut, "after": _STATUT_PREVIEW}},
        description=(
            f"EtlImport #{etl_import.id} réouvert ({old_statut} → PREVIEW)"
        ),
        ip_address=ctx.get("ip_address"),
        user_agent=ctx.get("user_agent"),
        request_id=ctx.get("request_id"),
    )

    if old_statut == "REVERTED":
        await _notify_reopen(
            db=db,
            etl_import=etl_import,
            tenant_id=tenant_id,
            reopener_id=user_id,
            reverter_id=reverter_id,
        )

    await db.flush()
    logger.info(
        "EtlImport %d reopened by user %d (%s → PREVIEW)",
        etl_import.id, user_id, old_statut,
    )
    return etl_import


async def revert_import(
    db: AsyncSession,
    etl_import: EtlImport,
    tenant_id: int,
    user_id: int,
) -> dict:
    """Annule un import validé : mouvements stock compensatoires, facture annulée, prix restaurés.

    Args:
        db: Session async (commit à la charge de l'appelant).
        etl_import: EtlImport en statut VALIDATED.
        tenant_id: Tenant épicerie.
        user_id: ID du compte qui déclenche le revert.

    Returns:
        dict avec stats du revert.

    Raises:
        ValueError: Si statut != VALIDATED.
    """
    from datetime import datetime, timezone
    from sqlalchemy import select
    from app.models.epicerie.stock_movement import EpicerieStockMovement
    from app.repositories.catalogue.catalogue_produit import AsyncCatalogueProduitRepository

    if etl_import.statut != "VALIDATED":
        raise ValueError(
            f"Impossible de reverter l'import {etl_import.id} : "
            f"statut={etl_import.statut!r}, attendu VALIDATED"
        )

    stock_repo = AsyncEpicerieStockRepository(db)
    invoice_repo = AsyncFinanceInvoiceRepository(db)
    cat_repo = AsyncCatalogueProduitRepository(db)

    # 1. Mouvements compensatoires : pour chaque ENTREE, créer AJUSTEMENT négatif
    stmt = select(EpicerieStockMovement).where(
        EpicerieStockMovement.etl_import_id == etl_import.id,
        EpicerieStockMovement.type == _TYPE_ENTREE,
    )
    result_mvts = await db.execute(stmt)
    entree_movements = result_mvts.scalars().all()

    mouvements_annules = 0
    for mvt in entree_movements:
        stock = await stock_repo.get_by_produit(mvt.produit_id, tenant_id)
        if stock is None:
            continue
        delta = -mvt.quantite
        nouvelle_qte = float(stock.quantite) + float(delta)
        await stock_repo.update_quantite(stock, delta)
        await stock_repo.create_movement(
            tenant_id=tenant_id,
            produit_id=mvt.produit_id,
            type=_TYPE_AJUSTEMENT,
            quantite=delta,
            stock_apres=nouvelle_qte,
            etl_import_id=etl_import.id,
            notes=f"Revert import #{etl_import.id}",
            created_by_id=user_id,
        )
        mouvements_annules += 1

    # 2. Facture finance → ANNULEE
    invoice_annulee = False
    invoice = await invoice_repo.get_by_etl_import_id(etl_import.id)
    if invoice and invoice.statut != "ANNULEE":
        invoice.statut = "ANNULEE"
        await db.flush()
        invoice_annulee = True

    # 3. Restaurer les prix catalogue depuis le snapshot
    prix_restaures = 0
    if etl_import.prix_snapshot:
        for produit_id_str, old_price in etl_import.prix_snapshot.items():
            produit = await cat_repo.get_by_id(int(produit_id_str))
            if produit:
                produit.prix_unitaire_cts = old_price
                prix_restaures += 1
        await db.flush()

    # 4. Marquer l'import comme REVERTED
    etl_import.statut = "REVERTED"
    etl_import.reverted_at = datetime.now(timezone.utc)
    etl_import.reverted_by_id = user_id
    await db.flush()

    logger.info(
        "Revert ETL %d : %d mouvements annulés, invoice=%s, %d prix restaurés",
        etl_import.id, mouvements_annules,
        "ANNULEE" if invoice_annulee else "N/A",
        prix_restaures,
    )

    return {
        "mouvements_annules": mouvements_annules,
        "invoice_annulee": invoice_annulee,
        "prix_restaures": prix_restaures,
    }
