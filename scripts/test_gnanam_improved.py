"""Test rapide du parser GNANAM amélioré sur 5 HEIC."""
from pathlib import Path
from scripts.etl.parsers.gnanam import parse_with_facture_metrics


def main():
    heic_dir = Path("/tmp/gnanam_heic")
    if not heic_dir.is_dir():
        print(f"Pas de HEIC dans {heic_dir}")
        return

    heics = sorted(heic_dir.glob("*.HEIC"))[:5]
    print(f"Testing {len(heics)} HEIC with improved parser\n")

    ok = rejected = 0
    total_chars = total_lines = 0
    for pdf in heics:
        lignes, metrics = parse_with_facture_metrics(str(pdf))
        err = metrics.get("error")
        alphanum = metrics.get("ocr_char_count", 0)
        qs = metrics.get("quality_score", 0)
        n = len(lignes)
        total_chars += alphanum
        total_lines += n
        if err:
            rejected += 1
            print(f"  ✗ {pdf.name:<20} alphanum={alphanum:<4} lignes={n:<2} qs={qs:<3}  {err[:60]}")
        else:
            ok += 1
            print(f"  ✓ {pdf.name:<20} alphanum={alphanum:<4} lignes={n:<2} qs={qs:<3}")

    print(f"\n{ok}/{len(heics)} OK, {rejected} rejected. Total: {total_chars} alphanum, {total_lines} lignes")


if __name__ == "__main__":
    main()
