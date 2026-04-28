"""Re-parse TOUS les PDFs TAIYAT en live (sans modifier la DB) et mesure le
taux d'extraction vol/colisage/marque après les fixes parser.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

if "/app" not in sys.path:
    sys.path.insert(0, "/app")

from sqlalchemy import create_engine, text

from scripts.etl.parsers.taiyat.core import parse


def main() -> None:
    eng = create_engine(os.environ["DATABASE_URL"])
    with eng.connect() as c:
        paths = [r[0] for r in c.execute(text(
            "SELECT fichier_path FROM etl_imports "
            "WHERE vendor_code='TAIYAT' AND fichier_path IS NOT NULL"
        )).fetchall()]

    base = Path("/app/uploads")
    total = avec_vol = avec_col = avec_marque = 0
    nb_fichiers = 0
    for p in paths:
        full = base / p
        if not full.exists():
            continue
        try:
            lignes = parse(str(full))
        except Exception as exc:
            print(f"  {p}: ERREUR {exc}")
            continue
        nb_fichiers += 1
        for l in lignes:
            total += 1
            if l.volume_unitaire_ml:
                avec_vol += 1
            if l.colisage and l.colisage > 1:
                avec_col += 1
            if l.marque:
                avec_marque += 1

    print(
        f"TAIYAT re-parse {nb_fichiers} PDFs : {total} lignes · "
        f"vol={avec_vol} ({100*avec_vol/total:.0f}%) · "
        f"colis={avec_col} ({100*avec_col/total:.0f}%) · "
        f"marque={avec_marque} ({100*avec_marque/total:.0f}%)"
    )


if __name__ == "__main__":
    main()
