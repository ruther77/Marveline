"""Import OpenFoodFacts France → enrichissement EAN catalogue + PREVIEW.

Source : dump public OFF France (CSV gzip, ~350 MB compressé, ~200k produits
alimentaires référencés en France). Téléchargé depuis
https://static.openfoodfacts.org/data/fr.openfoodfacts.org.products.csv.gz

Stratégie :

  1. Download + streaming parse (n'indexe que France + product_name non vide)
  2. Index mémoire `normalized_designation → [{ean, brand, quantity, ...}]`
  3. Enrichir CatalogueProduit sans EAN par match norm exact
  4. Enrichir EtlImport PREVIEW lignes sans EAN (idem + trace auto_applied_fields)

Le match n'applique l'EAN que si **un seul candidat OFF** correspond à la norme
(évite les ambiguïtés type "eau" qui matche 500 produits). En cas de pluralité,
on préfère le candidat avec le volume le plus proche (via `quantity` OFF vs
`volume_unitaire_ml` de la ligne).

Idempotent. Re-run sûr.

Usage :
    docker compose exec -T api python -m scripts.import_off_ean_catalogue \\
        [--dry-run] [--skip-download] [--max-preview-matches N]
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import gzip
import re
import sys
import urllib.request
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app.core.database import AsyncSessionLocal as async_session_factory
from app.models.catalogue.catalogue_produit import CatalogueProduit
from app.models.catalogue.etl_import import EtlImport
from app.services.catalogue.etl_deduplication import normalize_designation


OFF_URL = (
    "https://static.openfoodfacts.org/data/"
    "fr.openfoodfacts.org.products.csv.gz"
)
OFF_LOCAL = Path("/tmp/off_fr.csv.gz")

# Tokens "variants" retirés pour élargir le matching. "COCA ZERO" → "COCA",
# "PEPSI DIET" → "PEPSI". Ces variants sont très rarement discriminants côté
# OFF (même produit proposé en plusieurs sous-variantes partageant EAN).
# Symétrique : appliqué côté ligne ETL et côté OFF.
_VARIANT_TOKENS: frozenset[str] = frozenset({
    "zero", "diet", "light", "lite", "max", "premium", "gold", "silver",
    "extra", "original", "original", "classic", "regular",
    "sans", "sucre", "sucres", "sugar", "sugarfree", "nosugar",
    "0", "0%", "low",
})

# Premier token générique à ne JAMAIS indexer en (first_token, vol) :
# risque d'explosion combinatoire et de matchs ambigus (biere 25cl → 10000
# candidats). On exige que le premier token soit discriminant.
_FIRST_TOKEN_STOP: frozenset[str] = frozenset({
    "eau", "lait", "jus", "biere", "biere", "biere",
    "vin", "huile", "vinaigre", "sauce", "pain", "farine",
    "sucre", "sel", "beurre", "creme", "yaourt", "fromage",
    "viande", "poisson", "poulet", "riz", "pates", "pate",
    "cafe", "the", "chocolat", "boisson", "soda",
    "produit", "article",
})


def _strip_variants(norm: str) -> str:
    """Retire les tokens variants d'une désignation normalisée.

    Idempotent. Conserve l'ordre et la casse (lower) des autres tokens.
    """
    if not norm:
        return norm
    kept = [t for t in norm.split() if t not in _VARIANT_TOKENS]
    return " ".join(kept) if kept else norm  # si tout retiré, garder l'original


def _first_significant_token(norm: str) -> Optional[str]:
    """Retourne le premier token discriminant (pas dans stop-list)."""
    if not norm:
        return None
    for tok in norm.split():
        if tok and tok not in _FIRST_TOKEN_STOP and not tok.isdigit():
            return tok
    return None


import unicodedata as _ud

_RE_BRAND_SEP = re.compile(r"[\s\-_/&'.]+")
_RE_NON_ALNUM = re.compile(r"[^A-Z0-9]")


def _brand_keys(brand: Optional[str]) -> set[str]:
    """Génère toutes les clés d'indexation possibles pour une marque.

    Une marque OFF "Coca-Cola" doit être retrouvable depuis les variantes
    saisies côté ligne : "COCA", "COLA", "COCA COLA", "COCACOLA". Inversement,
    une ligne "REDBULL" doit retrouver une marque OFF "Red Bull".

    Stratégie : pour chaque marque on retient :
      - forme upper + sans accents (ASCII) : "COCA COLA"
      - forme sans séparateur : "COCACOLA"
      - chaque token ≥3 caractères : "COCA", "COLA"

    Les ambiguïtés sont filtrées en aval par `_best_candidate` (vol ±5%).
    """
    if not brand:
        return set()
    normalized = _ud.normalize("NFKD", brand).encode("ASCII", "ignore").decode()
    up = normalized.strip().upper()
    if not up:
        return set()
    keys: set[str] = {up}
    nosep = _RE_NON_ALNUM.sub("", up)
    if nosep and nosep != up:
        keys.add(nosep)
    for tok in _RE_BRAND_SEP.split(up):
        if len(tok) >= 3:
            keys.add(tok)
    return keys

# Parse "75cl", "1.5 L", "6 x 33 cL", "500g" → volume en mL si pertinent
_RE_VOL = re.compile(
    r"(?:(\d+)\s*[xX×]\s*)?(\d+(?:[.,]\d+)?)\s*(cl|ml|l|litre|lt)\b",
    re.IGNORECASE,
)


def _parse_quantity_ml(quantity: Optional[str]) -> Optional[int]:
    if not quantity:
        return None
    m = _RE_VOL.search(quantity.replace(",", "."))
    if not m:
        return None
    multi = int(m.group(1)) if m.group(1) else 1
    amt = float(m.group(2))
    unit = m.group(3).lower()
    if unit in {"l", "litre", "lt"}:
        amt *= 1000
    elif unit == "cl":
        amt *= 10
    # ml → inchangé
    return int(multi * amt)


def download_off() -> None:
    if OFF_LOCAL.exists() and OFF_LOCAL.stat().st_size > 10_000_000:
        print(f"→ OFF déjà présent : {OFF_LOCAL} ({OFF_LOCAL.stat().st_size / 1e6:.0f} MB)")
        return
    print(f"→ Téléchargement OFF France ({OFF_URL})...")
    print("  (~350 MB, peut prendre plusieurs minutes)")
    urllib.request.urlretrieve(OFF_URL, OFF_LOCAL)
    print(f"✓ Téléchargé : {OFF_LOCAL.stat().st_size / 1e6:.0f} MB")


def build_off_index(
    skip_download: bool = False,
) -> tuple[
    dict[str, list[dict]],
    dict[tuple[str, int], list[dict]],
    dict[tuple[str, int], list[dict]],
]:
    """Parse OFF et construit trois index complémentaires :

      1. `by_norm[norm]` et `by_norm[strip_variants(norm)]` — match strict
         (symétrique : la variante "coca zero 33cl" devient aussi "coca 33cl")
      2. `by_brand_vol[(BRAND, volume_ml)]` — match souple par marque + volume
      3. `by_token_vol[(first_sig_token, volume_ml)]` — pour produits sans
         marque dans le dict (MOGU, VIMTO, HAWAI...) : le premier token
         significatif du product_name + volume identifiants.

    Les tokens génériques ("eau", "biere", "lait"…) sont exclus du 3e index
    pour éviter des matches ambigus.
    """
    if not skip_download:
        download_off()
    if not OFF_LOCAL.exists():
        raise FileNotFoundError(f"OFF dump introuvable : {OFF_LOCAL}")

    by_norm: dict[str, list[dict]] = {}
    by_brand_vol: dict[tuple[str, int], list[dict]] = {}
    by_token_vol: dict[tuple[str, int], list[dict]] = {}
    scanned = 0
    indexed = 0
    csv.field_size_limit(sys.maxsize)

    with gzip.open(OFF_LOCAL, "rt", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            scanned += 1
            code = (row.get("code") or "").strip()
            # EAN standards : EAN-8 (8), UPC-A (12), EAN-13 (13), ITF-14 (14).
            # OFF contient parfois des codes internes ou corrompus (> 14 digits).
            if not code or not code.isdigit() or not (8 <= len(code) <= 14):
                continue
            product_name = (
                row.get("product_name_fr")
                or row.get("product_name")
                or ""
            ).strip()
            if not product_name:
                continue
            countries = (row.get("countries_tags") or "").lower()
            if "france" not in countries:
                continue
            norm = normalize_designation(product_name)
            if not norm:
                continue
            brand_raw = (row.get("brands") or "").strip()
            brand = brand_raw.split(",")[0].strip().upper() if brand_raw else None
            vol_ml = _parse_quantity_ml(row.get("quantity"))
            entry = {
                "ean": code,
                "designation": product_name,
                "brand": brand,
                "quantity": (row.get("quantity") or "").strip() or None,
                "volume_ml": vol_ml,
            }
            by_norm.setdefault(norm, []).append(entry)
            stripped = _strip_variants(norm)
            if stripped and stripped != norm:
                by_norm.setdefault(stripped, []).append(entry)
            if brand and vol_ml:
                # Indexer sous TOUTES les variantes de clé pour matcher
                # "COCA" ↔ "Coca-Cola", "REDBULL" ↔ "Red Bull", etc.
                for key in _brand_keys(brand):
                    for v in {vol_ml, vol_ml - 1, vol_ml + 1}:
                        by_brand_vol.setdefault((key, v), []).append(entry)
            first_tok = _first_significant_token(norm)
            if first_tok and vol_ml:
                for v in {vol_ml, vol_ml - 1, vol_ml + 1}:
                    by_token_vol.setdefault((first_tok, v), []).append(entry)
            indexed += 1
            if indexed % 100000 == 0:
                print(f"  … {indexed} produits FR indexés (sur {scanned} scannés)")

    print(
        f"→ Index OFF : {len(by_norm)} normes, "
        f"{len(by_brand_vol)} (marque,vol), "
        f"{len(by_token_vol)} (token,vol), "
        f"{indexed} produits FR / {scanned} lignes scannées"
    )
    return by_norm, by_brand_vol, by_token_vol


def _jaccard_tokens(a: str, b: str) -> float:
    ta = set((a or "").split())
    tb = set((b or "").split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _best_candidate(
    candidates: list[dict],
    ligne_volume_ml: Optional[int],
    ligne_norm: Optional[str] = None,
) -> Optional[dict]:
    """Choisit le meilleur candidat OFF pour une ligne.

    Séquence :
      1. Un seul candidat → OK direct.
      2. Filtrer par volume (±5%) si ligne_volume_ml. Un seul survivant → OK.
      3. Si plusieurs volume-matches, départager par Jaccard de désignation
         normalisée (ligne ↔ OFF, sur tokens strippés des variants). On exige
         que le top distance le second de ≥0.15 (sinon coin-toss → None).
      4. Sinon None (ambiguïté).
    """
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    vol_matches = candidates
    if ligne_volume_ml:
        tol = max(5, ligne_volume_ml * 0.05)
        vol_matches = [
            c for c in candidates
            if c.get("volume_ml")
            and abs(c["volume_ml"] - ligne_volume_ml) <= tol
        ]
        if not vol_matches:
            return None
        if len(vol_matches) == 1:
            return vol_matches[0]

    if ligne_norm:
        stripped_line = _strip_variants(ligne_norm)
        scored: list[tuple[float, dict]] = []
        for c in vol_matches:
            cand_norm = normalize_designation(c.get("designation") or "")
            stripped_cand = _strip_variants(cand_norm)
            sim = max(
                _jaccard_tokens(ligne_norm, cand_norm),
                _jaccard_tokens(stripped_line, stripped_cand),
            )
            scored.append((sim, c))
        scored.sort(key=lambda x: x[0], reverse=True)
        if len(scored) >= 1:
            top_sim, top_c = scored[0]
            second_sim = scored[1][0] if len(scored) > 1 else 0.0
            if top_sim >= 0.3 and (top_sim - second_sim) >= 0.15:
                return top_c
    return None


def _try_match(
    by_norm: dict[str, list[dict]],
    by_brand_vol: dict[tuple[str, int], list[dict]],
    by_token_vol: dict[tuple[str, int], list[dict]],
    norm: Optional[str],
    brand: Optional[str],
    vol_ml: Optional[int],
) -> Optional[dict]:
    """Séquence de fallbacks : norm → norm sans variants → (brand,vol) → (token,vol).

    `ligne_norm` sert à désambiguïser quand plusieurs candidats OFF partagent
    brand + volume (cas typique : Coca Zero vs Coca Cherry vs Coca Classic
    tous en 33cL dans le dump OFF).
    """
    # 1. norm exacte
    if norm:
        best = _best_candidate(by_norm.get(norm) or [], vol_ml, ligne_norm=norm)
        if best:
            return best
        # 2. norm sans variants (zéro, diet, light...)
        stripped = _strip_variants(norm)
        if stripped and stripped != norm:
            best = _best_candidate(by_norm.get(stripped) or [], vol_ml, ligne_norm=norm)
            if best:
                return best
    # 3. (marque, vol) — essaie chaque variante de clé
    if brand and vol_ml:
        for key in _brand_keys(brand):
            pool = by_brand_vol.get((key, vol_ml)) or []
            best = _best_candidate(pool, vol_ml, ligne_norm=norm)
            if best:
                return best
    # 4. (first_significant_token, vol)
    if vol_ml and norm:
        tok = _first_significant_token(norm)
        if tok:
            best = _best_candidate(
                by_token_vol.get((tok, vol_ml)) or [], vol_ml, ligne_norm=norm,
            )
            if best:
                return best
    return None


async def enrich_catalogue(
    db, by_norm: dict[str, list[dict]],
    by_brand_vol: dict[tuple[str, int], list[dict]],
    by_token_vol: dict[tuple[str, int], list[dict]],
    dry_run: bool,
) -> int:
    """Passe 1 : remplir `CatalogueProduit.ean` quand vide et match OFF.

    Respecte la contrainte UNIQUE(ean) : un EAN ne peut être assigné qu'à un
    seul produit. On précharge les EAN déjà pris et on track les assignations
    dans cette run pour éviter les collisions.
    """
    # EAN déjà utilisés en base (uniques)
    used_rows = await db.execute(
        select(CatalogueProduit.ean).where(CatalogueProduit.ean.isnot(None))
    )
    used_eans: set[str] = {r[0] for r in used_rows.all() if r[0]}

    rows = await db.execute(
        select(CatalogueProduit).where(CatalogueProduit.ean.is_(None))
    )
    products = list(rows.scalars())
    print(f"→ {len(products)} produits catalogue sans EAN à tenter d'enrichir")
    matched = 0
    skipped_collision = 0
    for prod in products:
        best = _try_match(
            by_norm, by_brand_vol, by_token_vol,
            norm=prod.designation_norm,
            brand=prod.marque,
            vol_ml=prod.volume_unitaire_ml,
        )
        if not best:
            continue
        ean = best["ean"]
        if ean in used_eans:
            skipped_collision += 1
            continue
        used_eans.add(ean)
        prod.ean = ean
        if not prod.marque and best.get("brand"):
            prod.marque = best["brand"]
        matched += 1
    print(
        f"→ {matched} produits catalogue enrichis (EAN via OFF), "
        f"{skipped_collision} skips collision"
    )
    return matched


async def enrich_preview_imports(
    db, by_norm: dict[str, list[dict]],
    by_brand_vol: dict[tuple[str, int], list[dict]],
    by_token_vol: dict[tuple[str, int], list[dict]],
    dry_run: bool, max_matches: Optional[int] = None,
) -> int:
    """Passe 2 : pour chaque ligne PREVIEW sans EAN, match OFF via 4 fallbacks."""
    imports = list((await db.execute(
        select(EtlImport).where(EtlImport.statut.in_(["PREVIEW", "PARTIEL"]))
    )).scalars())
    print(f"→ {len(imports)} imports PREVIEW à enrichir")

    total_matches = 0
    for imp in imports:
        lignes_raw = list(imp.lignes_data or [])
        if not lignes_raw:
            continue
        touched = False
        for l in lignes_raw:
            if not isinstance(l, dict):
                continue
            if l.get("ean"):
                continue
            desig = l.get("designation") or l.get("designation_raw") or ""
            norm = normalize_designation(desig) if desig else None
            best = _try_match(
                by_norm, by_brand_vol, by_token_vol,
                norm=norm,
                brand=l.get("marque"),
                vol_ml=l.get("volume_unitaire_ml"),
            )
            if not best:
                continue
            l["ean"] = best["ean"]
            meta = l.get("auto_applied_fields") or {}
            if not isinstance(meta, dict):
                meta = {}
            meta["ean"] = {
                "source": "off_import",
                "score": 1.0,
                "candidate_id": None,
                "candidate_designation": best["designation"],
            }
            if not l.get("marque") and best.get("brand"):
                l["marque"] = best["brand"]
                meta["marque"] = {
                    "source": "off_import",
                    "score": 1.0,
                    "candidate_id": None,
                    "candidate_designation": best["designation"],
                }
            l["auto_applied_fields"] = meta
            touched = True
            total_matches += 1
            if max_matches is not None and total_matches >= max_matches:
                break
        if touched:
            imp.lignes_data = list(lignes_raw)
            flag_modified(imp, "lignes_data")
        if max_matches is not None and total_matches >= max_matches:
            print("  (max-preview-matches atteint, arrêt)")
            break
    print(f"→ {total_matches} lignes PREVIEW enrichies (EAN via OFF)")
    return total_matches


async def run(dry_run: bool, skip_download: bool, max_matches: Optional[int]) -> None:
    by_norm, by_brand_vol, by_token_vol = build_off_index(skip_download=skip_download)
    if not by_norm:
        print("✗ Index OFF vide, arrêt")
        return
    async with async_session_factory() as db:
        cat_count = await enrich_catalogue(db, by_norm, by_brand_vol, by_token_vol, dry_run)
        prev_count = await enrich_preview_imports(
            db, by_norm, by_brand_vol, by_token_vol, dry_run, max_matches,
        )
        if dry_run:
            await db.rollback()
            print("\n(DRY-RUN : aucune écriture DB)")
            return
        await db.commit()
        print(
            f"\n✓ {cat_count} produits catalogue + {prev_count} lignes PREVIEW "
            "enrichis via OFF France"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--skip-download", action="store_true",
        help="Réutiliser le dump OFF local sans re-télécharger",
    )
    parser.add_argument(
        "--max-preview-matches", type=int, default=None,
        help="Stopper après N lignes PREVIEW matchées (tests)",
    )
    args = parser.parse_args()
    try:
        asyncio.run(run(
            dry_run=args.dry_run,
            skip_download=args.skip_download,
            max_matches=args.max_preview_matches,
        ))
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
