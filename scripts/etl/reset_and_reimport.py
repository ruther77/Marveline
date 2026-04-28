"""Script reset + reimport catalogue alimentaire.

Supprime toutes les données catalogue (étape optionnelle) puis relance
le pipeline ETL sur un dossier de fichiers fournisseurs.

Ordre de suppression (FK dépendances) :
    1. epicerie_produits  (FK → catalogue_produits)
    2. etl_conflicts      (FK → catalogue_produits + etl_imports)
    3. catalogue_produits
    4. etl_imports

Usage :
    # Reset + reimport synchrone (sans Celery)
    docker compose exec api python scripts/etl/reset_and_reimport.py \\
        --dossier /data/metro/ --fournisseur metro --fournisseur-id 1 --sync

    # Dry-run (affiche les fichiers sans rien modifier)
    python scripts/etl/reset_and_reimport.py --dossier /data/ --dry-run

    # Sans reset (reimport additionnel)
    python scripts/etl/reset_and_reimport.py \\
        --dossier /data/ --fournisseur metro --no-reset

Références :
    ADR-08 : pipeline ETL
    ADR-15 : etl_import_id FK SET NULL dans etl_conflicts
"""
import argparse
import asyncio
import dataclasses
import glob
import logging
import os
import sys
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

logger = logging.getLogger(__name__)

# Ordre de suppression respectant les FK.
# epicerie_produits est intentionnellement ABSENT : le sync fait un upsert
# des désignations et ne recrée pas les données opérationnelles (stock, ventes).
_RESET_TABLES = [
    "etl_conflicts",
    "catalogue_produits",
    "etl_imports",
]

_PARSERS: dict[str, str] = {
    "metro": "scripts.etl.parsers.metro",
    "taiyat": "scripts.etl.parsers.taiyat",
}


# ── Reset ──────────────────────────────────────────────────────────────────────


async def reset_catalogue(db) -> None:
    """Vide les tables catalogue dans l'ordre FK (TRUNCATE CASCADE risqué en prod).

    Utilise DELETE FROM pour rester compatible avec les contraintes FK
    WITHOUT CASCADE et éviter les suppressions involontaires sur d'autres tables.
    """
    from sqlalchemy import text

    for table in _RESET_TABLES:
        result = await db.execute(text(f"DELETE FROM {table}"))  # noqa: S608
        logger.info("DELETE %s : %d lignes supprimées", table, result.rowcount)


# ── Parsers ────────────────────────────────────────────────────────────────────


def _load_parser_module(fournisseur: str):
    """Charge dynamiquement le module parser du fournisseur."""
    if fournisseur not in _PARSERS:
        known = ", ".join(sorted(_PARSERS))
        logger.error("Fournisseur inconnu : %r. Disponibles : %s", fournisseur, known)
        sys.exit(1)
    import importlib

    return importlib.import_module(_PARSERS[fournisseur])


def _collect_fichiers(dossier: str) -> list[str]:
    """Retourne la liste triée des fichiers dans le dossier (non récursif)."""
    pattern = os.path.join(dossier, "*")
    return sorted(f for f in glob.glob(pattern) if os.path.isfile(f))


# ── Import synchrone (sans Celery) ────────────────────────────────────────────


async def _run_sync_import(
    fichier: str,
    fournisseur: str,
    fournisseur_id: Optional[int],
    parser_module,
) -> None:
    """Parse + exécute run_import() directement (contourne Celery)."""
    from app.core.database import AsyncSessionLocal
    from app.models.catalogue.etl_import import EtlImport
    from app.repositories.catalogue.etl_import import AsyncEtlImportRepository
    from app.services.catalogue.etl_import_service import run_import

    lignes = parser_module.parse(fichier)
    logger.info("Fichier %s : %d lignes parsées", fichier, len(lignes))

    async with AsyncSessionLocal() as db:
        repo = AsyncEtlImportRepository(db)
        import_obj = EtlImport(
            fournisseur_id=fournisseur_id,
            fichier_source=fichier,
            statut="PENDING",
        )
        created = await repo.create(import_obj)
        await db.commit()
        etl_import_id = created.id

    async with AsyncSessionLocal() as db:
        await run_import(db, lignes, etl_import_id)
        await db.commit()
        refreshed = await db.get(EtlImport, etl_import_id)
        if refreshed:
            logger.info(
                "Import %d terminé : statut=%s ok=%d conflit=%d erreur=%d",
                etl_import_id,
                refreshed.statut,
                refreshed.nb_lignes_ok or 0,
                refreshed.nb_lignes_conflit or 0,
                refreshed.nb_lignes_erreur or 0,
            )


# ── Import via Celery ──────────────────────────────────────────────────────────


async def _run_celery_import(
    fichier: str,
    fournisseur_id: Optional[int],
    parser_module,
) -> int:
    """Parse + crée EtlImport + enqueue Celery task."""
    from scripts.etl.import_pipeline import run_pipeline

    lignes = parser_module.parse(fichier)
    logger.info("Fichier %s : %d lignes parsées → enqueue Celery", fichier, len(lignes))
    etl_import_id = await run_pipeline(
        lignes=lignes,
        fournisseur_id=fournisseur_id,
        fichier_source=fichier,
    )
    return etl_import_id


# ── Orchestration principale ───────────────────────────────────────────────────


async def run_reset_and_reimport(
    dossier: str,
    fournisseur: str,
    fournisseur_id: Optional[int],
    do_reset: bool,
    sync: bool,
    dry_run: bool,
) -> None:
    """Orchestration complète reset + reimport.

    Args:
        dossier: Dossier contenant les fichiers à importer.
        fournisseur: Identifiant du parser (ex: 'metro').
        fournisseur_id: FK fournisseurs_alim.id (nullable).
        do_reset: Si True, supprime le catalogue avant import.
        sync: Si True, exécute run_import() directement (sans Celery).
        dry_run: Si True, liste les fichiers sans rien exécuter.
    """
    fichiers = _collect_fichiers(dossier)
    if not fichiers:
        logger.warning("Aucun fichier trouvé dans %s", dossier)
        return

    logger.info("%d fichiers trouvés dans %s", len(fichiers), dossier)
    for f in fichiers:
        logger.info("  %s", f)

    if dry_run:
        logger.info("Dry-run : aucune modification effectuée.")
        return

    parser_module = _load_parser_module(fournisseur)

    if do_reset:
        from app.core.database import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            await reset_catalogue(db)
            await db.commit()
        logger.info("Reset catalogue terminé.")

    for fichier in fichiers:
        if sync:
            await _run_sync_import(fichier, fournisseur, fournisseur_id, parser_module)
        else:
            etl_import_id = await _run_celery_import(fichier, fournisseur_id, parser_module)
            logger.info("Enqueued etl_import_id=%d pour %s", etl_import_id, fichier)


# ── CLI ────────────────────────────────────────────────────────────────────────


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Reset catalogue + reimport ETL depuis un dossier de fichiers.",
    )
    p.add_argument(
        "--dossier",
        required=True,
        help="Dossier contenant les fichiers à importer.",
    )
    p.add_argument(
        "--fournisseur",
        default="metro",
        help="Identifiant du parser fournisseur (défaut: metro).",
    )
    p.add_argument(
        "--fournisseur-id",
        type=int,
        default=None,
        dest="fournisseur_id",
        help="FK vers fournisseurs_alim.id (optionnel).",
    )
    p.add_argument(
        "--no-reset",
        action="store_true",
        help="Ne pas vider le catalogue avant import (import additionnel).",
    )
    p.add_argument(
        "--sync",
        action="store_true",
        help="Exécuter run_import() directement sans Celery.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help="Lister les fichiers sans rien modifier.",
    )
    return p


def main() -> None:
    """Point d'entrée CLI."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    args = _build_parser().parse_args()
    asyncio.run(
        run_reset_and_reimport(
            dossier=args.dossier,
            fournisseur=args.fournisseur,
            fournisseur_id=args.fournisseur_id,
            do_reset=not args.no_reset,
            sync=args.sync,
            dry_run=args.dry_run,
        )
    )


if __name__ == "__main__":
    main()
