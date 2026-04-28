#!/usr/bin/env python3
"""Scinde des PDFs TAIYAT multi-factures en factures individuelles.

Usage:
  python scripts/etl/split_taiyat_pdf.py \
      --input-pdf /path/to/factures.pdf \
      --output-dir /path/to/factures_individuelles

  python scripts/etl/split_taiyat_pdf.py \
      --input-dir /path/to/docs/TAIYAT \
      --output-dir /path/to/docs/TAIYAT/factures_individuelles
"""

from __future__ import annotations

import argparse
import logging
import re
from pathlib import Path
from typing import Optional

try:
    import pdfplumber
    from pypdf import PdfReader, PdfWriter
except ImportError as exc:
    raise ImportError("Dependances requises: pdfplumber et pypdf") from exc

logger = logging.getLogger(__name__)

_RE_FACTURE = re.compile(r"FACTURE\s*N[°O]?\s*(\d+)", re.IGNORECASE)
_RE_PAGE = re.compile(r"Page\s*(\d+)\s*/\s*(\d+)", re.IGNORECASE)
_RE_DATE = re.compile(r"\b(\d{2}/\d{2}/\d{4})\b")


def _client_hint_from_filename(pdf_path: Path) -> str:
    name = pdf_path.name.upper()
    if "NOUTAM" in name:
        return "NOUTAM"
    if "INCONTOURNABLE" in name:
        return "INCONTOURNABLE"
    return "INCONNU"


def detect_invoices(pdf_path: Path) -> list[dict]:
    """Detecte les bornes de factures dans un PDF multi-pages."""
    invoices: list[dict] = []
    client_hint = _client_hint_from_filename(pdf_path)

    with pdfplumber.open(pdf_path) as pdf:
        current_invoice: Optional[dict] = None

        for page_idx, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            facture_match = _RE_FACTURE.search(text)
            page_match = _RE_PAGE.search(text)
            date_match = _RE_DATE.search(text)

            if not facture_match or not page_match:
                continue

            facture_num = facture_match.group(1)
            page_num = int(page_match.group(1))
            total_pages = int(page_match.group(2))

            if page_num != 1:
                continue

            if current_invoice is not None:
                invoices.append(current_invoice)

            current_invoice = {
                "facture_num": facture_num,
                "date": date_match.group(1) if date_match else None,
                "client": client_hint,
                "start_page": page_idx,
                "end_page": page_idx + total_pages - 1,
                "total_pages": total_pages,
            }

        if current_invoice is not None:
            invoices.append(current_invoice)

    return invoices


def split_pdf(pdf_path: Path, invoices: list[dict], output_dir: Path) -> list[Path]:
    """Genere un PDF par facture."""
    reader = PdfReader(str(pdf_path))
    outputs: list[Path] = []

    for inv in invoices:
        writer = PdfWriter()
        for page_idx in range(inv["start_page"], inv["end_page"] + 1):
            if 0 <= page_idx < len(reader.pages):
                writer.add_page(reader.pages[page_idx])

        date_part = (inv["date"] or "nodate").replace("/", "")
        filename = f"TAIYAT_{inv['client']}_{inv['facture_num']}_{date_part}.pdf"
        out_path = output_dir / filename

        with out_path.open("wb") as fh:
            writer.write(fh)

        outputs.append(out_path)

    return outputs


def process_pdf(pdf_path: Path, output_dir: Path) -> tuple[int, int]:
    invoices = detect_invoices(pdf_path)
    if not invoices:
        logger.warning("Aucune facture detectee dans %s", pdf_path.name)
        return 0, 0

    outputs = split_pdf(pdf_path, invoices, output_dir)
    total_pages = sum(inv["total_pages"] for inv in invoices)
    logger.info("%s -> %d factures (%d pages)", pdf_path.name, len(outputs), total_pages)
    return len(outputs), total_pages


def process_directory(input_dir: Path, output_dir: Path) -> tuple[int, int, int]:
    """Traite tous les PDFs de factures d'un dossier TAIYAT."""
    pdf_files = sorted(
        f for f in input_dir.glob("*.pdf") if f.is_file() and "factures" in f.name.lower()
    )

    total_files = 0
    total_invoices = 0
    total_pages = 0

    for pdf_path in pdf_files:
        total_files += 1
        inv_count, page_count = process_pdf(pdf_path, output_dir)
        total_invoices += inv_count
        total_pages += page_count

    return total_files, total_invoices, total_pages


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Split PDFs TAIYAT multi-factures")
    parser.add_argument("--input-pdf", help="Chemin d'un PDF multi-factures")
    parser.add_argument("--input-dir", help="Dossier contenant les PDFs multi-factures")
    parser.add_argument("--output-dir", required=True, help="Dossier de sortie")
    parser.add_argument("--log-level", default="INFO", help="DEBUG, INFO, WARNING...")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    logging.basicConfig(level=args.log_level.upper(), format="%(asctime)s %(levelname)s %(message)s")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if bool(args.input_pdf) == bool(args.input_dir):
        raise SystemExit("Fournir exactement un des deux arguments: --input-pdf ou --input-dir")

    if args.input_pdf:
        pdf_path = Path(args.input_pdf)
        inv_count, page_count = process_pdf(pdf_path, output_dir)
        logger.info("Termine: %d factures, %d pages", inv_count, page_count)
        return

    input_dir = Path(args.input_dir)
    files, inv_count, page_count = process_directory(input_dir, output_dir)
    logger.info(
        "Termine: %d PDFs traites, %d factures extraites, %d pages",
        files,
        inv_count,
        page_count,
    )


if __name__ == "__main__":
    main()
