#!/usr/bin/env python3
"""Diagnostic des PDFs METRO avec écart HT > 5€ (les "BAD").

Usage :
    python scripts/etl/diag_metro_bad.py [--detail] [--pdf NOM.pdf]

    --detail   : afficher la liste des lignes produit et ajustements pour chaque BAD
    --pdf NAME : analyser un seul PDF (nom de fichier, pas chemin complet)

Critères :
    SKIP = total_ht_declared == None ou == 0
    OK   = ecart_ht_abs <= 5.0 (ou total_ht non déclaré)
    BAD  = ecart_ht_abs > 5.0
"""
from __future__ import annotations

import argparse
import sys
import os
import gc
import re
from pathlib import Path
from typing import Optional

# ── PYTHONPATH ─────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

PDF_DIRS = [
    ROOT / "docs" / "METRO" / f"Téléchargement({n})"
    for n in [8, 9, 10, 11, 12, 13]
]

SEUIL_BAD = 5.0


def collect_pdfs() -> list[Path]:
    pdfs = []
    for d in PDF_DIRS:
        if d.exists():
            pdfs.extend(sorted(d.glob("*invoice_cus_copy*.pdf")))
    return pdfs


def run_batch(pdfs: list[Path], detail: bool = False) -> None:
    from scripts.etl.parsers.metro.core import parse_with_facture_metrics

    ok, bad, skip = 0, 0, 0
    bad_cases: list[dict] = []

    for i, pdf in enumerate(pdfs, 1):
        try:
            lignes, m = parse_with_facture_metrics(str(pdf), dedupe_ean=False)
        except Exception as exc:
            print(f"[ERREUR] {pdf.name}: {exc}")
            skip += 1
            continue

        th = m.get("total_ht_declared")
        ecart_abs = m.get("ecart_ht_abs")

        if th is None or th == 0.0:
            skip += 1
            continue

        if ecart_abs is not None and ecart_abs > SEUIL_BAD:
            bad += 1
            bad_cases.append({"pdf": pdf, "lignes": lignes, "metrics": m})
        else:
            ok += 1

        if i % 50 == 0:
            gc.collect()
            print(f"  ... {i}/{len(pdfs)} traités — OK={ok} BAD={bad} SKIP={skip}", flush=True)

    print(f"\n{'='*70}")
    print(f"RÉSULTAT GLOBAL : {len(pdfs)} PDFs — OK={ok}  BAD={bad}  SKIP={skip}")
    print(f"{'='*70}\n")

    if not bad_cases:
        print("Aucun BAD. ")
        return

    # ── Classer les BAD par catégorie ─────────────────────────────────────
    # On essaie de diagnostiquer la cause principale de l'écart
    print(f"{'='*70}")
    print(f"  DÉTAIL DES {bad} PDFs BAD")
    print(f"{'='*70}\n")

    categories: dict[str, list[dict]] = {}

    for case in sorted(bad_cases, key=lambda c: abs(c["metrics"]["ecart_ht"]), reverse=True):
        pdf = case["pdf"]
        m = case["metrics"]
        lignes = case["lignes"]

        th = m["total_ht_declared"]
        reconcilie = m["montant_reconcilie"]
        ecart = m["ecart_ht"]
        ecart_abs = m["ecart_ht_abs"]
        remises_det = m["montant_remises_detectees"]
        remises_app = m["montant_remises_appliquees"]
        suppl_det = m["montant_supplements_detectes"]
        suppl_app = m["montant_supplements_appliques"]
        n_lignes = m["line_count_output"]
        n_all = m["line_count_all"]
        fallback = m.get("fallback_no_ean_count", 0)

        # Catégorisation heuristique
        cat = _categorize(m)
        categories.setdefault(cat, []).append(case)

        # Affichage
        print(f"  [{cat}] {pdf.name}")
        print(f"    TH déclaré={th:.2f}  réconcilié={reconcilie:.2f}  écart={ecart:+.2f}€")
        print(f"    lignes={n_all}→{n_lignes}  remises déct={remises_det:.2f}/app={remises_app:.2f}"
              f"  suppl déct={suppl_det:.2f}/app={suppl_app:.2f}  fallback_no_ean={fallback}")

        if detail:
            _print_detail(case)
        print()

    # ── Synthèse par catégorie ─────────────────────────────────────────────
    print(f"\n{'='*70}")
    print("  SYNTHÈSE PAR CATÉGORIE DE PROBLÈME")
    print(f"{'='*70}")
    for cat, cases in sorted(categories.items(), key=lambda x: -len(x[1])):
        ecarts = [c["metrics"]["ecart_ht_abs"] for c in cases]
        print(f"  {cat} : {len(cases)} PDFs  (écart min={min(ecarts):.2f} max={max(ecarts):.2f})")
    print()


def _categorize(m: dict) -> str:
    """Heuristique de catégorisation de la cause du BAD."""
    th = m["total_ht_declared"]
    reconcilie = m["montant_reconcilie"]
    ecart = m["ecart_ht"]
    ecart_abs = m["ecart_ht_abs"]
    remises_det = m["montant_remises_detectees"]
    remises_app = m["montant_remises_appliquees"]
    suppl_det = m["montant_supplements_detectes"]
    suppl_app = m["montant_supplements_appliques"]
    n_lignes = m["line_count_output"]
    fallback = m.get("fallback_no_ean_count", 0)

    # Supplément non appliqué → écart positif non comblé
    suppl_manquant = suppl_det - suppl_app
    remise_manquante = remises_det - remises_app

    if ecart < 0 and abs(ecart_abs - abs(suppl_det)) < 2.0:
        return "SUPPL_MANQUANT"  # supplément détecté mais pas appliqué (dépasse total)

    if remise_manquante < -1.0:
        return "REMISE_NON_APPLIQUEE"  # remise détectée mais non appliquée

    if suppl_manquant > 1.0:
        return "SUPPL_NON_APPLIQUE"  # supplément non retenu par select_best

    if th is not None and reconcilie < th * 0.5:
        return "LIGNES_MANQUANTES"  # beaucoup de lignes non parsées

    if fallback > 3:
        return "BEAUCOUP_FALLBACK_EAN"

    if ecart > 0:
        return "ECART_POSITIF"  # réconcilié < déclaré → lignes ou remises oubliées
    else:
        return "ECART_NEGATIF"  # réconcilié > déclaré → doublon ou mauvaise ligne


def _print_detail(case: dict) -> None:
    """Affiche les lignes produit et les ajustements candidats d'un BAD."""
    pdf = case["pdf"]
    m = case["metrics"]
    lignes = case["lignes"]

    # Relancer pour récupérer les candidats ajustements (non exposés dans metrics)
    # → on doit relancer le parser avec un hook de debug
    print(f"    --- Lignes produit ({len(lignes)}) ---")
    total_from_lignes = 0.0
    for l in lignes:
        ht_eur = (l.montant_ht_cts or 0) / 100
        total_from_lignes += ht_eur
        ean_s = l.ean or "(no ean)"
        print(f"      {ean_s:15s}  {(l.designation or '')[:30]:30s}  "
              f"qte={l.quantite or '?':>5}  ht={ht_eur:8.2f}€")
    print(f"    Total lignes : {total_from_lignes:.2f}€  (attendu réconcilié={m['montant_reconcilie']:.2f}€)")


def run_single(pdf_name: str, detail: bool = True) -> None:
    """Analyse approfondie d'un seul PDF avec dump détaillé."""
    from scripts.etl.parsers.metro.core import parse_with_facture_metrics

    # Chercher le fichier dans les dossiers
    pdf_path: Optional[Path] = None
    for d in PDF_DIRS:
        candidate = d / pdf_name
        if candidate.exists():
            pdf_path = candidate
            break
    if pdf_path is None:
        # Cherche aussi dans docs/METRO directement
        for d in PDF_DIRS:
            for f in d.glob("*.pdf"):
                if pdf_name in f.name:
                    pdf_path = f
                    break
    if pdf_path is None:
        print(f"PDF introuvable : {pdf_name}")
        sys.exit(1)

    print(f"Analyse : {pdf_path}")
    lignes, m = parse_with_facture_metrics(str(pdf_path), dedupe_ean=False)

    th = m.get("total_ht_declared")
    ecart = m.get("ecart_ht")
    ecart_abs = m.get("ecart_ht_abs")

    print(f"\n{'='*70}")
    print(f"  TH déclaré   : {th}")
    print(f"  Réconcilié   : {m['montant_reconcilie']:.2f}€")
    print(f"  Écart        : {ecart:+.2f}€" if ecart is not None else "  Écart : N/A")
    print(f"  Lignes       : {m['line_count_all']} total → {m['line_count_output']} retenues")
    print(f"  Remises déct : {m['montant_remises_detectees']:.2f}€  appliquées : {m['montant_remises_appliquees']:.2f}€")
    print(f"  Suppl. déct  : {m['montant_supplements_detectes']:.2f}€  appliqués  : {m['montant_supplements_appliques']:.2f}€")
    print(f"  fallback_no_ean : {m.get('fallback_no_ean_count', 0)}")
    print(f"{'='*70}\n")

    # Lignes
    print("LIGNES PRODUIT :")
    total = 0.0
    for l in lignes:
        ht = (l.montant_ht_cts or 0) / 100
        total += ht
        ean_s = l.ean or "(no ean)"
        print(f"  p{l.page_number or '?'}  {ean_s:15s}  {(l.designation or '')[:35]:35s}"
              f"  qte={str(l.quantite or '?'):>5}  pu={str((l.prix_unitaire_cts or 0)//100) if l.prix_unitaire_cts else '?':>6}€"
              f"  ht={ht:8.2f}€")
    print(f"  TOTAL LIGNES : {total:.2f}€\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--detail", action="store_true", help="Afficher le détail des lignes pour chaque BAD")
    parser.add_argument("--pdf", type=str, default=None, help="Analyser un seul PDF")
    args = parser.parse_args()

    if args.pdf:
        run_single(args.pdf, detail=True)
    else:
        pdfs = collect_pdfs()
        print(f"PDFs trouvés : {len(pdfs)}")
        run_batch(pdfs, detail=args.detail)
