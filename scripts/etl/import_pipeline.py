"""CLI pipeline ETL catalogue alimentaire (ADR-08).

Orchestrateur thin-wrapper : crée l'EtlImport PENDING en DB, sérialise les
lignes parsées et délègue le traitement à la Celery task run_etl_import.

Usage (Docker) :
    docker compose exec api python scripts/etl/import_pipeline.py \\
        --fichier /data/metro_2026-03-10.csv \\
        --fournisseur-id 1

Usage (local) :
    python3 scripts/etl/import_pipeline.py --fichier path/to/file.csv

Références :
    ADR-08 : pipeline ETL, rôle du CLI orchestrateur
    etl_tasks.py : Celery task qui exécute le pipeline
    etl_import_service.py : logique métier (run_import)
"""
import argparse
import asyncio
import dataclasses
import logging
import sys
import os
from typing import Optional

# Dossier racine au path pour les imports app.*
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalogue.etl_import import EtlImport
from app.repositories.catalogue.etl_import import AsyncEtlImportRepository
from app.etl_types import FactureMetadata, LigneParsee

logger = logging.getLogger(__name__)


# ── Helpers (testables — reçoivent une session externe) ──────────────────────


async def _create_import_record(
    db: AsyncSession,
    fournisseur_id: Optional[int],
    fichier_source: Optional[str],
) -> int:
    """Crée un EtlImport PENDING en DB et retourne son id.

    Args:
        db: AsyncSession fournie par l'appelant.
        fournisseur_id: FK vers fournisseurs_alim.id (nullable).
        fichier_source: Nom ou chemin du fichier importé (pour traçabilité).

    Returns:
        ID de l'EtlImport créé.
    """
    repo = AsyncEtlImportRepository(db)
    obj = EtlImport(
        fournisseur_id=fournisseur_id,
        fichier_source=fichier_source,
        statut="PENDING",
    )
    created = await repo.create(obj)
    return created.id


def enqueue_import(etl_import_id: int, lignes_data: list[dict]) -> None:
    """Envoie la Celery task run_etl_import en async.

    Séparé de run_pipeline pour être patchable dans les tests.

    Args:
        etl_import_id: ID de l'EtlImport PENDING créé en DB.
        lignes_data: Lignes sérialisées (list[dict]) prêtes pour Celery.
    """
    from app.tasks.etl_tasks import run_etl_import

    run_etl_import.delay(etl_import_id, lignes_data)
    logger.info(
        "Task ETL enqueued : etl_import_id=%d, %d lignes",
        etl_import_id,
        len(lignes_data),
    )


# ── Point d'entrée orchestrateur ─────────────────────────────────────────────


async def run_pipeline(
    lignes: list[LigneParsee],
    fournisseur_id: Optional[int] = None,
    fichier_source: Optional[str] = None,
) -> int:
    """Crée l'EtlImport PENDING, commit, et enqueue la Celery task.

    Cette fonction crée sa propre AsyncSession (usage CLI autonome).
    Pour les tests, utiliser _create_import_record + enqueue_import séparément.

    Args:
        lignes: Lignes parsées issues d'un parser fournisseur.
        fournisseur_id: FK fournisseurs_alim.id (nullable).
        fichier_source: Chemin ou nom du fichier source (pour traçabilité).

    Returns:
        etl_import_id de l'EtlImport créé.
    """
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        etl_import_id = await _create_import_record(db, fournisseur_id, fichier_source)
        await db.commit()

    lignes_data = [dataclasses.asdict(l) for l in lignes]
    enqueue_import(etl_import_id, lignes_data)
    return etl_import_id


# ── CLI ───────────────────────────────────────────────────────────────────────

_PARSERS: dict[str, str] = {
    # fournisseur → module parser (Session 6-F+)
    "metro": "scripts.etl.parsers.metro",
    "taiyat": "scripts.etl.parsers.taiyat",
    "ethan": "scripts.etl.parsers.ethan",
    "eurociel": "scripts.etl.parsers.eurociel",
    "gnanam": "scripts.etl.parsers.gnanam",
}


def _load_lignes(fournisseur: str, fichier: str) -> list[LigneParsee]:
    """Charge le parser du fournisseur et parse le fichier.

    Args:
        fournisseur: Identifiant du fournisseur (ex: 'metro').
        fichier: Chemin vers le fichier à parser.

    Returns:
        Liste de LigneParsee issues du parser.

    Raises:
        SystemExit: Si le parser est inconnu ou si le fichier est introuvable.
    """
    if fournisseur not in _PARSERS:
        known = ", ".join(sorted(_PARSERS))
        logger.error("Fournisseur inconnu : %r. Parsers disponibles : %s", fournisseur, known)
        sys.exit(1)

    import importlib
    module = importlib.import_module(_PARSERS[fournisseur])
    lignes: list[LigneParsee] = module.parse(fichier)
    logger.info("Parser %s : %d lignes chargées depuis %s", fournisseur, len(lignes), fichier)
    return lignes


def _load_facture(
    fournisseur: str, fichier: str,
) -> tuple[list[LigneParsee], FactureMetadata]:
    """Charge le parser et parse en mode facture (lignes + metadata ADR-25).

    Args:
        fournisseur: Identifiant du fournisseur (ex: 'metro').
        fichier: Chemin vers le fichier à parser.

    Returns:
        Tuple (lignes, metadata) pour le workflow preview.

    Raises:
        ValueError: Si le parser n'a pas de fonction parse_facture().
    """
    if fournisseur not in _PARSERS:
        known = ", ".join(sorted(_PARSERS))
        raise ValueError(f"Fournisseur inconnu : {fournisseur!r}. Disponibles : {known}")

    import importlib
    module = importlib.import_module(_PARSERS[fournisseur])

    if not hasattr(module, "parse_facture"):
        raise ValueError(
            f"Parser {fournisseur!r} ne supporte pas parse_facture(). "
            f"Utiliser _load_lignes() pour l'import catalogue classique."
        )

    lignes, metadata = module.parse_facture(fichier)
    logger.info(
        "Parser %s (facture) : %d lignes, facture=%s, quality=%s depuis %s",
        fournisseur, len(lignes),
        metadata.numero_facture, metadata.quality_score,
        fichier,
    )
    return lignes, metadata


async def run_pipeline_preview(
    lignes: list[LigneParsee],
    metadata: FactureMetadata,
    fournisseur_id: Optional[int] = None,
    fichier_source: Optional[str] = None,
) -> int:
    """Crée un EtlImport en mode PREVIEW (workflow facture fournisseur ADR-25).

    Parse → persiste metadata → statut PREVIEW. Pas d'import catalogue.
    L'opérateur valide/rejette ensuite via l'API admin.

    Args:
        lignes: Lignes parsées issues de parse_facture().
        metadata: Métadonnées facture extraites par le parser.
        fournisseur_id: FK fournisseurs_alim.id (nullable).
        fichier_source: Chemin ou nom du fichier source.

    Returns:
        etl_import_id de l'EtlImport créé (statut=PREVIEW).
    """
    from app.core.database import AsyncSessionLocal
    from app.services.catalogue.etl_import_service import run_import

    async with AsyncSessionLocal() as db:
        etl_import_id = await _create_import_record(db, fournisseur_id, fichier_source)
        await db.commit()

    # Exécuter run_import en mode preview (synchrone, pas Celery)
    async with AsyncSessionLocal() as db:
        await run_import(
            db, lignes, etl_import_id,
            metadata=metadata,
            preview_mode=True,
        )
        await db.commit()

    logger.info("ETL preview created — etl_import_id=%d", etl_import_id)
    return etl_import_id


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Pipeline ETL catalogue alimentaire — enqueue Celery task (ADR-08)",
    )
    p.add_argument(
        "--fichier",
        required=True,
        help="Chemin vers le fichier fournisseur à importer.",
    )
    p.add_argument(
        "--fournisseur",
        default="metro",
        help="Identifiant du fournisseur (défaut: metro).",
    )
    p.add_argument(
        "--fournisseur-id",
        type=int,
        default=None,
        dest="fournisseur_id",
        help="FK vers fournisseurs_alim.id (optionnel).",
    )
    return p


def main() -> None:
    """Point d'entrée CLI."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    args = _build_parser().parse_args()
    lignes = _load_lignes(args.fournisseur, args.fichier)
    etl_import_id = asyncio.run(
        run_pipeline(
            lignes=lignes,
            fournisseur_id=args.fournisseur_id,
            fichier_source=args.fichier,
        )
    )
    print(f"ETL enqueued — etl_import_id={etl_import_id}")


if __name__ == "__main__":
    main()
