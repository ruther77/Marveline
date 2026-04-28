"""Dry-run : parse tous les PDFs TAIYAT et agrège les métriques.

Usage :
    docker exec -w /app futurproj_api bash -c 'PYTHONPATH=/app python scripts/taiyat_bulk_analyze.py /tmp/taiyat_batch'

Ne touche pas la DB. Produit un rapport JSON + résumé terminal.
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median

from scripts.etl.parsers.taiyat import parse_facture, parse_with_facture_metrics


def _fmt_eur_cts(cts: int | None) -> str:
    if cts is None:
        return "—"
    return f"{cts / 100:,.2f} €"


def analyze(dir_path: str) -> dict:
    pdf_dir = Path(dir_path)
    pdfs = sorted(pdf_dir.glob("*.pdf"))
    print(f"→ Analysing {len(pdfs)} PDFs from {dir_path}")

    per_file: list[dict] = []
    t0 = time.perf_counter()
    errors: list[dict] = []

    for i, pdf in enumerate(pdfs, 1):
        try:
            lignes, metadata = parse_facture(str(pdf))
            _, metrics = parse_with_facture_metrics(str(pdf))

            ean_count = sum(1 for l in lignes if l.ean)
            marque_count = sum(1 for l in lignes if l.marque)
            cat_count = sum(1 for l in lignes if l.categorie_code)

            per_file.append({
                "file": pdf.name,
                "client": metadata.client_name,
                "target_tenant": metadata.target_tenant_id,
                "numero": metadata.numero_facture,
                "date": metadata.date_facture.isoformat() if metadata.date_facture else None,
                "nb_lignes": len(lignes),
                "ht_cts": metadata.montant_ht_total,
                "tva_cts": metadata.montant_tva_total,
                "ttc_cts": metadata.montant_ttc_total,
                "quality": metadata.quality_score,
                "ecart": float(metadata.ecart_reconciliation) if metadata.ecart_reconciliation else 0.0,
                "ean_pct": 100.0 * ean_count / max(len(lignes), 1),
                "marque_pct": 100.0 * marque_count / max(len(lignes), 1),
                "cat_pct": 100.0 * cat_count / max(len(lignes), 1),
                "line_outliers": metrics.get("line_coherence_outlier_count", 0),
                "remise_count": metrics.get("line_count_discount", 0),
                "is_coherent": metrics.get("is_total_coherent", False),
                "tva_rates": sorted(metrics.get("reconciled_ttc_by_rate", {}).keys()),
                "categories": Counter(l.categorie_code for l in lignes if l.categorie_code),
                "marques": Counter(l.marque for l in lignes if l.marque),
            })
        except Exception as exc:
            errors.append({"file": pdf.name, "error": str(exc)[:200]})

        if i % 25 == 0:
            print(f"  [{i}/{len(pdfs)}] parsed, elapsed={time.perf_counter() - t0:.0f}s")

    elapsed = time.perf_counter() - t0
    print(f"✓ Done in {elapsed:.0f}s")

    # ── Agrégation ───────────────────────────────────────────────────────────
    by_client: dict[str, list] = defaultdict(list)
    for r in per_file:
        by_client[r["client"] or "UNKNOWN"].append(r)

    total_ttc = sum(r["ttc_cts"] or 0 for r in per_file)
    total_ht = sum(r["ht_cts"] or 0 for r in per_file)
    total_tva = sum(r["tva_cts"] or 0 for r in per_file)
    total_lignes = sum(r["nb_lignes"] for r in per_file)
    coherent_count = sum(1 for r in per_file if r["is_coherent"])

    qualities = [r["quality"] for r in per_file if r["quality"] is not None]
    ean_pcts = [r["ean_pct"] for r in per_file]
    marque_pcts = [r["marque_pct"] for r in per_file]
    cat_pcts = [r["cat_pct"] for r in per_file]
    outliers_total = sum(r["line_outliers"] for r in per_file)
    remise_total = sum(r["remise_count"] for r in per_file)

    # Catégories globales (top 15)
    cat_global: Counter = Counter()
    for r in per_file:
        cat_global.update(r["categories"])
    marque_global: Counter = Counter()
    for r in per_file:
        marque_global.update(r["marques"])

    # TVA rates distribution
    tva_rates_dist: Counter = Counter()
    for r in per_file:
        for rate in r["tva_rates"]:
            tva_rates_dist[rate] += 1

    # Date range
    dates = [r["date"] for r in per_file if r["date"]]
    date_range = (min(dates), max(dates)) if dates else (None, None)

    # Distribution par client
    client_summary = {}
    for client, rows in by_client.items():
        ttc_client = sum(r["ttc_cts"] or 0 for r in rows)
        lignes_client = sum(r["nb_lignes"] for r in rows)
        client_summary[client] = {
            "factures": len(rows),
            "total_ttc_cts": ttc_client,
            "total_lignes": lignes_client,
            "ligne_moyenne_par_facture": round(lignes_client / len(rows), 1) if rows else 0,
            "ttc_moyen": ttc_client // max(len(rows), 1),
            "target_tenant": rows[0]["target_tenant"] if rows else None,
        }

    # Factures problématiques (qualité < 100 OR incohérence OR outliers)
    problematic = [
        {"file": r["file"], "client": r["client"], "quality": r["quality"],
         "ecart": r["ecart"], "outliers": r["line_outliers"]}
        for r in per_file
        if (r["quality"] or 0) < 100 or not r["is_coherent"] or r["line_outliers"] > 0
    ]

    report = {
        "global": {
            "nb_factures_total": len(pdfs),
            "nb_factures_parsees": len(per_file),
            "nb_erreurs": len(errors),
            "duree_sec": round(elapsed, 1),
            "date_debut": date_range[0],
            "date_fin": date_range[1],
            "nb_lignes_total": total_lignes,
            "ligne_moyenne_par_facture": round(total_lignes / max(len(per_file), 1), 1),
            "total_ht_cts": total_ht,
            "total_tva_cts": total_tva,
            "total_ttc_cts": total_ttc,
            "quality_median": median(qualities) if qualities else None,
            "quality_mean": round(mean(qualities), 1) if qualities else None,
            "quality_100_count": sum(1 for q in qualities if q == 100),
            "coherence_rate_pct": round(100.0 * coherent_count / max(len(per_file), 1), 1),
            "ean_coverage_mean_pct": round(mean(ean_pcts), 1) if ean_pcts else 0,
            "marque_coverage_mean_pct": round(mean(marque_pcts), 1) if marque_pcts else 0,
            "categorie_coverage_mean_pct": round(mean(cat_pcts), 1) if cat_pcts else 0,
            "line_outliers_total": outliers_total,
            "remise_total": remise_total,
        },
        "par_client": client_summary,
        "top_categories": cat_global.most_common(20),
        "top_marques": marque_global.most_common(15),
        "tva_rates_distribution": dict(sorted(tva_rates_dist.items())),
        "factures_problematiques": problematic[:50],
        "nb_problematiques": len(problematic),
        "errors": errors,
    }
    return report


def print_report(r: dict) -> None:
    g = r["global"]
    print()
    print("═" * 72)
    print(f"  TAIYAT — ANALYSE BULK {g['nb_factures_parsees']}/{g['nb_factures_total']} factures")
    print("═" * 72)
    print(f"  Période       : {g['date_debut']} → {g['date_fin']}")
    print(f"  Erreurs parse : {g['nb_erreurs']}")
    print(f"  Durée         : {g['duree_sec']}s")
    print()
    print(f"  Lignes totales         : {g['nb_lignes_total']:,}")
    print(f"  Lignes moyennes/facture: {g['ligne_moyenne_par_facture']}")
    print(f"  Total HT               : {_fmt_eur_cts(g['total_ht_cts'])}")
    print(f"  Total TVA              : {_fmt_eur_cts(g['total_tva_cts'])}")
    print(f"  Total TTC              : {_fmt_eur_cts(g['total_ttc_cts'])}")
    print()
    print(f"  Quality score médian   : {g['quality_median']}")
    print(f"  Quality score moyen    : {g['quality_mean']}")
    print(f"  Factures quality=100   : {g['quality_100_count']}/{g['nb_factures_parsees']}")
    print(f"  Cohérence TTC (declared≈computed) : {g['coherence_rate_pct']}%")
    print(f"  Line outliers totaux   : {g['line_outliers_total']}")
    print(f"  Lignes remise totales  : {g['remise_total']}")
    print()
    print(f"  Couverture EAN moyenne       : {g['ean_coverage_mean_pct']}%")
    print(f"  Couverture marque moyenne    : {g['marque_coverage_mean_pct']}%")
    print(f"  Couverture catégorie moyenne : {g['categorie_coverage_mean_pct']}%")
    print()
    print("─── PAR CLIENT ─────────────────────────────────────────────────────────")
    for client, stats in r["par_client"].items():
        print(f"  {client} (tenant={stats['target_tenant']})")
        print(f"    {stats['factures']} factures · {stats['total_lignes']} lignes "
              f"· moy {stats['ligne_moyenne_par_facture']} lignes/facture")
        print(f"    Total TTC: {_fmt_eur_cts(stats['total_ttc_cts'])} "
              f"· Moyenne/facture: {_fmt_eur_cts(stats['ttc_moyen'])}")
    print()
    print("─── TOP 20 CATÉGORIES ──────────────────────────────────────────────────")
    for code, n in r["top_categories"]:
        print(f"  {code:25s} {n:4d} lignes")
    print()
    print("─── TOP 15 MARQUES ─────────────────────────────────────────────────────")
    for marque, n in r["top_marques"]:
        print(f"  {marque:30s} {n:4d} lignes")
    print()
    print("─── TVA RATES ──────────────────────────────────────────────────────────")
    for rate, count in r["tva_rates_distribution"].items():
        print(f"  {rate}% dans {count} factures")
    print()
    print(f"─── FACTURES PROBLÉMATIQUES : {r['nb_problematiques']} ──────────────")
    for p in r["factures_problematiques"][:10]:
        print(f"  {p['file'][:50]:52s} q={p['quality']} écart={p['ecart']} outliers={p['outliers']}")
    if r["errors"]:
        print()
        print(f"─── ERREURS PARSE : {len(r['errors'])} ────────────────")
        for e in r["errors"][:10]:
            print(f"  {e['file']}: {e['error']}")


if __name__ == "__main__":
    directory = sys.argv[1] if len(sys.argv) > 1 else "/tmp/taiyat_batch"
    report = analyze(directory)
    print_report(report)

    out_path = Path("/tmp/taiyat_bulk_report.json")
    # Convertir Counter en dict et tva_rates list en str
    clean = json.loads(json.dumps(report, default=lambda o: list(o) if isinstance(o, (set,)) else str(o)))
    out_path.write_text(json.dumps(clean, indent=2, ensure_ascii=False, default=str))
    print(f"\n→ Rapport JSON : {out_path}")
