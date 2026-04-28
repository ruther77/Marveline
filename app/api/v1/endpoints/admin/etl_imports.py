"""Endpoints admin — Queue factures fournisseur (upload, preview, validation).

Workflow ADR-25 :
    1. POST /admin/etl/upload   → parse PDF → EtlImport PREVIEW
    2. GET  /admin/etl/imports  → liste queue (filtrable par statut)
    3. GET  /admin/etl/imports/{id} → détail preview avec lignes
    4. PATCH /admin/etl/imports/{id} → modifier metadata avant validation
    5. POST /admin/etl/imports/{id}/validate → créer FinanceInvoice
    6. POST /admin/etl/imports/{id}/reject   → marquer REJECTED
    7. GET  /admin/etl/imports/{id}/pdf → servir le PDF source
    8. PATCH /admin/etl/imports/{id}/lignes → modifier lignes en preview
    9. POST /admin/etl/imports/{id}/lignes → ajouter une ligne
   10. DELETE /admin/etl/imports/{id}/lignes/{idx} → supprimer une ligne
   11. GET  /admin/etl/categories → catégories groupées

Auth : SETTINGS_READ (lecture) / SETTINGS_WRITE (mutation) — scope admin.
"""
import dataclasses
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_async_db
from app.core.deps import require_scope
from app.core.permissions import Scope
from app.repositories.catalogue.etl_import import AsyncEtlImportRepository
from app.schemas.catalogue.etl_import import (
    CategoriesResponse,
    CategoryGroup,
    CategoryItem,
    EtlImportDetail,
    EtlImportListResponse,
    EtlImportRead,
    EtlImportUpdateRequest,
    FactureUploadResponse,
    LigneAddRequest,
    LigneFactureRead,
    LignesBatchUpdateRequest,
    RevertImportResponse,
    DashboardResponse,
    DashboardQualityTrend,
    DashboardVendorStats,
    ValidatedLignesBatchEditRequest,
    ValidatedInvoiceMetaEditRequest,
    ValidatedLignesEditResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/etl", tags=["Admin — ETL Imports"])

_VALID_FOURNISSEURS = {"metro", "taiyat", "ethan", "eurociel", "gnanam"}
_PREVIEW_STATUT = "PREVIEW"
_VALIDATED_STATUT = "VALIDATED"
_REJECTED_STATUT = "REJECTED"
_VALID_STATUT_FILTERS = {"all", "preview", "validated", "rejected", "running", "pending", "reverted"}


# ── Catégories alimentaires (91 codes groupés) ────────────────────────────────

_CATEGORY_GROUPS: list[tuple[str, str, list[tuple[str, str]]]] = [
    ("ALC", "Alcools", [
        ("ALC_BIERE", "Bières"), ("ALC_VIN_RGE", "Vins rouges"),
        ("ALC_VIN_BLC", "Vins blancs"), ("ALC_VIN_ROSE", "Vins rosés"),
        ("ALC_SPIRITUEUX", "Spiritueux"), ("ALC_LIQUEUR", "Liqueurs"),
        ("ALC_APERO", "Apéritifs"),
    ]),
    ("BOIS", "Boissons", [
        ("BOIS_EAU", "Eaux"), ("BOIS_SODA", "Sodas"), ("BOIS_JUS", "Jus"),
        ("BOIS_SIROP", "Sirops"), ("BOIS_ENERG", "Énergisantes"),
        ("BOIS_CAFE", "Cafés"), ("BOIS_THE", "Thés"), ("BOIS_CHOCO", "Chocolats"),
    ]),
    ("BOUL", "Boulangerie", [
        ("BOUL_BRIOCHE", "Brioches"), ("BOUL_PAIN", "Pains"),
        ("BOUL_VIEN", "Viennoiseries"),
    ]),
    ("COND", "Condiments", [
        ("COND_BOUILLON", "Bouillons"), ("COND_SEL", "Sels"),
        ("COND_HUILE", "Huiles"), ("COND_VINAIGRE", "Vinaigres"),
        ("COND_SAUCE", "Sauces"), ("COND_EPICE", "Épices"),
    ]),
    ("CONS", "Conserves", [
        ("CONS_LEGUME", "Légumes"), ("CONS_PLAT", "Plats"),
        ("CONS_POISSON", "Poissons"), ("CONS_SAUCE", "Sauces"),
    ]),
    ("ENTR", "Entretien", [
        ("ENTR_LESSIVE", "Lessives"), ("ENTR_NETTOY", "Nettoyants"),
        ("ENTR_VAISS", "Vaisselle"),
    ]),
    ("EPIC", "Épicerie sèche", [
        ("EPIC_SEMOULE", "Semoules"), ("EPIC_LEGUM_SEC", "Légumes secs"),
        ("EPIC_PATE", "Pâtes"), ("EPIC_RIZ", "Riz"),
    ]),
    ("FL", "Fruits & Légumes", [
        ("FL_AROMATE", "Aromates"), ("FL_SALADE", "Salades"),
        ("FL_LEGUME", "Légumes"), ("FL_FRUIT", "Fruits"),
    ]),
    ("FRAIS", "Frais", [
        ("FRAIS_BOEUF", "Boeuf"), ("FRAIS_PORC", "Porc"),
        ("FRAIS_AGNEAU", "Agneau"), ("FRAIS_VOLAILLE", "Volaille"),
        ("FRAIS_CHARC", "Charcuterie"), ("FRAIS_SAUCISSE", "Saucisses"),
        ("FRAIS_JAMBON", "Jambons"), ("FRAIS_LARDON", "Lardons"),
        ("FRAIS_POISSON", "Poissons"), ("FRAIS_CRUST", "Crustacés"),
        ("FRAIS_COQUIL", "Coquillages"), ("FRAIS_OEUF", "Oeufs"),
        ("FRAIS_TRAIT", "Traiteur"),
    ]),
    ("HYG", "Hygiène", [
        ("HYG_CORPS", "Hygiène corporelle"), ("HYG_PAPIER", "Papier"),
    ]),
    ("LAIT", "Produits laitiers", [
        ("LAIT_CREME", "Crèmes"), ("LAIT_BEURRE", "Beurres"),
        ("LAIT_FROMAGE", "Fromages"), ("LAIT_YAOURT", "Yaourts"),
        ("LAIT_DESSERT", "Desserts"), ("LAIT_UHT", "Lait UHT"),
    ]),
    ("MONDE", "Monde", [
        ("MONDE_HALAL", "Halal"), ("MONDE_ASIE", "Asie"),
        ("MONDE_ORIENT", "Oriental"), ("MONDE_AMERIQUE", "Amérique"),
        ("MONDE_AFRIQUE", "Afrique"),
    ]),
    ("PRO", "Professionnel", [
        ("PRO_FILM", "Films"), ("PRO_PROTECT", "Protection"),
        ("PRO_ETIQ", "Étiquettes"), ("PRO_EMBALL", "Emballages"),
        ("PRO_JETABLE", "Jetables"),
    ]),
    ("SNACK", "Snacking", [
        ("SNACK_CHIPS", "Chips"), ("SNACK_FRUIT_SEC", "Fruits secs"),
        ("SNACK_BISCUIT", "Biscuits apéro"),
    ]),
    ("SUCR", "Sucré", [
        ("SUCR_LEVURE", "Levures"), ("SUCR_AROME", "Arômes"),
        ("SUCR_NAPPAGE", "Nappages"), ("SUCR_FARINE", "Farines"),
        ("SUCR_CEREAL", "Céréales"), ("SUCR_CONF", "Confitures"),
        ("SUCR_SUCRE", "Sucres"), ("SUCR_CHOCO", "Chocolats"),
        ("SUCR_BONBON", "Bonbons"), ("SUCR_BISC", "Biscuits"),
        ("SUCR_GATEAU", "Gâteaux"), ("SUCR_VIEN", "Viennoiseries"),
    ]),
    ("SURG", "Surgelés", [
        ("SURG_VIANDE", "Viandes"), ("SURG_POISSON", "Poissons"),
        ("SURG_GLACE", "Glaces"), ("SURG_PATISS", "Pâtisseries"),
        ("SURG_LEGUME", "Légumes"),
    ]),
    ("AUTRE", "Autre", [
        ("AUTRE", "Non classé"),
    ]),
]


from app.services.catalogue.etl_pdf_storage import (
    get_etl_upload_dir as _get_etl_upload_dir,  # noqa: F401 (re-export pour compat)
    persist_etl_source as _persist_etl_source,
    resolve_uploads_base as _resolve_uploads_base,
)


def _compute_lignes_totals(lignes: list[dict]) -> tuple[int, int]:
    """Calcule le total HT et TTC à partir des lignes."""
    total_ht = 0
    total_ttc = 0
    for l in lignes:
        ht = l.get("montant_ht_cts") or 0
        ttc = l.get("montant_ttc_cts") or 0
        total_ht += ht
        total_ttc += ttc
    return total_ht, total_ttc


def _recompute_ligne_amounts(ligne: dict, changed_fields: set[str] | None = None) -> dict:
    """Recalcule montant_ht et montant_ttc d'une ligne.

    Si changed_fields est fourni, ne recalcule HT que si quantite ou
    prix_unitaire_cts a changé — préserve la précision du parser pour
    les lignes avec remise N POUR M appliquée.
    """
    financial_changed = changed_fields is None or bool(
        changed_fields & {"quantite", "prix_unitaire_cts"}
    )
    tva = ligne.get("taux_tva_centieme") or 0

    if financial_changed:
        qte = ligne.get("quantite") or 0
        pu = ligne.get("prix_unitaire_cts") or 0
        ht = int(qte * pu)
        ligne["montant_ht_cts"] = ht
    else:
        ht = ligne.get("montant_ht_cts") or 0

    ligne["montant_ttc_cts"] = int(ht * (1 + tva / 10000))
    return ligne


def _index_lignes(lignes: list[dict]) -> list[dict]:
    """Ajoute un idx séquentiel à chaque ligne."""
    for i, l in enumerate(lignes):
        l["idx"] = i
    return lignes


async def _get_visible_import_or_404(
    db: AsyncSession,
    import_id: int,
    tenant_id: int,
):
    """Charge un import ETL visible pour le tenant appelant, sinon 404."""
    repo = AsyncEtlImportRepository(db)
    obj = await repo.get_by_id_for_tenant(import_id, tenant_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Import ETL introuvable.")
    return obj


# ── Upload ────────────────────────────────────────────────────────────────────


@router.post("/upload", response_model=FactureUploadResponse, status_code=201)
async def upload_facture(
    file: UploadFile = File(..., description="PDF facture fournisseur"),
    fournisseur: str = Form(default="metro", description="metro | taiyat"),
    fournisseur_id: Optional[int] = Form(default=None, description="FK fournisseurs_alim.id"),
    target_tenant_id: Optional[int] = Form(
        default=None,
        description="Override tenant cible (2=épicerie, 3=restaurant). NULL = auto-détecté par le parser.",
    ),
    db: AsyncSession = Depends(get_async_db),
    _=Depends(require_scope(Scope.SETTINGS_WRITE)),
):
    """Upload un PDF fournisseur, parse et crée un EtlImport en PREVIEW.

    Le PDF est persisté dans uploads/etl/{import_id}.pdf pour la vue split.
    Si target_tenant_id est fourni, il prime sur l'auto-détection parser
    (utile si le nom de fichier a été renommé et que l'heuristique se trompe).
    """
    if fournisseur not in _VALID_FOURNISSEURS:
        raise HTTPException(
            status_code=422,
            detail=f"fournisseur doit être dans {_VALID_FOURNISSEURS}",
        )
    _ALLOWED_TENANTS = {2, 3}
    if target_tenant_id is not None and target_tenant_id not in _ALLOWED_TENANTS:
        raise HTTPException(
            status_code=422,
            detail=f"target_tenant_id doit être dans {_ALLOWED_TENANTS} (2=épicerie, 3=restaurant).",
        )

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=422, detail="Seuls les fichiers PDF sont acceptés.")

    content = await file.read()

    # Parser dans un fichier temporaire
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        import importlib
        from scripts.etl.import_pipeline import _PARSERS

        module = importlib.import_module(_PARSERS[fournisseur])
        lignes, metadata = module.parse_facture(tmp_path)
        # Override explicite opérateur : prime sur l'auto-détection parser
        if target_tenant_id is not None:
            metadata.target_tenant_id = target_tenant_id
    except Exception as exc:
        logger.exception("Erreur parsing %s : %s", fournisseur, exc)
        raise HTTPException(status_code=422, detail=f"Erreur parsing : {exc}") from exc
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    # Créer l'EtlImport et passer en mode preview
    from app.services.catalogue.etl_import_service import run_import

    repo = AsyncEtlImportRepository(db)
    from app.models.catalogue.etl_import import EtlImport

    import_obj = EtlImport(
        fournisseur_id=fournisseur_id,
        fichier_source=file.filename,
        statut="PENDING",
    )
    created = await repo.create(import_obj)
    await db.flush()

    # Persister le PDF dans uploads/etl/{id}.pdf
    fichier_path = _persist_etl_source(
        created.id, source=content, source_filename=file.filename,
    )
    if fichier_path:
        created.fichier_path = fichier_path

    await run_import(
        db, lignes, created.id,
        metadata=metadata,
        preview_mode=True,
    )
    await db.commit()
    await db.refresh(created)

    return FactureUploadResponse(
        etl_import_id=created.id,
        statut=created.statut,
        nb_lignes=created.nb_lignes_total or 0,
        numero_facture=created.numero_facture,
        vendor_code=created.vendor_code,
        quality_score=created.quality_score,
    )


# ── List / Detail ─────────────────────────────────────────────────────────────


@router.get("/imports", response_model=EtlImportListResponse)
async def list_imports(
    statut: str = Query(default="all", description="all | preview | validated | rejected | running | pending"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(require_scope(Scope.SETTINGS_READ)),
):
    """Liste les imports ETL avec filtre par statut."""
    if statut not in _VALID_STATUT_FILTERS:
        raise HTTPException(status_code=422, detail=f"statut doit être dans {_VALID_STATUT_FILTERS}")

    repo = AsyncEtlImportRepository(db)
    statut_filter = statut.upper() if statut != "all" else None
    items, total = await repo.list_paginated_for_tenant(
        tenant_id=current_user.tenant_id,
        statut_filter=statut_filter,
        limit=limit,
        offset=offset,
    )

    # Source de vérité live : recompte les conflits PENDING par import pour ignorer
    # un éventuel champ nb_lignes_conflit stale.
    from app.models.catalogue.etl_conflict import EtlConflict as _EtlConflict
    item_ids = [i.id for i in items]
    pending_by_import: dict[int, int] = {}
    if item_ids:
        rows = await db.execute(
            select(_EtlConflict.etl_import_id, func.count())
            .where(
                _EtlConflict.etl_import_id.in_(item_ids),
                _EtlConflict.resolution == "PENDING",
            )
            .group_by(_EtlConflict.etl_import_id)
        )
        pending_by_import = {row[0]: row[1] for row in rows.all()}

    out_items = []
    for i in items:
        read = EtlImportRead.model_validate(i)
        read.nb_lignes_conflit = pending_by_import.get(i.id, 0)
        out_items.append(read)

    return EtlImportListResponse(items=out_items, total=total)


@router.get("/imports/{import_id}", response_model=EtlImportDetail)
async def get_import_detail(
    import_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(require_scope(Scope.SETTINGS_READ)),
):
    """Récupère le détail d'un import ETL avec les lignes parsées et totaux calculés."""
    obj = await _get_visible_import_or_404(db, import_id, current_user.tenant_id)

    # Source de vérité live : recompter les conflits PENDING pour éviter un champ stale
    # si la synchronisation du parent a été ratée lors d'une résolution antérieure.
    from app.models.catalogue.etl_conflict import EtlConflict as _EtlConflict
    pending_conflits_q = await db.execute(
        select(func.count())
        .select_from(_EtlConflict)
        .where(
            _EtlConflict.etl_import_id == import_id,
            _EtlConflict.resolution == "PENDING",
        )
    )
    pending_conflits = pending_conflits_q.scalar() or 0

    data = EtlImportDetail.model_validate(obj)
    data.nb_lignes_conflit = pending_conflits
    if obj.lignes_data:
        indexed = _index_lignes(list(obj.lignes_data))
        lignes = [LigneFactureRead(**l) for l in indexed]

        # Enrichir avec prix catalogue actuel (batch lookup)
        from app.models.catalogue.catalogue_produit import CatalogueProduit
        eans = [l.ean for l in lignes if l.ean]
        if eans:
            prix_q = await db.execute(
                select(CatalogueProduit.ean, CatalogueProduit.prix_unitaire_cts)
                .where(CatalogueProduit.ean.in_(eans))
            )
            prix_map = {row[0]: row[1] for row in prix_q.all()}
            for l in lignes:
                if l.ean and l.ean in prix_map:
                    l.prix_catalogue_actuel_cts = prix_map[l.ean]

        data.lignes = lignes
        ht, ttc = _compute_lignes_totals(indexed)
        data.montant_ht_calcule = ht
        data.montant_ttc_calcule = ttc
    return data


# ── PDF Serve ─────────────────────────────────────────────────────────────────


@router.get("/imports/{import_id}/pdf")
async def serve_import_pdf(
    import_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(require_scope(Scope.SETTINGS_READ)),
):
    """Sert le PDF source d'un import ETL."""
    obj = await _get_visible_import_or_404(db, import_id, current_user.tenant_id)

    if not obj.fichier_path:
        raise HTTPException(status_code=404, detail="PDF non disponible pour cet import.")

    pdf_path = os.path.join(_resolve_uploads_base(), obj.fichier_path)

    if not os.path.isfile(pdf_path):
        raise HTTPException(status_code=404, detail="Fichier PDF introuvable sur le serveur.")

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=obj.fichier_source or f"import_{import_id}.pdf",
    )


# ── Update metadata ──────────────────────────────────────────────────────────


@router.patch("/imports/{import_id}", response_model=EtlImportRead)
async def update_import_preview(
    import_id: int,
    payload: EtlImportUpdateRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(require_scope(Scope.SETTINGS_WRITE)),
):
    """Modifie les métadonnées facture d'un import en PREVIEW."""
    obj = await _get_visible_import_or_404(db, import_id, current_user.tenant_id)
    if obj.statut != _PREVIEW_STATUT:
        raise HTTPException(
            status_code=409,
            detail=f"Modification impossible : statut={obj.statut!r} (attendu PREVIEW).",
        )

    update_data = payload.model_dump(exclude_unset=True)
    for field_name, value in update_data.items():
        setattr(obj, field_name, value)

    await db.flush()
    await db.commit()
    await db.refresh(obj)
    return EtlImportRead.model_validate(obj)


# ── Lignes CRUD ───────────────────────────────────────────────────────────────


@router.patch("/imports/{import_id}/lignes", response_model=EtlImportDetail)
async def update_lignes(
    import_id: int,
    payload: LignesBatchUpdateRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(require_scope(Scope.SETTINGS_WRITE)),
):
    """Modifie une ou plusieurs lignes parsées (preview). Recalcule les montants."""
    obj = await _get_visible_import_or_404(db, import_id, current_user.tenant_id)
    if obj.statut not in {_PREVIEW_STATUT, "RUNNING"}:
        raise HTTPException(status_code=409, detail="Modification lignes impossible hors PREVIEW.")

    lignes = list(obj.lignes_data or [])
    _TRACKED_FIELDS = {"categorie_code", "marque", "ean"}

    for update in payload.updates:
        if update.idx < 0 or update.idx >= len(lignes):
            raise HTTPException(
                status_code=422,
                detail=f"Index ligne {update.idx} hors bornes (0-{len(lignes) - 1}).",
            )
        old_ligne = dict(lignes[update.idx])
        update_dict = update.model_dump(exclude_unset=True, exclude={"idx"})
        lignes[update.idx].update(update_dict)
        lignes[update.idx] = _recompute_ligne_amounts(lignes[update.idx], set(update_dict.keys()))

        # S5 : si l'opérateur modifie manuellement un champ, l'auto-fill
        # associé (badge "auto X%") doit disparaître — la valeur n'est plus
        # issue du pipeline. Le frontend peut aussi forcer le dict via
        # `auto_applied_fields` (cas révocation : valeur = null).
        if "auto_applied_fields" not in update_dict:
            meta = lignes[update.idx].get("auto_applied_fields") or {}
            if isinstance(meta, dict):
                for field_touched in update_dict.keys():
                    meta.pop(field_touched, None)
                lignes[update.idx]["auto_applied_fields"] = meta or None

        # Auto-apprentissage : enregistrer les corrections manuelles
        # Stocker la designation_norm NORMALISÉE (lowercase ascii) pour que
        # auto_fill_layer_correction_history puisse matcher sans re-normaliser
        # (bug 2026-04-24 résolu).
        designation_raw = old_ligne.get("designation_norm") or old_ligne.get("designation", "")
        designation_norm = normalize_designation(designation_raw)
        for field in _TRACKED_FIELDS:
            if field in update_dict:
                old_val = old_ligne.get(field)
                new_val = update_dict[field]
                if old_val != new_val and new_val:
                    try:
                        from app.models.catalogue.etl_correction_history import EtlCorrectionHistory
                        correction = EtlCorrectionHistory(
                            designation_norm=designation_norm[:500],
                            field_corrected=field,
                            old_value=str(old_val) if old_val else None,
                            new_value=str(new_val),
                            etl_import_id=import_id,
                        )
                        db.add(correction)
                    except Exception:
                        pass  # non-bloquant

        # Brand-dictionary feedback : quand l'opérateur corrige la marque
        # et que la catégorie est présente et non-AUTRE, on enrichit le dict
        # en temps réel (la correction a plus de poids qu'une validation
        # passive). Non-bloquant.
        marque_now = (lignes[update.idx].get("marque") or "").strip().upper()
        cat_now = lignes[update.idx].get("categorie_code")
        if (
            "marque" in update_dict
            and marque_now and len(marque_now) >= 2
            and cat_now and cat_now != "AUTRE"
        ):
            try:
                from scripts.etl.parsers.brand_dictionary import get_brand_dictionary
                bd = get_brand_dictionary()
                if bd.add(marque_now, [cat_now], source="user_correction"):
                    bd.save()
            except Exception as e:  # noqa: BLE001
                logger.debug("Brand dict user-correction learning failed: %s", e)

    # Recalcul du score de confiance post-édition : une correction (EAN,
    # marque, catégorie…) doit se refléter immédiatement dans le badge ligne.
    from app.services.catalogue.etl_import_service import compute_line_confidence
    from app.etl_types import LigneParsee
    for ligne in lignes:
        try:
            stub = LigneParsee(
                designation=ligne.get("designation", "") or "",
                unite_base=ligne.get("unite_base", "U") or "U",
                source_fournisseur=ligne.get("source_fournisseur", "") or "",
                ean=ligne.get("ean"),
                marque=ligne.get("marque"),
                categorie_code=ligne.get("categorie_code"),
                quantite=ligne.get("quantite"),
                prix_unitaire_cts=ligne.get("prix_unitaire_cts"),
                montant_ht_cts=ligne.get("montant_ht_cts"),
            )
            ligne["confidence_score"] = compute_line_confidence(stub)
        except Exception:
            pass  # Non-bloquant : le score restera stale, mais l'edit est sauvé

    obj.lignes_data = _index_lignes(lignes)
    ht, ttc = _compute_lignes_totals(lignes)

    # Recalculer l'écart de réconciliation
    declared_ht = obj.montant_ht_total or 0
    if declared_ht > 0:
        obj.ecart_reconciliation = round((declared_ht - ht) / 100, 2)

    await db.flush()
    await db.commit()
    await db.refresh(obj)

    data = EtlImportDetail.model_validate(obj)
    data.lignes = [LigneFactureRead(**l) for l in obj.lignes_data]
    data.montant_ht_calcule = ht
    data.montant_ttc_calcule = ttc
    return data


@router.post("/imports/{import_id}/lignes", response_model=EtlImportDetail, status_code=201)
async def add_ligne(
    import_id: int,
    payload: LigneAddRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(require_scope(Scope.SETTINGS_WRITE)),
):
    """Ajoute une ligne manuellement à un import en PREVIEW."""
    obj = await _get_visible_import_or_404(db, import_id, current_user.tenant_id)
    if obj.statut != _PREVIEW_STATUT:
        raise HTTPException(status_code=409, detail="Ajout ligne impossible hors PREVIEW.")

    lignes = list(obj.lignes_data or [])
    new_ligne = payload.model_dump()
    new_ligne["montant_ht_cts"] = 0
    new_ligne["montant_ttc_cts"] = 0
    new_ligne = _recompute_ligne_amounts(new_ligne)
    lignes.append(new_ligne)

    obj.lignes_data = _index_lignes(lignes)
    obj.nb_lignes_total = len(lignes)
    ht, ttc = _compute_lignes_totals(lignes)

    await db.flush()
    await db.commit()
    await db.refresh(obj)

    data = EtlImportDetail.model_validate(obj)
    data.lignes = [LigneFactureRead(**l) for l in obj.lignes_data]
    data.montant_ht_calcule = ht
    data.montant_ttc_calcule = ttc
    return data


@router.delete("/imports/{import_id}/lignes/{idx}", response_model=EtlImportDetail)
async def delete_ligne(
    import_id: int,
    idx: int,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(require_scope(Scope.SETTINGS_WRITE)),
):
    """Supprime une ligne par index d'un import en PREVIEW."""
    obj = await _get_visible_import_or_404(db, import_id, current_user.tenant_id)
    if obj.statut != _PREVIEW_STATUT:
        raise HTTPException(status_code=409, detail="Suppression ligne impossible hors PREVIEW.")

    lignes = list(obj.lignes_data or [])
    if idx < 0 or idx >= len(lignes):
        raise HTTPException(
            status_code=422,
            detail=f"Index ligne {idx} hors bornes (0-{len(lignes) - 1}).",
        )

    lignes.pop(idx)
    obj.lignes_data = _index_lignes(lignes)
    obj.nb_lignes_total = len(lignes)
    ht, ttc = _compute_lignes_totals(lignes)

    # Recompter OK/conflit/erreur basé sur les lignes restantes
    nb_ok = sum(1 for l in lignes if l.get("categorie_code") and l["categorie_code"] != "AUTRE")
    obj.nb_lignes_ok = nb_ok
    obj.nb_lignes_erreur = max(0, len(lignes) - nb_ok - (obj.nb_lignes_conflit or 0))

    await db.flush()
    await db.commit()
    await db.refresh(obj)

    data = EtlImportDetail.model_validate(obj)
    data.lignes = [LigneFactureRead(**l) for l in obj.lignes_data]
    data.montant_ht_calcule = ht
    data.montant_ttc_calcule = ttc
    return data


# ── Validate / Reject ─────────────────────────────────────────────────────────


@router.post("/imports/{import_id}/validate", response_model=EtlImportRead)
async def validate_import(
    import_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(require_scope(Scope.SETTINGS_WRITE)),
):
    """Valide un import PREVIEW : catalogue + epicerie + stock + FinanceInvoice."""
    obj = await _get_visible_import_or_404(db, import_id, current_user.tenant_id)
    # Row lock : serialise les validations concurrentes sur cet import
    # (défense contre les double-clics / retry navigateur qui créaient des
    # mouvements dupliqués — incident 2026-04-21).
    await db.execute(
        select(EtlImport).where(EtlImport.id == obj.id).with_for_update()
    )
    await db.refresh(obj)
    _VALIDATABLE = {_PREVIEW_STATUT, "RUNNING"}
    if obj.statut not in _VALIDATABLE:
        raise HTTPException(
            status_code=409,
            detail=f"Validation impossible : statut={obj.statut!r} (attendu PREVIEW ou RUNNING).",
        )

    # Routing multi-tenant : TAIYAT peut cibler épicerie (2, NOUTAM) ou
    # restaurant (3, INCONTOURNABLE). Par défaut, tenant de l'opérateur.
    effective_tenant_id = obj.target_tenant_id or current_user.tenant_id

    # Idempotence guard (régression 2026-04-21) : calcul du NET stock généré
    # par cet import. Si le net est > 0, l'import a encore un impact sur le
    # stock → bloquer pour éviter des doublons de validation.
    if effective_tenant_id == 2:  # épicerie
        from app.models.epicerie.stock_movement import EpicerieStockMovement
        net_stock = (await db.execute(
            select(func.coalesce(func.sum(EpicerieStockMovement.quantite), 0)).where(
                EpicerieStockMovement.etl_import_id == obj.id,
            )
        )).scalar_one()
        if net_stock is not None and float(net_stock) > 0:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "ALREADY_VALIDATED_WITH_MOVEMENTS",
                    "message": (
                        f"Import #{obj.id} a déjà un impact net de {net_stock} "
                        "sur le stock. Re-validation interdite (doublons). "
                        "Pour corriger : revert puis reopen."
                    ),
                    "net_stock": float(net_stock),
                },
            )

    # Dispatch service de réception selon tenant cible
    if effective_tenant_id == 2:
        from app.services.epicerie.reception_etl import recevoir_facture_etl
        result = await recevoir_facture_etl(
            db=db,
            etl_import=obj,
            tenant_id=effective_tenant_id,
            user_id=current_user.id,
        )
    elif effective_tenant_id == 3:
        from app.services.restaurant.reception_etl import recevoir_facture_etl_restaurant
        result = await recevoir_facture_etl_restaurant(
            db=db,
            etl_import=obj,
            tenant_id=effective_tenant_id,
            user_id=current_user.id,
        )
    else:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Tenant cible {effective_tenant_id!r} non supporté pour l'ETL "
                "(seulement 2=épicerie, 3=restaurant)."
            ),
        )

    # Si conflits de déduplication détectés : revenir à PREVIEW et bloquer
    if result.has_conflicts:
        obj.statut = _PREVIEW_STATUT
        obj.validation_step = None
        await db.commit()
        raise HTTPException(
            status_code=409,
            detail={
                "code": "CONFLICTS_PENDING",
                "message": (
                    f"{result.pending_conflicts} conflit(s) de déduplication "
                    "à résoudre avant validation"
                ),
                "pending_conflicts": result.pending_conflicts,
                "etl_import_id": import_id,
            },
        )

    obj.statut = _VALIDATED_STATUT
    await db.flush()
    await db.commit()
    await db.refresh(obj)

    # Auto-apprentissage brand_dictionary : chaque ligne validée avec
    # (marque non vide + catégorie résolue ≠ AUTRE) alimente le dict.
    # Non-bloquant : une erreur ici ne doit pas casser la validation.
    try:
        from scripts.etl.parsers.brand_dictionary import get_brand_dictionary
        from scripts.etl.parsers.brand_candidates import (
            get_brand_candidates, run_promotion_cycle,
        )
        bd = get_brand_dictionary()
        touched = False
        for ligne in obj.lignes_data or []:
            if not isinstance(ligne, dict):
                continue
            raw_brand = (ligne.get("marque") or "").strip().upper()
            cat = ligne.get("categorie_code")
            if not raw_brand or not cat or cat == "AUTRE" or len(raw_brand) < 2:
                continue
            if bd.add(raw_brand, [cat], source="auto_validate"):
                touched = True
        if touched:
            bd.save()

        # Apprentissage passif : tokens des lignes SANS marque explicite.
        # Détecte les marques récurrentes que l'opérateur ne saisit pas.
        cands = get_brand_candidates()
        cands.record_batch(obj.lignes_data or [], import_id)
        promoted = run_promotion_cycle()
        if promoted:
            logger.info("ETL import %d → %d brand(s) auto-promoted", import_id, promoted)
    except Exception as e:  # noqa: BLE001
        logger.warning("Brand dict auto-learning failed for import %d: %s", import_id, e)

    logger.info(
        "ETL import %d validated → FinanceInvoice %s (id=%d), "
        "%d mouvements ENTREE, %d produits synced",
        import_id,
        result.invoice.numero if result.invoice else "N/A",
        result.invoice.id if result.invoice else 0,
        result.mouvements_crees,
        result.produits_synced,
    )

    return EtlImportRead.model_validate(obj)


@router.post("/imports/{import_id}/reject", response_model=EtlImportRead)
async def reject_import(
    import_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(require_scope(Scope.SETTINGS_WRITE)),
):
    """Rejette un import PREVIEW → passe en REJECTED."""
    obj = await _get_visible_import_or_404(db, import_id, current_user.tenant_id)
    if obj.statut != _PREVIEW_STATUT:
        raise HTTPException(
            status_code=409,
            detail=f"Rejet impossible : statut={obj.statut!r} (attendu PREVIEW).",
        )

    obj.statut = _REJECTED_STATUT
    await db.flush()
    await db.commit()
    await db.refresh(obj)
    return EtlImportRead.model_validate(obj)


# ── Revert ────────────────────────────────────────────────────────────────────


@router.post("/imports/{import_id}/revert", response_model=RevertImportResponse)
async def revert_import_endpoint(
    import_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(require_scope(Scope.SETTINGS_WRITE)),
):
    """Annule un import VALIDATED : mouvements stock compensatoires, facture annulée, prix restaurés."""
    obj = await _get_visible_import_or_404(db, import_id, current_user.tenant_id)
    if obj.statut != _VALIDATED_STATUT:
        raise HTTPException(
            status_code=409,
            detail=f"Revert impossible : statut={obj.statut!r} (attendu VALIDATED).",
        )

    # Routing revert selon tenant cible (symétrique du dispatch validate)
    effective_tenant_id = obj.target_tenant_id or current_user.tenant_id
    if effective_tenant_id == 2:
        from app.services.epicerie.reception_etl import revert_import
        stats = await revert_import(
            db=db, etl_import=obj, tenant_id=effective_tenant_id, user_id=current_user.id,
        )
    elif effective_tenant_id == 3:
        from app.services.restaurant.reception_etl import revert_import_restaurant
        stats = await revert_import_restaurant(
            db=db, etl_import=obj, tenant_id=effective_tenant_id, user_id=current_user.id,
        )
    else:
        raise HTTPException(
            status_code=422,
            detail=f"Tenant cible {effective_tenant_id!r} non supporté pour le revert.",
        )

    await db.commit()
    logger.info("ETL import %d reverted by user %d", import_id, current_user.id)

    return stats


# ── Édition post-validation (Option B — P1) ──────────────────────────────────
# PATCH granulaire des champs financiers (quantite/prix/tva) d'un import VALIDATED.
# Cascades : delta stock AJUSTEMENT + recalcul FinanceInvoice + audit par champ.


def _normalize_dt_for_match(s: str) -> str:
    """Normalise un datetime ISO pour comparaison If-Match (Z ↔ +00:00 équivalents)."""
    return s.strip().strip('"').replace("Z", "+00:00")


def _parse_if_match_header(
    raw: Optional[str], server_updated_at
) -> None:
    """Valide le header If-Match contre etl_imports.updated_at.

    Format attendu : ISO 8601 (ex: '2026-04-11T17:35:50.181844+00:00').
    Tolérance : Z et +00:00 sont équivalents (normalisation avant comparaison).
    """
    if raw is None:
        raise HTTPException(
            status_code=428,
            detail={
                "code": "IF_MATCH_REQUIRED",
                "message": "Header If-Match obligatoire (updated_at ISO).",
            },
        )
    server_iso = server_updated_at.isoformat() if server_updated_at else ""
    if _normalize_dt_for_match(raw) != _normalize_dt_for_match(server_iso):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "STALE",
                "message": "If-Match ne correspond plus à l'état serveur.",
                "server_updated_at": server_iso,
            },
        )


def _edit_error_to_http(exc) -> HTTPException:
    """Mappe EtlValidationEditError → HTTPException avec code stable."""
    from app.services.epicerie.reception_etl import EtlValidationEditError
    if not isinstance(exc, EtlValidationEditError):
        raise exc
    status_map = {
        "NOT_VALIDATED": 409,
        "NO_INVOICE": 409,
        "WRONG_TENANT": 404,
        "INVOICE_LOCKED": 409,
        "LIGNE_OUT_OF_RANGE": 422,
    }
    status = status_map.get(exc.code, 500)
    return HTTPException(
        status_code=status,
        detail={"code": exc.code, "message": exc.message, **exc.extra},
    )


def _reopen_error_to_http(exc) -> HTTPException:
    """Mappe EtlReopenError → HTTPException avec code stable."""
    from app.services.epicerie.reception_etl import EtlReopenError
    if not isinstance(exc, EtlReopenError):
        raise exc
    status_map = {
        "NOT_REOPENABLE": 409,
        "WRONG_TENANT": 404,
    }
    status = status_map.get(exc.code, 500)
    return HTTPException(
        status_code=status,
        detail={"code": exc.code, "message": exc.message, **exc.extra},
    )


@router.patch(
    "/imports/{import_id}/validated-lignes",
    response_model=ValidatedLignesEditResponse,
)
async def edit_validated_lignes_endpoint(
    import_id: int,
    payload: ValidatedLignesBatchEditRequest,
    if_match: Optional[str] = Header(default=None, alias="If-Match"),
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(require_scope(Scope.SETTINGS_WRITE)),
):
    """Édite les lignes (financier + non-financier) d'un import VALIDATED.

    Champs financiers : quantite, prix_unitaire_cts, taux_tva_centieme.
    Champs non-financiers : marque, categorie_code.
    Gate : If-Match obligatoire, facture non-payée (financier uniquement),
    import en VALIDATED. Cascades : stock AJUSTEMENT + recalcul facture +
    cascade catalogue + audit par champ.

    Retourne aussi `warnings` (list) avec les alertes downstream :
    ex STOCK_NEGATIVE si le stock passe sous zéro (ventes intervenues entre
    validation et correction).
    """
    obj = await _get_visible_import_or_404(db, import_id, current_user.tenant_id)

    _parse_if_match_header(if_match, obj.updated_at)

    from app.services.epicerie.reception_etl import (
        edit_validated_lignes, EtlValidationEditError,
    )

    updates_dicts = [u.model_dump(exclude_unset=True) for u in payload.updates]
    try:
        edit_result = await edit_validated_lignes(
            db=db,
            etl_import=obj,
            updates=updates_dicts,
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
            request_context=None,
        )
    except EtlValidationEditError as exc:
        await db.rollback()
        raise _edit_error_to_http(exc)

    await db.commit()
    await db.refresh(obj)

    lignes = list(obj.lignes_data or [])
    ht_tot = sum(int(l.get("montant_ht_cts") or 0) for l in lignes)
    ttc_tot = sum(int(l.get("montant_ttc_cts") or 0) for l in lignes)

    data = ValidatedLignesEditResponse.model_validate(obj)
    data.lignes = [LigneFactureRead(**l) for l in lignes]
    data.montant_ht_calcule = ht_tot
    data.montant_ttc_calcule = ttc_tot
    data.warnings = edit_result.warnings

    logger.info(
        "ETL import %d validated-lignes edited by user %d (%d updates, %d warnings)",
        import_id, current_user.id, len(updates_dicts), len(edit_result.warnings),
    )
    return data


@router.patch(
    "/imports/{import_id}/invoice-meta",
    response_model=EtlImportRead,
)
async def edit_validated_invoice_meta_endpoint(
    import_id: int,
    payload: ValidatedInvoiceMetaEditRequest,
    if_match: Optional[str] = Header(default=None, alias="If-Match"),
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(require_scope(Scope.SETTINGS_WRITE)),
):
    """Édite les métadonnées facture d'un import VALIDATED (non-financier).

    Champs : numero_facture, date_facture, vendor_code.
    Cascade FinanceInvoice.reference + date_facture. Pas de gate PAYEE.
    """
    obj = await _get_visible_import_or_404(db, import_id, current_user.tenant_id)

    _parse_if_match_header(if_match, obj.updated_at)

    from app.services.epicerie.reception_etl import (
        edit_validated_invoice_meta, EtlValidationEditError,
    )

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(
            status_code=422,
            detail={"code": "EMPTY_UPDATE", "message": "Aucun champ à mettre à jour."},
        )

    try:
        await edit_validated_invoice_meta(
            db=db, etl_import=obj, updates=updates,
            tenant_id=current_user.tenant_id, user_id=current_user.id,
            request_context=None,
        )
    except EtlValidationEditError as exc:
        await db.rollback()
        raise _edit_error_to_http(exc)

    await db.commit()
    await db.refresh(obj)
    logger.info(
        "ETL import %d invoice-meta edited by user %d", import_id, current_user.id,
    )
    return EtlImportRead.model_validate(obj)


# ── Reopen (P7 — sortir du cul-de-sac REJECTED/REVERTED) ────────────────────


@router.post("/imports/{import_id}/reopen", response_model=EtlImportRead)
async def reopen_import_endpoint(
    import_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(require_scope(Scope.SETTINGS_WRITE)),
):
    """Rouvre un import REJECTED ou REVERTED en statut PREVIEW.

    Cas d'usage :
      - REJECTED : l'opérateur a rejeté puis souhaite corriger/revalider
      - REVERTED : l'import a été annulé, on veut retenter une correction +
        nouvelle validation

    Cascades : aucune pour REJECTED. Pour REVERTED, reset des champs
    reverted_at/reverted_by_id. Les mouvements stock compensatoires créés
    par le revert sont conservés ; la re-validation future créera de
    nouveaux ENTREE qui s'ajoutent (net +N reste comptablement cohérent).

    Notifications (REVERTED uniquement) : 1 par destinataire parmi
    {validateur original, reverteur}, sauf le réouvreur lui-même.
    """
    obj = await _get_visible_import_or_404(db, import_id, current_user.tenant_id)

    from app.services.epicerie.reception_etl import (
        reopen_import, EtlReopenError,
    )

    try:
        await reopen_import(
            db=db,
            etl_import=obj,
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
            request_context=None,
        )
    except EtlReopenError as exc:
        await db.rollback()
        raise _reopen_error_to_http(exc)

    await db.commit()
    await db.refresh(obj)
    logger.info(
        "ETL import %d reopened by user %d", import_id, current_user.id,
    )
    return EtlImportRead.model_validate(obj)


# ── Reclassification KNN (PREVIEW) ──────────────────────────────────────────


@router.post("/imports/{import_id}/reclassify", response_model=EtlImportDetail)
async def reclassify_import(
    import_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(require_scope(Scope.SETTINGS_WRITE)),
):
    """Re-classe par KNN les lignes PREVIEW sans catégorie (null/AUTRE).

    Applique dans l'ordre : keyword rules → KNN Jaro-Winkler (seuil 0.70) sur
    le corpus labellisé du CatalogueProduit. Enregistre les corrections dans
    EtlCorrectionHistory pour l'auto-apprentissage.
    """
    obj = await _get_visible_import_or_404(db, import_id, current_user.tenant_id)
    if obj.statut != _PREVIEW_STATUT:
        raise HTTPException(status_code=409, detail="Reclassification impossible hors PREVIEW.")

    from app.services.catalogue.etl_classification import classify_by_knn, classify_categorie_code
    from app.services.catalogue.etl_deduplication import normalize_designation
    from app.models.catalogue.catalogue_produit import CatalogueProduit
    from app.models.catalogue.etl_correction_history import EtlCorrectionHistory
    from sqlalchemy import and_

    corpus_q = await db.execute(
        select(CatalogueProduit.designation_norm, CatalogueProduit.categorie_code).where(
            and_(
                CatalogueProduit.categorie_code.isnot(None),
                CatalogueProduit.categorie_code != "AUTRE",
                CatalogueProduit.designation_norm.isnot(None),
            )
        )
    )
    labelled = [(row[0], row[1]) for row in corpus_q.all()]

    lignes = list(obj.lignes_data or [])
    classified = 0
    enriched = 0

    # Enrichissement universel depuis la désignation — remplit marque,
    # conditionnement, volume, contenant, degré alcool si manquants.
    from app.services.catalogue.etl_designation_enrichment import (
        enrich_ligne_from_designation,
    )
    from app.services.catalogue.etl_import_service import compute_line_confidence
    from app.etl_types import LigneParsee as _LigneParsee
    for ligne in lignes:
        try:
            stub = _LigneParsee(
                designation=ligne.get("designation", "") or "",
                unite_base=ligne.get("unite_base", "U") or "U",
                source_fournisseur=ligne.get("source_fournisseur", "") or "",
                ean=ligne.get("ean"),
                marque=ligne.get("marque"),
                conditionnement=ligne.get("conditionnement"),
                volume_unitaire_ml=ligne.get("volume_unitaire_ml"),
                contenant=ligne.get("contenant"),
                degre_alcool=ligne.get("degre_alcool"),
                categorie_code=ligne.get("categorie_code"),
            )
            enrich_ligne_from_designation(stub)
            for field in ("marque", "conditionnement", "volume_unitaire_ml", "contenant", "degre_alcool", "unite_base"):
                old = ligne.get(field)
                new = getattr(stub, field, None)
                if new and not old:
                    ligne[field] = new
                    enriched += 1
        except Exception:
            pass

    for ligne in lignes:
        cat = ligne.get("categorie_code")
        if cat and cat != "AUTRE":
            continue

        desig = ligne.get("designation") or ligne.get("designation_raw") or ""
        if not desig.strip():
            continue

        norm = normalize_designation(desig)
        new_cat = classify_categorie_code(norm)

        if new_cat == "AUTRE" and labelled:
            knn_cat = classify_by_knn(norm, labelled, seuil=0.70)
            if knn_cat != "AUTRE":
                new_cat = knn_cat

        if new_cat and new_cat != "AUTRE" and new_cat != cat:
            ligne["categorie_code"] = new_cat
            classified += 1
            try:
                # `norm` vient de normalize_designation(desig) quelques lignes plus haut,
                # donc c'est déjà lowercase ascii — OK à stocker tel quel.
                designation_norm = norm or normalize_designation(ligne.get("designation", ""))
                db.add(EtlCorrectionHistory(
                    designation_norm=designation_norm[:500],
                    field_corrected="categorie_code",
                    old_value=str(cat) if cat else None,
                    new_value=new_cat,
                    etl_import_id=import_id,
                ))
            except Exception:
                pass

    # Recalcul confidence score après enrichissement + reclassification
    for ligne in lignes:
        try:
            stub = _LigneParsee(
                designation=ligne.get("designation", "") or "",
                unite_base=ligne.get("unite_base", "U") or "U",
                source_fournisseur=ligne.get("source_fournisseur", "") or "",
                ean=ligne.get("ean"),
                marque=ligne.get("marque"),
                categorie_code=ligne.get("categorie_code"),
                quantite=ligne.get("quantite"),
                prix_unitaire_cts=ligne.get("prix_unitaire_cts"),
                montant_ht_cts=ligne.get("montant_ht_cts"),
            )
            ligne["confidence_score"] = compute_line_confidence(stub)
        except Exception:
            pass

    # Régénération `similar_products` avec les champs enrichis (categorie_code,
    # marque, conditionnement, volume, prix, TVA). Réplique la logique de
    # run_import preview_mode pour que les imports PREVIEW existants
    # bénéficient du fix sans ré-upload.
    try:
        from app.services.catalogue.etl_deduplication import (
            classify_designation_top_n, build_idf_from_candidates,
        )
        from app.repositories.catalogue.catalogue_produit import (
            AsyncCatalogueProduitRepository,
        )
        produit_repo = AsyncCatalogueProduitRepository(db)
        preview_candidates = await produit_repo.get_all_candidates()
        if preview_candidates:
            build_idf_from_candidates(preview_candidates)
            for ligne in lignes:
                if ligne.get("ean"):
                    continue  # si EAN, déjà match direct → pas de similar
                desig = ligne.get("designation") or ligne.get("designation_raw") or ""
                if not desig.strip():
                    continue
                top = classify_designation_top_n(desig, preview_candidates, seuil=0.70, n=3)
                if not top:
                    ligne["similar_products"] = None
                    continue
                enriched_similar = []
                for t in top:
                    prod = await produit_repo.get_by_id(t["candidate_id"])
                    enriched_similar.append({
                        "candidate_id": t["candidate_id"],
                        "designation": prod.designation if prod else t["designation_norm"],
                        "ean": prod.ean if prod else None,
                        "categorie_code": prod.categorie_code if prod else None,
                        "marque": prod.marque if prod else None,
                        "conditionnement": prod.conditionnement if prod else None,
                        "volume_unitaire_ml": getattr(prod, "volume_unitaire_ml", None) if prod else None,
                        "prix_unitaire_cts": prod.prix_unitaire_cts if prod else None,
                        "taux_tva_centieme": getattr(prod, "taux_tva_centieme", None) if prod else None,
                        "score": t["score"],
                    })
                ligne["similar_products"] = enriched_similar
    except Exception as e:  # noqa: BLE001
        logger.warning("Reclassify: similar_products regen failed: %s", e)

    obj.lignes_data = _index_lignes(lignes)
    ht, ttc = _compute_lignes_totals(lignes)

    await db.flush()
    await db.commit()
    await db.refresh(obj)

    logger.info(
        "ETL import %d reclassified %d lines by user %d (+%d enrichments, similar_products regen)",
        import_id, classified, current_user.id, enriched,
    )

    data = EtlImportDetail.model_validate(obj)
    data.lignes = [LigneFactureRead(**l) for l in obj.lignes_data]
    data.montant_ht_calcule = ht
    data.montant_ttc_calcule = ttc
    return data


# ── Fetch Images ──────────────────────────────────────────────────────────────


@router.post("/fetch-images")
async def fetch_images_endpoint(
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(require_scope(Scope.SETTINGS_WRITE)),
):
    """Fetch images pour tous les produits épicerie sans image (synchrone)."""
    from app.repositories.epicerie.produit import AsyncEpicerieProduitRepository
    from app.services.epicerie.image_fetcher import fetch_product_image

    repo = AsyncEpicerieProduitRepository(db)
    products = await repo.list_without_image(current_user.tenant_id, limit=50)

    fetched = 0
    for p in products:
        path = fetch_product_image(
            product_id=p.id,
            ean=p.ean,
            designation=p.designation_clean,
            marque=None,
        )
        if path:
            p.image_url = path
            fetched += 1

    if fetched > 0:
        await db.flush()
        await db.commit()

    return {"fetched": fetched, "total": len(products)}


# ── Categories ────────────────────────────────────────────────────────────────


@router.get("/categories", response_model=CategoriesResponse)
async def get_categories(
    _=Depends(require_scope(Scope.SETTINGS_READ)),
):
    """Retourne les 91 catégories alimentaires groupées par famille."""
    groups = []
    total = 0
    for code, label, items in _CATEGORY_GROUPS:
        cat_items = [CategoryItem(code=c, label=l) for c, l in items]
        total += len(cat_items)
        groups.append(CategoryGroup(group=code, label=label, items=cat_items))
    return CategoriesResponse(groups=groups, total=total)


# ── Suggestions intelligentes (Phase 2) ──────────────────────────────────────


@router.get("/suggest/category")
async def suggest_category(
    designation: str = Query(..., min_length=3, max_length=200),
    limit: int = Query(5, ge=1, le=10),
    db: AsyncSession = Depends(get_async_db),
    _=Depends(require_scope(Scope.SETTINGS_READ)),
):
    """Top-N catégories par KNN Jaro-Winkler sur les produits labellisés du catalogue."""
    from app.services.catalogue.etl_classification import classify_by_knn_top_n
    from app.services.catalogue.etl_deduplication import normalize_designation
    from app.repositories.catalogue.catalogue_produit import AsyncCatalogueProduitRepository
    from sqlalchemy import select, and_
    from app.models.catalogue.catalogue_produit import CatalogueProduit

    norm = normalize_designation(designation)
    result = await db.execute(
        select(CatalogueProduit.designation_norm, CatalogueProduit.categorie_code).where(
            and_(
                CatalogueProduit.categorie_code.isnot(None),
                CatalogueProduit.categorie_code != "AUTRE",
                CatalogueProduit.designation_norm.isnot(None),
            )
        )
    )
    labelled = [(row[0], row[1]) for row in result.all()]
    suggestions = classify_by_knn_top_n(norm, labelled, n=limit)

    # Enrichir avec le label humain
    cat_labels = {c: l for _, _, items in _CATEGORY_GROUPS for c, l in items}
    for s in suggestions:
        s["label"] = cat_labels.get(s["code"], s["code"])
    return {"suggestions": suggestions}


@router.get("/suggest/brand")
async def suggest_brand(
    q: str = Query(..., min_length=1, max_length=100),
    limit: int = Query(10, ge=1, le=30),
    _=Depends(require_scope(Scope.SETTINGS_READ)),
):
    """Recherche fuzzy dans le dictionnaire de marques (prefix/substring)."""
    from scripts.etl.parsers.brand_dictionary import get_brand_dictionary

    brand_dict = get_brand_dictionary()
    query_lower = q.lower()
    results = []
    for name, entry in brand_dict._brands.items():
        if query_lower in name.lower():
            results.append({
                "name": name,
                "categories": entry.categories,
                "usage_count": entry.usage_count,
            })
    results.sort(key=lambda r: r["usage_count"], reverse=True)
    return {"suggestions": results[:limit]}


@router.get("/suggest/product")
async def suggest_product(
    designation: str = Query(..., min_length=3, max_length=200),
    limit: int = Query(5, ge=1, le=10),
    db: AsyncSession = Depends(get_async_db),
    _=Depends(require_scope(Scope.SETTINGS_READ)),
):
    """Top-N produits similaires par Soft TF-IDF dans le catalogue."""
    from app.services.catalogue.etl_deduplication import (
        classify_designation_top_n,
        build_idf_from_candidates,
    )
    from app.repositories.catalogue.catalogue_produit import AsyncCatalogueProduitRepository

    repo = AsyncCatalogueProduitRepository(db)
    candidates = await repo.get_all_candidates()
    build_idf_from_candidates(candidates)
    top_n = classify_designation_top_n(designation, candidates, n=limit)

    # Enrichir avec les données produit
    for item in top_n:
        produit = await repo.get_by_id(item["candidate_id"])
        if produit:
            item["designation"] = produit.designation
            item["ean"] = produit.ean
            item["categorie_code"] = produit.categorie_code
            item["prix_unitaire_cts"] = produit.prix_unitaire_cts
    return {"suggestions": top_n}


# ── Dashboard analytique (Phase 3) ──────────────────────────────────────────


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    db: AsyncSession = Depends(get_async_db),
    _=Depends(require_scope(Scope.SETTINGS_READ)),
):
    """Dashboard analytique ETL : KPIs, tendance qualité, stats fournisseurs."""
    from app.models.catalogue.etl_import import EtlImport
    from app.models.catalogue.etl_conflict import EtlConflict

    # Total imports
    total_q = await db.execute(select(func.count(EtlImport.id)))
    total_imports = total_q.scalar() or 0

    # Par statut
    status_q = await db.execute(
        select(EtlImport.statut, func.count(EtlImport.id)).group_by(EtlImport.statut)
    )
    by_status = {row[0]: row[1] for row in status_q.all()}

    # Qualité moyenne globale
    avg_q = await db.execute(
        select(func.avg(EtlImport.quality_score)).where(EtlImport.quality_score.isnot(None))
    )
    avg_quality = avg_q.scalar()

    # Trend : 30 derniers imports avec quality_score
    trend_q = await db.execute(
        select(
            EtlImport.id, EtlImport.date_facture, EtlImport.quality_score,
            EtlImport.vendor_code, EtlImport.nb_lignes_total,
        )
        .where(EtlImport.quality_score.isnot(None))
        .order_by(EtlImport.id.desc())
        .limit(30)
    )
    quality_trend = [
        DashboardQualityTrend(
            id=r[0], date=r[1], quality_score=r[2],
            vendor_code=r[3], nb_lignes_total=r[4],
        )
        for r in trend_q.all()
    ]

    # Stats par fournisseur
    vendor_q = await db.execute(
        select(
            EtlImport.vendor_code,
            func.count(EtlImport.id),
            func.avg(EtlImport.quality_score),
        )
        .where(EtlImport.vendor_code.isnot(None))
        .group_by(EtlImport.vendor_code)
    )
    vendor_stats = [
        DashboardVendorStats(
            vendor_code=r[0], total_imports=r[1],
            avg_quality=round(r[2], 1) if r[2] else None,
        )
        for r in vendor_q.all()
    ]

    # Conflits pending
    conflict_q = await db.execute(
        select(func.count(EtlConflict.id)).where(EtlConflict.resolution == "PENDING")
    )
    pending_conflicts = conflict_q.scalar() or 0

    # Temps moyen de correction (VALIDATED/REJECTED only)
    time_q = await db.execute(
        select(
            func.avg(
                func.extract("epoch", EtlImport.updated_at) - func.extract("epoch", EtlImport.created_at)
            )
        ).where(EtlImport.statut.in_(["VALIDATED", "REJECTED"]))
    )
    avg_time = time_q.scalar()

    return DashboardResponse(
        total_imports=total_imports,
        by_status=by_status,
        avg_quality_global=round(avg_quality, 1) if avg_quality else None,
        quality_trend=quality_trend,
        vendor_stats=vendor_stats,
        pending_conflicts=pending_conflicts,
        avg_correction_time_sec=round(avg_time, 0) if avg_time else None,
    )


# ── Brand candidates (E4 — apprentissage passif) ──────────────────────────


@router.get("/brand-candidates")
async def list_brand_candidates(
    limit: int = Query(100, ge=1, le=500),
    _=Depends(require_scope(Scope.SETTINGS_READ)),
):
    """Liste les tokens récurrents détectés comme marques candidates.

    Pour chaque candidat : catégories observées (comptage), imports distincts,
    ready (prêt à promouvoir selon seuils conservateurs), promoted (déjà
    passé dans le brand_dictionary).
    """
    from scripts.etl.parsers.brand_candidates import get_brand_candidates
    cands = get_brand_candidates()
    ready_set = {t for t, _ in cands.promote_ready()}

    items = []
    for token, entry in cands._data.items():
        cats = entry.get("categories", {})
        total = sum(cats.values())
        best_cat = max(cats.items(), key=lambda x: x[1])[0] if cats else None
        items.append({
            "token": token,
            "total_count": total,
            "distinct_imports": len(entry.get("import_ids", [])),
            "categories": cats,
            "best_category": best_cat,
            "last_seen": entry.get("last_seen"),
            "promoted": bool(entry.get("promoted")),
            "ready": token in ready_set,
        })
    # Trier : ready en haut, puis total_count desc
    items.sort(key=lambda x: (not x["ready"], -x["total_count"]))
    return {
        "stats": cands.stats(),
        "items": items[:limit],
    }


@router.post("/brand-candidates/promote")
async def promote_brand_candidates(
    _=Depends(require_scope(Scope.SETTINGS_WRITE)),
):
    """Force un cycle de promotion des candidats prêts → brand_dictionary."""
    from scripts.etl.parsers.brand_candidates import run_promotion_cycle
    from scripts.etl.parsers.brand_dictionary import get_brand_dictionary
    before = get_brand_dictionary().size
    promoted = run_promotion_cycle()
    after = get_brand_dictionary().size
    return {
        "promoted": promoted,
        "brand_dict_size_before": before,
        "brand_dict_size_after": after,
    }


@router.delete("/brand-candidates/{token}")
async def reject_brand_candidate(
    token: str,
    _=Depends(require_scope(Scope.SETTINGS_WRITE)),
):
    """Supprime un candidat (token saisi par erreur ou bruit récurrent).

    Effet : le token ne reviendra pas dans la liste. S'il est ré-observé
    plus tard, il sera à nouveau tracké. Pour blacklister définitivement,
    ajouter à `_STOP_TOKENS` dans brand_candidates.py.
    """
    from scripts.etl.parsers.brand_candidates import get_brand_candidates
    cands = get_brand_candidates()
    t = token.strip().upper()
    if t not in cands._data:
        raise HTTPException(status_code=404, detail=f"Candidat {t!r} introuvable")
    del cands._data[t]
    cands.save()
    return {"removed": t}


# ── Métriques qualité par fournisseur (taux remplissage attribut) ──────────


@router.get("/quality-metrics")
async def get_quality_metrics(
    days: int = Query(90, ge=1, le=365),
    db: AsyncSession = Depends(get_async_db),
    _=Depends(require_scope(Scope.SETTINGS_READ)),
):
    """Taux de remplissage par attribut × fournisseur sur les N derniers jours.

    Permet d'identifier où un parser/fournisseur sous-performe :
      - EAN absent → catalogue sans code-barre
      - Marque / conditionnement / volume → parser minimal (ex: ETHAN xlsx)
      - Catégorie AUTRE élevée → KNN à enrichir ou seed corrections
    """
    from app.models.catalogue.etl_import import EtlImport
    from datetime import datetime, timedelta

    cutoff = datetime.utcnow() - timedelta(days=days)
    rows = await db.execute(
        select(
            EtlImport.vendor_code,
            EtlImport.lignes_data,
            EtlImport.quality_score,
        )
        .where(
            EtlImport.vendor_code.isnot(None),
            EtlImport.lignes_data.isnot(None),
            EtlImport.created_at >= cutoff,
            EtlImport.statut.in_(["PREVIEW", "VALIDATED", "SUCCES", "PARTIEL"]),
        )
    )

    agg: dict[str, dict] = {}
    for vendor_code, lignes_data, quality_score in rows.all():
        if not vendor_code or not lignes_data:
            continue
        bucket = agg.setdefault(vendor_code, {
            "vendor_code": vendor_code,
            "nb_imports": 0,
            "nb_lignes": 0,
            "quality_sum": 0.0,
            "quality_count": 0,
            "fields": {
                "ean": 0, "marque": 0, "categorie": 0,
                "conditionnement": 0, "volume_unitaire_ml": 0,
                "prix_unitaire_cts": 0, "taux_tva_centieme": 0,
                "confidence_ge_60": 0,
            },
        })
        bucket["nb_imports"] += 1
        if quality_score is not None:
            bucket["quality_sum"] += float(quality_score)
            bucket["quality_count"] += 1
        for ligne in lignes_data:
            if not isinstance(ligne, dict):
                continue
            bucket["nb_lignes"] += 1
            fields = bucket["fields"]
            if ligne.get("ean"):
                fields["ean"] += 1
            if ligne.get("marque"):
                fields["marque"] += 1
            cat = ligne.get("categorie_code")
            if cat and cat != "AUTRE":
                fields["categorie"] += 1
            if ligne.get("conditionnement"):
                fields["conditionnement"] += 1
            if ligne.get("volume_unitaire_ml"):
                fields["volume_unitaire_ml"] += 1
            if ligne.get("prix_unitaire_cts"):
                fields["prix_unitaire_cts"] += 1
            if ligne.get("taux_tva_centieme"):
                fields["taux_tva_centieme"] += 1
            score = ligne.get("confidence_score") or 0
            if score >= 60:
                fields["confidence_ge_60"] += 1

    vendors = []
    for v in agg.values():
        nb = v["nb_lignes"] or 1
        vendors.append({
            "vendor_code": v["vendor_code"],
            "nb_imports": v["nb_imports"],
            "nb_lignes": v["nb_lignes"],
            "avg_quality": round(v["quality_sum"] / v["quality_count"], 1) if v["quality_count"] else None,
            "pct_ean": round(100 * v["fields"]["ean"] / nb, 1),
            "pct_marque": round(100 * v["fields"]["marque"] / nb, 1),
            "pct_categorie": round(100 * v["fields"]["categorie"] / nb, 1),
            "pct_conditionnement": round(100 * v["fields"]["conditionnement"] / nb, 1),
            "pct_volume": round(100 * v["fields"]["volume_unitaire_ml"] / nb, 1),
            "pct_prix": round(100 * v["fields"]["prix_unitaire_cts"] / nb, 1),
            "pct_tva": round(100 * v["fields"]["taux_tva_centieme"] / nb, 1),
            "pct_confidence_ok": round(100 * v["fields"]["confidence_ge_60"] / nb, 1),
        })
    vendors.sort(key=lambda x: -x["nb_lignes"])
    return {"days": days, "vendors": vendors}
