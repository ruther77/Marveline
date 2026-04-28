"""Migration de données : convertit les produits couleur/gamme/taille en ProductVariant.

Pour chaque famille définie dans FAMILIES :
  1. Crée ou identifie le produit parent (via SKU parent)
  2. Crée une ProductVariant pour chaque produit fils (par SKU fils)
  3. Réaffecte les références (reservation_lines, movement_items, bundle_items)
  4. Soft-delete les anciens produits fils

Idempotent : si la variante existe déjà (même label pour ce parent), skip.
Toutes les erreurs rollback la transaction complète.

Usage :
    docker compose exec api python scripts/migrate_color_products.py [--dry-run]
    docker compose exec api python scripts/migrate_color_products.py [--family HOU-CHA]
"""
import sys
import os
import logging
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import SessionLocal

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)

DRY_RUN = "--dry-run" in sys.argv
ONLY_FAMILY = next((sys.argv[i + 1] for i, a in enumerate(sys.argv) if a == "--family"), None)

TENANT_ID = 1


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Définition des familles ───────────────────────────────────────────────────
#
# Chaque famille décrit :
#   parent_sku   : SKU du produit parent (créé si absent)
#   parent_name  : Nom du produit parent
#   category     : Slug catégorie (valeur string dans products.category)
#   price_per_day: Prix parent en centimes
#   children     : list de dicts {sku, label, color?, size?, gamme?, price_per_day?}
#                  sku → SKU du produit existant à convertir en variante
#                  label → Label affiché (obligatoire, clé d'unicité)
#
FAMILIES = [
    # ── Housses de chaise — couleur ──────────────────────────────────────────
    {
        "parent_sku": "HOU-CHA",
        "parent_name": "Housse de chaise",
        "category": "housses",
        "price_per_day_cents": 240,
        "children": [
            {"sku": "HOU-CHA-BLC", "label": "Blanche", "color": "blanc"},
            {"sku": "HOU-CHA-IVO", "label": "Ivoire",  "color": "ivoire"},
        ],
    },
    # ── Serviettes coton standard — couleur ──────────────────────────────────
    {
        "parent_sku": "SER-COT",
        "parent_name": "Serviette de table coton",
        "category": "serviettes",
        "price_per_day_cents": 90,
        "children": [
            {"sku": "SER-COT-BLC", "label": "Blanche", "color": "blanc"},
            {"sku": "SER-COT-IVO", "label": "Ivoire",  "color": "ivoire"},
        ],
    },
    # ── Serviettes coton couleur — couleur ───────────────────────────────────
    {
        "parent_sku": "SER-COT-COL",
        "parent_name": "Serviette de table coton couleur",
        "category": "serviettes",
        "price_per_day_cents": 180,
        "children": [
            {"sku": "SER-COT-BOR", "label": "Bordeaux",    "color": "bordeaux"},
            {"sku": "SER-COT-NOI", "label": "Noire",       "color": "noir"},
            {"sku": "SER-COT-ROU", "label": "Rouge",       "color": "rouge"},
            {"sku": "SER-COT-VAM", "label": "Vert amande", "color": "vert_amande"},
            {"sku": "SER-COT-VSA", "label": "Vert sapin",  "color": "vert_sapin"},
        ],
    },
    # ── Nappes rondes couleurs ────────────────────────────────────────────────
    {
        "parent_sku": "NAP-RND-240",
        "parent_name": "Nappe ronde coton 240cm",
        "category": "nappes",
        "price_per_day_cents": 1500,
        "children": [
            # Couleurs : le produit blanc est le produit existant "blanc"
            # NAP-RND-240-IVO est déjà dans la DB comme produit séparé
            {"sku": "NAP-RND-240-IVO", "label": "Ivoire", "color": "ivoire"},
        ],
    },
    # ── Verre à eau — gamme ──────────────────────────────────────────────────
    {
        "parent_sku": "VER-EAU",
        "parent_name": "Verre à eau",
        "category": "verres",
        "price_per_day_cents": 30,
        "children": [
            {"sku": "VER-EAU-CLA", "label": "Classique", "gamme": "classique", "price_per_day_cents": 30},
            {"sku": "VER-EAU-ELG", "label": "Élégance",  "gamme": "elegance",  "price_per_day_cents": 35},
            {"sku": "VER-EAU-OPN", "label": "Open'Up",   "gamme": "open_up",   "price_per_day_cents": 90},
        ],
    },
    # ── Verre à vin rouge — gamme ────────────────────────────────────────────
    {
        "parent_sku": "VER-VR",
        "parent_name": "Verre à vin rouge",
        "category": "verres",
        "price_per_day_cents": 30,
        "children": [
            {"sku": "VER-VR-CLA", "label": "Classique", "gamme": "classique", "price_per_day_cents": 30},
            {"sku": "VER-VR-ELG", "label": "Élégance",  "gamme": "elegance",  "price_per_day_cents": 35},
            {"sku": "VER-VR-OPN", "label": "Open'Up",   "gamme": "open_up",   "price_per_day_cents": 90},
        ],
    },
    # ── Verre à vin blanc — gamme ────────────────────────────────────────────
    {
        "parent_sku": "VER-VB",
        "parent_name": "Verre à vin blanc",
        "category": "verres",
        "price_per_day_cents": 30,
        "children": [
            {"sku": "VER-VB-CLA", "label": "Classique", "gamme": "classique", "price_per_day_cents": 30},
            {"sku": "VER-VB-ELG", "label": "Élégance",  "gamme": "elegance",  "price_per_day_cents": 35},
            {"sku": "VER-VB-OPN", "label": "Open'Up",   "gamme": "open_up",   "price_per_day_cents": 90},
        ],
    },
    # ── Flûte à champagne — gamme ────────────────────────────────────────────
    {
        "parent_sku": "VER-FLU",
        "parent_name": "Flûte à champagne",
        "category": "verres",
        "price_per_day_cents": 30,
        "children": [
            {"sku": "VER-FLU-CLA", "label": "Classique", "gamme": "classique", "price_per_day_cents": 30},
            {"sku": "VER-FLU-ELG", "label": "Élégance",  "gamme": "elegance",  "price_per_day_cents": 35},
            {"sku": "VER-FLU-OPN", "label": "Open'Up",   "gamme": "open_up",   "price_per_day_cents": 90},
        ],
    },
    # ── Verre à soft — gamme ─────────────────────────────────────────────────
    {
        "parent_sku": "VER-SOFT",
        "parent_name": "Verre à soft",
        "category": "verres",
        "price_per_day_cents": 35,
        "children": [
            {"sku": "VER-SOFT-ELG", "label": "Élégance", "gamme": "elegance", "price_per_day_cents": 35},
        ],
    },
    # ── Assiette ronde classique — taille ────────────────────────────────────
    {
        "parent_sku": "ASS-RND-CLA",
        "parent_name": "Assiette ronde classique",
        "category": "assiettes",
        "price_per_day_cents": 30,
        "children": [
            {"sku": "ASS-RND-CLA-16", "label": "16cm",    "size": "16cm",    "price_per_day_cents": 30},
            {"sku": "ASS-RND-CLA-21", "label": "21cm",    "size": "21cm",    "price_per_day_cents": 30},
            {"sku": "ASS-CRS-CLA-22", "label": "22,5cm",  "size": "22.5cm",  "price_per_day_cents": 30},
            {"sku": "ASS-RND-CLA-26", "label": "26cm",    "size": "26cm",    "price_per_day_cents": 30},
            {"sku": "ASS-RND-CLA-30", "label": "30,5cm",  "size": "30.5cm",  "price_per_day_cents": 42},
        ],
    },
    # ── Assiette carrée élégance — taille ────────────────────────────────────
    {
        "parent_sku": "ASS-CAR-ELG",
        "parent_name": "Assiette carrée élégance",
        "category": "assiettes",
        "price_per_day_cents": 36,
        "children": [
            {"sku": "ASS-CAR-ELG-23",     "label": "23cm plate",  "size": "23cm"},
            {"sku": "ASS-CAR-CRS-ELG-23", "label": "23cm creuse", "size": "23cm-creuse"},
            {"sku": "ASS-CAR-ELG-27",     "label": "27cm",        "size": "27cm"},
        ],
    },
    # ── Assiette ronde vintage — taille ─────────────────────────────────────
    {
        "parent_sku": "ASS-RND-VIN",
        "parent_name": "Assiette ronde vintage",
        "category": "assiettes",
        "price_per_day_cents": 60,
        "children": [
            {"sku": "ASS-RND-VIN-16", "label": "16cm", "size": "16cm", "price_per_day_cents": 60},
            {"sku": "ASS-CRS-VIN-22", "label": "22cm creuse", "size": "22cm", "price_per_day_cents": 60},
            {"sku": "ASS-RND-VIN-27", "label": "27cm", "size": "27cm", "price_per_day_cents": 78},
        ],
    },
]


# ── Helpers DB ────────────────────────────────────────────────────────────────

def _get_product_by_sku(db: Session, sku: str) -> dict | None:
    row = db.execute(
        text("SELECT id, sku, name, stock_quantity, available_quantity "
             "FROM products WHERE sku = :sku AND tenant_id = :tid"),
        {"sku": sku, "tid": TENANT_ID},
    ).fetchone()
    return dict(row._mapping) if row else None


def _create_parent(db: Session, fam: dict, total_stock: int, total_avail: int) -> int:
    now = _now()
    row = db.execute(
        text("""
            INSERT INTO products
                (name, sku, category, price_per_day, deposit_amount, condition,
                 cleaning_fee, stock_quantity, available_quantity,
                 requires_advance_booking_days, tva_rate,
                 tenant_id, is_active, created_at, updated_at)
            VALUES
                (:name, :sku, :cat, :ppd, 0, 'bon',
                 0, :stock, :avail,
                 0, 0.2,
                 :tid, true, :now, :now)
            RETURNING id
        """),
        {
            "name": fam["parent_name"], "sku": fam["parent_sku"],
            "cat": fam["category"],    "ppd": fam["price_per_day"],
            "stock": total_stock,      "avail": total_avail,
            "tid": TENANT_ID,          "now": now,
        },
    )
    return row.fetchone().id


def _variant_exists(db: Session, parent_id: int, label: str) -> bool:
    row = db.execute(
        text("SELECT id FROM product_variants "
             "WHERE product_id = :pid AND label = :lbl AND tenant_id = :tid"),
        {"pid": parent_id, "lbl": label, "tid": TENANT_ID},
    ).fetchone()
    return row is not None


def _create_variant(db: Session, parent_id: int, child: dict,
                    stock: int, avail: int) -> int:
    now = _now()
    row = db.execute(
        text("""
            INSERT INTO product_variants
                (product_id, color, size, gamme, label, price_per_day,
                 sku, stock_quantity, available_quantity,
                 tenant_id, is_active, created_at, updated_at)
            VALUES
                (:pid, :color, :size, :gamme, :label, :ppd,
                 :sku, :stock, :avail,
                 :tid, true, :now, :now)
            RETURNING id
        """),
        {
            "pid":   parent_id,
            "color": child.get("color"),
            "size":  child.get("size"),
            "gamme": child.get("gamme"),
            "label": child["label"],
            "ppd":   child.get("price_per_day"),
            "sku":   child["sku"] + "-V",   # suffixe -V pour éviter conflit SKU
            "stock": stock,
            "avail": avail,
            "tid":   TENANT_ID,
            "now":   now,
        },
    )
    return row.fetchone().id


def _update_references(db: Session, old_pid: int, new_pid: int, vid: int) -> None:
    """Réaffecte reservation_lines, movement_items et bundle_items."""
    for table, id_col in [
        ("reservation_lines", "product_id"),
        ("movement_items",    "product_id"),
    ]:
        r = db.execute(
            text(f"UPDATE {table} SET {id_col} = :new, variant_id = :vid "
                 f"WHERE {id_col} = :old AND tenant_id = :tid"),
            {"new": new_pid, "vid": vid, "old": old_pid, "tid": TENANT_ID},
        )
        if r.rowcount:
            logger.info("    %s : %d lignes mises à jour", table, r.rowcount)

    # bundle_items n'a pas de variant_id — juste réaffecter le product_id
    r = db.execute(
        text("UPDATE bundle_items SET product_id = :new "
             "WHERE product_id = :old"),
        {"new": new_pid, "old": old_pid},
    )
    if r.rowcount:
        logger.info("    bundle_items : %d lignes mises à jour", r.rowcount)


def _soft_delete(db: Session, product_id: int) -> None:
    db.execute(
        text("UPDATE products SET is_active = false, updated_at = :now "
             "WHERE id = :id AND tenant_id = :tid"),
        {"id": product_id, "tid": TENANT_ID, "now": _now()},
    )


# ── Traitement d'une famille ──────────────────────────────────────────────────

def _migrate_family(db: Session, fam: dict) -> dict:
    """Migre une famille. Retourne un dict de stats."""
    parent_sku = fam["parent_sku"]
    stats = {"parent": parent_sku, "created": 0, "skipped": 0, "not_found": 0}

    logger.info("── Famille : %s ──────────────────────────────────", parent_sku)

    # Calcul du stock total depuis les enfants existants
    total_stock = total_avail = 0
    for child in fam["children"]:
        prod = _get_product_by_sku(db, child["sku"])
        if prod:
            total_stock += prod["stock_quantity"]
            total_avail += prod["available_quantity"]

    # Récupérer ou créer le parent
    parent = _get_product_by_sku(db, parent_sku)
    if parent:
        parent_id = parent["id"]
        logger.info("  ✓ Parent existant id=%d", parent_id)
    else:
        parent_id = _create_parent(db, fam, total_stock, total_avail)
        logger.info("  + Parent créé id=%d (stock=%d, avail=%d)", parent_id, total_stock, total_avail)

    # Créer les variantes depuis les produits enfants
    for child in fam["children"]:
        child_sku = child["sku"]

        if _variant_exists(db, parent_id, child["label"]):
            logger.info("  ✓ Variante '%s' existe déjà → skip", child["label"])
            stats["skipped"] += 1
            continue

        prod = _get_product_by_sku(db, child_sku)
        if not prod:
            logger.warning("  ⚠ Produit %s introuvable → skip", child_sku)
            stats["not_found"] += 1
            continue

        vid = _create_variant(db, parent_id, child, prod["stock_quantity"], prod["available_quantity"])
        logger.info("  + Variante '%s' créée id=%d (depuis %s)", child["label"], vid, child_sku)
        stats["created"] += 1

        # Réaffecter les références et soft-delete
        _update_references(db, prod["id"], parent_id, vid)
        _soft_delete(db, prod["id"])
        logger.info("  → Produit %s (id=%d) soft-deleted", child_sku, prod["id"])

    return stats


# ── Point d'entrée ────────────────────────────────────────────────────────────

def run_migration(db: Session) -> None:
    families = FAMILIES
    if ONLY_FAMILY:
        families = [f for f in FAMILIES if f["parent_sku"] == ONLY_FAMILY]
        if not families:
            logger.error("Famille '%s' introuvable. SKUs disponibles : %s",
                         ONLY_FAMILY, [f["parent_sku"] for f in FAMILIES])
            sys.exit(1)

    all_stats = [_migrate_family(db, fam) for fam in families]

    total_created = sum(s["created"] for s in all_stats)
    total_skipped = sum(s["skipped"] for s in all_stats)
    total_missing = sum(s["not_found"] for s in all_stats)
    logger.info("")
    logger.info("══ Résumé ══════════════════════════════════════════════")
    logger.info("  Variantes créées  : %d", total_created)
    logger.info("  Déjà présentes    : %d", total_skipped)
    logger.info("  Produits manquants: %d", total_missing)
    logger.info("════════════════════════════════════════════════════════")


def main() -> None:
    if DRY_RUN:
        logger.info("=== MODE DRY-RUN (aucune écriture) ===")

    db = SessionLocal()
    try:
        run_migration(db)
        if DRY_RUN:
            db.rollback()
            logger.info("=== DRY-RUN : rollback effectué ===")
        else:
            db.commit()
            logger.info("=== Migration terminée avec succès ===")
    except Exception:
        db.rollback()
        logger.exception("=== ERREUR : rollback effectué ===")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
