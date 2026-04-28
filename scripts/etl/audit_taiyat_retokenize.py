"""Quick audit : re-tokenize les designations TAIYAT stockées et mesure le
taux d'extraction vol/colisage après les fixes UNIT_TO_ML (poids) + extraction
des paires 'NxM' + unite séparée.

Usage : docker exec -w /app futurproj_api python3 scripts/etl/audit_taiyat_retokenize.py
"""
from __future__ import annotations

import json
import os
import sys

if "/app" not in sys.path:
    sys.path.insert(0, "/app")

from sqlalchemy import create_engine, text

from scripts.etl.parsers._shared.tokenizer import (
    DesigToken,
    classify_token,
    extract_colisage,
    extract_volume_ml,
)


def main() -> None:
    eng = create_engine(os.environ["DATABASE_URL"])
    with eng.connect() as c:
        rows = c.execute(text(
            "SELECT lignes_data FROM etl_imports "
            "WHERE vendor_code='TAIYAT' AND lignes_data IS NOT NULL"
        )).fetchall()

    total = avec_vol = avec_col = 0
    for (raw,) in rows:
        lignes = json.loads(raw) if isinstance(raw, str) else raw or []
        for l in lignes:
            desig = l.get("designation") or ""
            if not desig:
                continue
            total += 1
            tokens = [
                DesigToken(cleaned=w.upper(), raw=w, token_type=classify_token(w))
                for w in desig.split()
            ]
            if extract_volume_ml(tokens):
                avec_vol += 1
            c_col = extract_colisage(tokens)
            if c_col and c_col > 1:
                avec_col += 1

    print(
        f"TAIYAT re-tokenize : {total} lignes · "
        f"vol={avec_vol} ({100*avec_vol/total:.0f}%) · "
        f"colis={avec_col} ({100*avec_col/total:.0f}%)"
    )


if __name__ == "__main__":
    main()
