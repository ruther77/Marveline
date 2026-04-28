"""Re-parse tous les imports ETL existants avec le parser actuel.

Préserve les corrections manuelles (catégorie, marque, EAN) stockées
dans etl_correction_history en les ré-appliquant après le re-parse.
Recalcule le confidence_score de chaque ligne.

Usage : docker exec futurproj_api python3 scripts/etl/reparse_all_imports.py
        docker exec futurproj_api python3 scripts/etl/reparse_all_imports.py --id 6543
"""
import dataclasses
import json
import logging
import os
import re
import sys
import time
from argparse import ArgumentParser

if "/app" not in sys.path:
    sys.path.insert(0, "/app")

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    logger.error("DATABASE_URL non défini")
    sys.exit(1)

UPLOADS_BASE = os.environ.get("UPLOAD_DIR", "uploads")
ETL_DIR = os.path.join(UPLOADS_BASE, "etl")

engine = create_engine(DATABASE_URL)

# Champs manuellement corrigés qu'il faut préserver
_MANUAL_FIELDS = {"categorie_code", "marque", "ean"}


def _compute_confidence(l: dict) -> int:
    """Score confiance 0-100 (réplique légère de compute_line_confidence)."""
    score = 0
    if l.get("ean"):
        score += 25 if re.match(r"^\d{8}(\d{5})?$", l["ean"]) else 10
    if l.get("categorie_code") and l["categorie_code"] != "AUTRE":
        score += 20
    if l.get("prix_unitaire_cts") and l["prix_unitaire_cts"] > 0:
        score += 20
    if l.get("quantite") and l["quantite"] > 0:
        score += 15
    if l.get("marque"):
        score += 10
    if l.get("quantite") and l.get("prix_unitaire_cts") and l.get("montant_ht_cts") is not None:
        if abs(round(l["quantite"] * l["prix_unitaire_cts"]) - l["montant_ht_cts"]) < 2:
            score += 10
    return min(score, 100)


def _load_corrections(conn) -> dict[int, list[tuple[str, str, str]]]:
    """Charge toutes les corrections manuelles, groupées par import_id.

    Retourne {import_id: [(field, new_value, designation_norm), ...]}.
    On garde la DERNIÈRE correction par (designation_norm, field).
    """
    r = conn.execute(text(
        "SELECT etl_import_id, field_corrected, new_value, designation_norm "
        "FROM etl_correction_history ORDER BY id"
    ))
    # Dédupliquer : dernière correction gagne
    latest: dict[int, dict[tuple[str, str], str]] = {}
    for import_id, field, value, desig in r:
        latest.setdefault(import_id, {})[(desig, field)] = value

    result: dict[int, list[tuple[str, str, str]]] = {}
    for import_id, entries in latest.items():
        result[import_id] = [(field, value, desig) for (desig, field), value in entries.items()]
    return result


def _apply_corrections(lignes: list[dict], corrections: list[tuple[str, str, str]]) -> int:
    """Applique les corrections manuelles sur les lignes parsées.

    Match par designation (normalisée, préfixe 25 chars).
    Retourne le nombre de corrections appliquées.
    """
    applied = 0
    for field, value, desig_norm in corrections:
        dn = desig_norm.lower().strip()
        for l in lignes:
            l_desig = (l.get("designation_norm") or l.get("designation", "")).lower().strip()
            if l_desig == dn or (len(dn) >= 10 and l_desig[:25] == dn[:25]):
                l[field] = value
                applied += 1
                break
    return applied


def reparse_import(import_id: int, vendor_code: str, corrections: list | None) -> dict:
    """Re-parse un import et retourne les nouvelles données."""
    pdf_path = os.path.join(ETL_DIR, f"{import_id}.pdf")
    if not os.path.isfile(pdf_path):
        return {"status": "skip", "reason": "pdf_missing"}

    try:
        if vendor_code == "METRO":
            from scripts.etl.parsers.metro.core import parse_facture
        else:
            return {"status": "skip", "reason": f"vendor_{vendor_code}"}

        lignes, metadata = parse_facture(pdf_path)
    except Exception as exc:
        return {"status": "error", "reason": str(exc)[:120]}

    lignes_data = [dataclasses.asdict(l) for l in lignes]

    # Ré-appliquer les corrections manuelles AVANT le calcul de confidence
    corrections_applied = 0
    if corrections:
        corrections_applied = _apply_corrections(lignes_data, corrections)

    # Calculer confidence_score
    for l in lignes_data:
        l["confidence_score"] = _compute_confidence(l)

    meta_fields = {}
    if metadata:
        meta_fields["numero_facture"] = metadata.numero_facture
        meta_fields["date_facture"] = metadata.date_facture
        meta_fields["montant_ht_total"] = metadata.montant_ht_total
        meta_fields["montant_tva_total"] = metadata.montant_tva_total
        meta_fields["montant_ttc_total"] = metadata.montant_ttc_total
        meta_fields["vendor_code"] = metadata.vendor_code
        meta_fields["quality_score"] = metadata.quality_score
        meta_fields["ecart_reconciliation"] = metadata.ecart_reconciliation

    return {
        "status": "ok",
        "lignes_data": lignes_data,
        "nb_lignes": len(lignes_data),
        "meta_fields": meta_fields,
        "ecart": meta_fields.get("ecart_reconciliation"),
        "corrections_applied": corrections_applied,
    }


def main():
    parser = ArgumentParser(description="Re-parse imports ETL")
    parser.add_argument("--id", type=int, help="Re-parser un seul import")
    args = parser.parse_args()

    t0 = time.time()

    with engine.connect() as conn:
        # Charger corrections manuelles
        all_corrections = _load_corrections(conn)
        logger.info("Corrections manuelles chargées : %d imports, %d corrections",
                     len(all_corrections), sum(len(v) for v in all_corrections.values()))

        if args.id:
            rows = conn.execute(text(
                "SELECT id, vendor_code, statut FROM etl_imports WHERE id = :id"
            ), {"id": args.id}).fetchall()
        else:
            rows = conn.execute(text(
                "SELECT id, vendor_code, statut FROM etl_imports ORDER BY id"
            )).fetchall()

    total = len(rows)
    logger.info("Imports à re-parser : %d", total)

    stats = {"ok": 0, "skip": 0, "error": 0, "ecart_zero": 0, "corrections": 0}

    with Session(engine) as session:
        for i, (import_id, vendor_code, statut) in enumerate(rows):
            corrections = all_corrections.get(import_id)
            result = reparse_import(import_id, vendor_code or "METRO", corrections)

            if result["status"] == "skip":
                stats["skip"] += 1
                continue

            if result["status"] == "error":
                stats["error"] += 1
                logger.warning("  ERR import #%d : %s", import_id, result["reason"])
                continue

            meta = result["meta_fields"]
            session.execute(text("""
                UPDATE etl_imports SET
                    lignes_data = :lignes_data,
                    nb_lignes_total = :nb_lignes,
                    nb_lignes_ok = :nb_lignes,
                    numero_facture = :numero_facture,
                    date_facture = :date_facture,
                    montant_ht_total = :montant_ht_total,
                    montant_tva_total = :montant_tva_total,
                    montant_ttc_total = :montant_ttc_total,
                    vendor_code = :vendor_code,
                    quality_score = :quality_score,
                    ecart_reconciliation = :ecart_reconciliation,
                    updated_at = NOW()
                WHERE id = :import_id
            """), {
                "import_id": import_id,
                "lignes_data": json.dumps(result["lignes_data"]),
                "nb_lignes": result["nb_lignes"],
                "numero_facture": meta.get("numero_facture"),
                "date_facture": meta.get("date_facture"),
                "montant_ht_total": meta.get("montant_ht_total"),
                "montant_tva_total": meta.get("montant_tva_total"),
                "montant_ttc_total": meta.get("montant_ttc_total"),
                "vendor_code": meta.get("vendor_code"),
                "quality_score": meta.get("quality_score"),
                "ecart_reconciliation": result["ecart"],
            })

            stats["ok"] += 1
            stats["corrections"] += result.get("corrections_applied", 0)
            if result["ecart"] is not None and abs(result["ecart"]) < 0.01:
                stats["ecart_zero"] += 1

            if (i + 1) % 50 == 0:
                session.commit()
                elapsed = time.time() - t0
                rate = (i + 1) / elapsed
                logger.info(
                    "  %d/%d (%.0f/s) — OK=%d SKIP=%d ERR=%d corr=%d",
                    i + 1, total, rate,
                    stats["ok"], stats["skip"], stats["error"], stats["corrections"],
                )

        session.commit()

    elapsed = time.time() - t0
    logger.info("")
    logger.info("=" * 60)
    logger.info("TERMINÉ en %.1fs — %d imports", elapsed, total)
    logger.info("  OK=%d  SKIP=%d  ERR=%d", stats["ok"], stats["skip"], stats["error"])
    logger.info("  Écart=0 : %d  Corrections ré-appliquées : %d", stats["ecart_zero"], stats["corrections"])
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
