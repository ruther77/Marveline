"""Persistance du fichier source d'un import ETL (PDF/XLSX/HEIC).

Responsabilité unique : copier un fichier source vers `uploads/etl/{id}.ext`
et retourner le chemin relatif à persister dans `EtlImport.fichier_path`.

Utilisé par :
  - `app/api/v1/endpoints/admin/etl_imports.py::upload_facture` (upload frontend)
  - `scripts/{taiyat,ethan,eurociel,gnanam}_bulk_integrate.py` (intégration bulk)
  - `scripts/backfill_etl_pdfs.py` (rattrapage des imports historiques)

Formats supportés (extensions) : .pdf, .xlsx, .heic, .jpg, .jpeg, .png.
"""
from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from typing import Optional, Union

from app.core.config import settings

logger = logging.getLogger(__name__)

# Extensions acceptées comme source ETL
_ACCEPTED_EXTENSIONS: frozenset[str] = frozenset({
    ".pdf", ".xlsx", ".heic", ".jpg", ".jpeg", ".png",
})


def resolve_uploads_base() -> str:
    """Résout le répertoire uploads absolu (même logique que main.py).

    Crée le dossier s'il n'existe pas. En cas d'erreur de permission sur
    `settings.UPLOAD_DIR`, retombe sur `./uploads`.
    """
    base = settings.UPLOAD_DIR or "uploads"
    if not os.path.isabs(base):
        base = os.path.abspath(base)
    try:
        os.makedirs(base, exist_ok=True)
    except PermissionError:
        base = os.path.abspath("uploads")
        os.makedirs(base, exist_ok=True)
    return base


def get_etl_upload_dir() -> str:
    """Répertoire persistant pour les fichiers source ETL : `uploads/etl/`."""
    etl_dir = os.path.join(resolve_uploads_base(), "etl")
    os.makedirs(etl_dir, exist_ok=True)
    return etl_dir


def persist_etl_source(
    import_id: int,
    source: Union[str, Path, bytes],
    source_filename: Optional[str] = None,
) -> Optional[str]:
    """Persiste le fichier source d'un import dans `uploads/etl/{id}.ext`.

    Args:
        import_id: ID de l'EtlImport (détermine le nom de destination).
        source: Chemin du fichier source (str/Path) OU bytes à écrire.
        source_filename: Nom original avec extension (requis si source=bytes,
            sinon déduit du chemin).

    Returns:
        Chemin relatif à `uploads/` (ex: "etl/42.pdf") à stocker dans
        `EtlImport.fichier_path`, ou None si l'extension n'est pas supportée.
    """
    # Déterminer l'extension depuis le nom de fichier ou le chemin
    if isinstance(source, bytes):
        if not source_filename:
            logger.warning("persist_etl_source(bytes) requires source_filename")
            return None
        ext = Path(source_filename).suffix.lower()
    else:
        src_path = Path(source)
        ext = src_path.suffix.lower()
        if source_filename:
            # L'appelant peut fournir un nom différent (ex: hash → nom original)
            ext = Path(source_filename).suffix.lower() or ext

    if ext not in _ACCEPTED_EXTENSIONS:
        logger.warning(
            "persist_etl_source: extension %r non supportée pour import %d "
            "(filename=%r)", ext, import_id, source_filename,
        )
        return None

    etl_dir = get_etl_upload_dir()
    dest_filename = f"{import_id}{ext}"
    dest_path = os.path.join(etl_dir, dest_filename)

    if isinstance(source, bytes):
        with open(dest_path, "wb") as f:
            f.write(source)
    else:
        if not Path(source).is_file():
            logger.warning(
                "persist_etl_source: fichier source introuvable %r (import %d)",
                str(source), import_id,
            )
            return None
        shutil.copyfile(str(source), dest_path)

    relative_path = f"etl/{dest_filename}"
    logger.info(
        "persist_etl_source: import_id=%d → %s (%d bytes)",
        import_id, relative_path, os.path.getsize(dest_path),
    )
    return relative_path
