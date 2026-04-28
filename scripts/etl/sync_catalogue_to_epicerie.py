"""Sync catalogue_produits → epicerie_produits (gap §6.5).

Lit les produits du catalogue global (catalogue_produits, table sans tenant_id)
filtrés par source_fournisseur, et upsert dans epicerie_produits pour un tenant.

Stratégie upsert :
  - Si EAN présent : upsert par (tenant_id, ean) — update designation + categorie
  - Si pas d'EAN : insert si designation_clean absente, sinon skip

Ce script est le chaînon manquant entre le pipeline ETL (qui peuple
catalogue_produits) et le module épicerie (qui lit epicerie_produits).

Workflow complet :
    1. ETL : python scripts/etl/import_pipeline.py --fichier xxx.pdf --fournisseur metro
    2. Sync : python scripts/etl/sync_catalogue_to_epicerie.py --tenant-id 1 --vendor-id 1

Usage :
    python3 scripts/etl/sync_catalogue_to_epicerie.py \\
        --tenant-id 1 \\
        --vendor-id 1 \\
        [--source METRO]   # défaut: METRO \\
        [--dry-run]

Variables d'environnement requises : DATABASE_URL (depuis .env).
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import app.models  # noqa: F401 — enregistre tous les modèles SQLAlchemy

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalogue.catalogue_produit import CatalogueProduit
from app.models.epicerie.produit import EpicerieProduit
from app.models.epicerie.stock import EpicerieStock

logger = logging.getLogger(__name__)

_DESIGNATION_MAXLEN = 255


@dataclass
class _Stats:
    catalogue_lus: int = 0
    inseres: int = 0
    mis_a_jour: int = 0
    ignores: int = 0
    stock_crees: int = 0


# -- Normalisation désignation ------------------------------------------------

# Unités de poids/volume reconnues (insensible à la casse)
_UNITS = r"(?:GR?|KG|MGR?|ML|CL|DL|LT?|OZ|LB)"

# Contenants / conditionnement
_CONTAINERS = (
    r"(?:SAC|SACHET|BOITE|BTE|BIDON|BOUTEILLE|BTLLE|BOUT|PAQUET|PQT|"
    r"PACK|LOT|BARQUETTE|BQTTE|CARTON|COLIS|ETUI|PLATEAU|FILM|POT|"
    r"TUBE|FLACON|ROULEAU|BRIQUE|BAG|SEAU|POCHE|FILET|BOTTE|"
    r"CAISSE|FUT|JERRICAN|DOSETTE|CAPSULE)"
)

# Mots-bruit fournisseur (supprimés globalement)
_NOISE_WORDS = re.compile(
    r"\bMETRO\b|\bREF\b|\bART\.?\s*|\bN°\s*ART\b|\bENVIRON\b|\bSOIT\b",
    re.IGNORECASE,
)

# 1) Multiplicateur : X12, X 24, x6 (en fin ou isolé)
_RE_MULTIPLIER = re.compile(
    r"\bX\s*\d+\b",
    re.IGNORECASE,
)

# 2) Quantité + unité : 600 GR, 1.5KG, 33CL, 5L, 250 ML
_RE_QTY_UNIT = re.compile(
    rf"\b\d+(?:[.,]\d+)?\s*{_UNITS}\b",
    re.IGNORECASE,
)

# 3) Contenant avec article/préposition optionnel : LE SAC, BOITE DE 12, LOT DE 3
_RE_CONTAINER = re.compile(
    rf"(?:\b(?:LE|LA|LES|EN|AU|PAR)\s+)?{_CONTAINERS}(?:\s+DE\s+\d+)?\b",
    re.IGNORECASE,
)

# 4) Code article numérique en début : "123456 PAIN..." → "PAIN..."
_RE_LEADING_CODE = re.compile(r"^\d{4,7}\s+")

# 5) Nombre orphelin en fin de chaîne (ex: "... 600" résiduel)
_RE_TRAILING_NUMBER = re.compile(r"\s+\d+(?:[.,]\d+)?$")

# 6) Tirets/slashs isolés (artefacts OCR)
_RE_ARTEFACT_SEPS = re.compile(r"\s+[-/]\s+")

# 7) Codes étoilés OCR : "018212*1", "3560070*"
_RE_STAR_CODE = re.compile(r"\b\d+\*\d*\b")

# 8) Combiné multiplicateur+unité collé : "6X140G", "12x33CL"
_RE_COMBINED_MULT_UNIT = re.compile(
    rf"\b\d+\s*[Xx]\s*\d+(?:[.,]\d+)?\s*{_UNITS}\b",
    re.IGNORECASE,
)

# 9) Pourcentages : "20%", "5.5% VOL", "40% MG"
_RE_PERCENTAGE = re.compile(r"\b\d+(?:[.,]\d+)?\s*%\s*(?:VOL|MG|MAT\.?\s*GR\.?)?\b", re.IGNORECASE)

# 10) Nombre orphelin en début (résidu après suppression code)
_RE_LEADING_NUMBER = re.compile(r"^\d+(?:[.,]\d+)?\s+")

# 11) Lettre isolée OCR (TVA code qui fuit : "125G t", "SPRAY i BOITE")
# Sauf articles courants (A, L, D = "d'") et sigles
_RE_ISOLATED_LETTER = re.compile(r"\s+[a-z]\b")

# 12) Lettre collée en début de mot (OCR merge : "lDIVINIUM", "iGEL")
_RE_OCR_MERGED_LETTER = re.compile(r"\b([a-z])([A-Z][A-Za-z]+)")

# 13) Degré OCR : "40aD", "37.5D" (notation alcool/régie METRO)
_RE_DEGREE_OCR = re.compile(r"\b\d+(?:[.,]\d+)?\s*[aA]?[dD]\b")

# 14) Désignation trop courte post-nettoyage (artefact résiduel < 4 chars alpha)
_MIN_DESIGNATION_ALPHA = 4

# 15) Trailing single letter (uppercase, post-regex) : "... VP L" → "... VP"
_RE_TRAILING_SINGLE_LETTER = re.compile(r"\s+[A-Z]\s*$")

# 16) Leading single letter (OCR) : "m MISE EN ROUTE" → "MISE EN ROUTE"
_RE_LEADING_SINGLE_LETTER = re.compile(r"^[A-Z]\s+", re.IGNORECASE)

# Mots à garder en majuscules (sigles courants alimentaire)
_UPPERCASE_KEEP = frozenset({
    "AOC", "AOP", "IGP", "BIO", "AB", "STG", "Label",
    "HVE", "MSC", "ASC",
})


# ── Nettoyage final post-sync : patterns résiduels ────────────────────────────
# Appliqué en fin de _build_designation_vente() et _normaliser() pour traiter
# les artefacts fournisseur-spécifiques que les regex séquentielles laissent
# passer. 8 règles documentées dans docs (analyse qualité désignations).

# R1 : taxons latins entre parenthèses — noms scientifiques bruts issus des
# fiches produit TAIYAT ("(gadus morhua)", "(clarias Macrocep", "(pangasius)").
# Détection : parenthèse ouvrante suivie de 1+ mots purement alphabétiques
# (min 3 chars, avec ou sans parenthèse fermante). La regex STOPPE au premier
# token contenant un chiffre, ce qui préserve les volumes qui suivent.
# Ex: "Chat Poisson (clarias Macrocep 4kg" → "Chat Poisson 4kg"
_RE_LATIN_TAXON = re.compile(
    r"\s*\(\s*[A-Za-zÀ-ÿ]{3,}(?:\s+[A-Za-zÀ-ÿ]{3,})*\)?",
)

# R2 : parenthèse orpheline non fermée restante (fragment non-latin)
_RE_UNCLOSED_PAREN = re.compile(r"\s*\([^)]*$")

# R3 : symbole degré isolé ("Haricots Blancs °1") = N° mal parsé
# Négative lookbehind sur N/n pour préserver les "N°1" déjà bien formés.
_RE_ORPHAN_DEGREE = re.compile(r"(?<![Nn])\s*°\s*(\d+)")

# R4 : codes METRO répétés (sous-marques sans valeur commerciale)
# "Metro Pro Mpro Bobine" → "Bobine" (la marque seule "Metro" est préservée au
# niveau supérieur). On retire aussi "Pro " isolé après un mot "Metro".
_RE_METRO_SUBBRAND = re.compile(
    r"\b(?:Pro\s+Mpro|Mpro|Ppx|Hwd|Tpe)\b",
    re.IGNORECASE,
)

# R5 : suffixes codes tronqués en fin ("... Gr", "... Ca", "... Mu")
# Liste vendor-agnostique de codes 2-3 lettres sans valeur informative qu'on
# observe en fin de désignation après nettoyage partiel des unités.
_TRAILING_CODE_SUFFIXES = frozenset({
    "Gr", "GR", "Kg", "KG", "Cl", "CL", "Ml", "ML",  # unités orphelines (le nombre a été retiré)
    "Ca", "Mu", "Fi", "Dr", "Ds", "Bk", "Bv", "Lp", "Pd",  # codes OCR/vendor
    "Hal", "Cert", "Ref", "Mp", "Ue", "Bf", "Pl",
})

# R6 : préfixe "Marque Commune" (générique METRO marque blanche)
_RE_MARQUE_COMMUNE = re.compile(r"^\s*(?:Marque\s+Commune)\s+", re.IGNORECASE)

# R7 : ponctuation finale indésirable (virgule, point seul, point-virgule, deux-points)
_RE_TRAILING_PUNCT = re.compile(r"[,;:.]+\s*$")

# R8 : double apostrophes et guillemets doubles OCR
_RE_DOUBLE_APOS = re.compile(r"['`´]{2,}")


def _cleanup_designation_final(text: str) -> str:
    """Nettoyage final appliqué à la fin de la normalisation.

    Traite les patterns résiduels observés sur 1620+ produits réels (métriques
    qualité 2026-04-24) : parenthèses orphelines, taxons latins, °N mal parsé,
    sous-marques METRO, suffixes tronqués, préfixes marque blanche, ponctuation
    finale, apostrophes doubles. Idempotent.
    """
    if not text:
        return ""
    s = text

    # R1+R2 : parenthèses (latin taxon d'abord, puis orpheline restante)
    s = _RE_LATIN_TAXON.sub("", s)
    s = _RE_UNCLOSED_PAREN.sub("", s)

    # R3 : °N → N°N (ajoute la lettre N devant les degrés orphelins)
    s = _RE_ORPHAN_DEGREE.sub(r" N°\1", s)

    # R4 : retire sous-marques METRO
    s = _RE_METRO_SUBBRAND.sub("", s)

    # R5 : retire suffixe code tronqué en fin (itératif : "... Pro Gr" → "... Pro" → "...")
    changed = True
    while changed:
        changed = False
        parts = s.rsplit(" ", 1)
        if len(parts) == 2 and parts[1] in _TRAILING_CODE_SUFFIXES:
            s = parts[0]
            changed = True

    # R6 : préfixe "Marque Commune"
    s = _RE_MARQUE_COMMUNE.sub("", s)

    # R7+R8 : ponctuation et apostrophes
    s = _RE_DOUBLE_APOS.sub("'", s)
    s = _RE_TRAILING_PUNCT.sub("", s)

    # Collapse espaces + strip final
    s = re.sub(r"\s+", " ", s).strip()

    return s


def _build_designation_vente(
    marque: str | None,
    designation_raw: str,
    conditionnement: str | None,
) -> str:
    """Construit une désignation de vente propre : Marque + Produit + Volume.

    Transformations :
      - Extraire le type produit (ce qui reste après suppression marque, codes, specs)
      - Ajouter le volume unitaire depuis le conditionnement (sans le colisage)
      - Title case intelligent

    Exemples :
      ("HEINEKEN", "HEINEKEN", "65cL, lot de 12")                → "Heineken 65cL"
      ("CIROC", "VODKA CIROC COCONUT37. 5D70", "70cL")           → "Ciroc Coconut Vodka 70cL"
      ("GILBERT", "SIROP GILBERT PASSION", "1L")                 → "Gilbert Sirop Passion 1L"
      ("ARO", "ARO MAYO ALLEGEE ARO SEAU", "5L")                 → "ARO Mayo Allégée 5L"
      (None, "DRAGIBUS SACHETS", "40g, lot de 30")                → "Dragibus Sachets 40g"
    """
    if not designation_raw or not designation_raw.strip():
        return ""

    desig = designation_raw.strip()

    # 1. Extraire le type produit = designation sans la marque, sans les codes techniques
    product_type = desig
    if marque:
        # Supprimer la marque du début ou de n'importe où
        import re as _re
        marque_pattern = _re.escape(marque.upper())
        product_type = _re.sub(marque_pattern, "", product_type.upper(), count=1).strip()

    # 2. Supprimer les codes techniques
    product_type = re.sub(r'\d+[.,]\s?\d*D\d*\w*', '', product_type)      # "37.5D70CL", "40D"
    product_type = re.sub(r'\b\d+[.,]?\d*\s*(CL|ML|L|KG|G)\b', '', product_type, flags=re.I)  # "70CL", "5L"
    product_type = re.sub(r'\b\d+\s*[×Xx]\s*\d+\s*(CL|ML|L|KG|G)?\b', '', product_type, flags=re.I)  # "12X33CL"
    product_type = re.sub(r'\bX\d+\b', '', product_type, flags=re.I)      # "X12", "X6"
    product_type = re.sub(r'\b(VP|BTE|PET|BID|FUT|CAN|BAG|BIB|BOUT)\b', '', product_type, flags=re.I)
    product_type = re.sub(r'\b(PROMO|OFFRE|GRATUIT)\b', '', product_type, flags=re.I)
    product_type = re.sub(r'\b\d{5,}\b', '', product_type)                # codes articles (5+ chiffres)
    product_type = re.sub(r'\b[A-Z]\b(?!\s*$)', '', product_type)         # lettres isolées
    # Codes METRO courts : 4f, 2p, 6v, Vbf, Grs, Rato, Fbon, Rdm, Bf, Ue
    product_type = re.sub(r'\b\d[a-z]\b', '', product_type)               # "4f", "2p", "6v"
    product_type = re.sub(r'\b(VBF|GRS|RATO|FBON|RDM|BF|UE|SERV|DUPLI)\b', '', product_type, flags=re.I)
    # Slash-codes : /p, /site, /epong, S/v, S/at
    product_type = re.sub(r'\b\w*/\w+\b', '', product_type)               # "S/v", "/p", "/site", "/epong"
    product_type = re.sub(r'/\w+', '', product_type)                       # "/p" en début
    # Tokens collés avec point et volume : "MONBAZIL.75CL" → "MONBAZIL"
    product_type = re.sub(r'\.\d+(?:CL|ML|L|KG|G)\b', '', product_type, flags=re.I)
    # +6v, +6VER type promotions
    product_type = re.sub(r'\+\d+\w*', '', product_type)
    # 250SERV, 10GX100 type codes quantité
    product_type = re.sub(r'\b\d+SERV\w*\b', '', product_type, flags=re.I)
    product_type = re.sub(r'\b\d+GX\d+\b', '', product_type, flags=re.I)
    product_type = re.sub(r'\s+', ' ', product_type).strip()

    # 3. Supprimer les mots-bruit, doublons marque, et nombres orphelins
    _NOISE = {"METRO", "REF", "ART", "ART.", "SEAU", "BUCH", "SAC", "BOITE",
              "PACK", "LOT", "DE", "*", "EN", "DU", "AU", "LE", "LA", "LES"}
    _BRAND_NUMBERS = {"1664", "86", "51"}
    words = []
    seen_upper: set[str] = set()
    for w in product_type.split():
        wu = w.upper()
        if wu in _NOISE or len(w) <= 1:
            continue
        if w.replace(".", "").replace(",", "").isdigit() and w not in _BRAND_NUMBERS:
            continue
        # Dédupliqué (même mot 2x)
        if wu in seen_upper:
            continue
        seen_upper.add(wu)
        words.append(w)
    # Supprimer les doublons de la marque (y compris variantes avec &)
    if marque:
        marque_upper = marque.upper()
        marque_words = set(marque_upper.split())
        # Aussi gérer "MOET&CHANDON" comme un seul mot
        marque_variants = marque_words | {marque_upper.replace(" ", "&"), marque_upper.replace("& ", "").replace(" &", "")}
        words = [w for w in words if w.upper() not in marque_variants]
    product_type = " ".join(words)

    # 4. Extraire le volume unitaire depuis le conditionnement (sans le colisage)
    volume_str = ""
    if conditionnement:
        vol_match = re.search(r'(\d+(?:[.,]\d+)?)\s*(cL|L|mL|kg|g)', conditionnement, re.I)
        if vol_match:
            vol_val = vol_match.group(1).replace(",", ".")
            vol_unit = vol_match.group(2)
            # Simplifier : 1000mL → 1L, 100cL → 1L
            try:
                v = float(vol_val)
                if vol_unit.lower() == "ml" and v >= 1000 and v % 1000 == 0:
                    vol_val, vol_unit = str(int(v / 1000)), "L"
                elif vol_unit.lower() == "cl" and v >= 100 and v % 100 == 0:
                    vol_val, vol_unit = str(int(v / 100)), "L"
                elif vol_unit.lower() == "g" and v >= 1000 and v % 1000 == 0:
                    vol_val, vol_unit = str(int(v / 1000)), "kg"
            except ValueError:
                pass
            # Normaliser l'unité : cL, mL, L, g, kg
            _UNIT_DISPLAY = {"cl": "cL", "ml": "mL", "l": "L", "g": "g", "kg": "kg"}
            vol_unit = _UNIT_DISPLAY.get(vol_unit.lower(), vol_unit)
            volume_str = f"{vol_val}{vol_unit}"

    # 5. Assembler : Marque + Type + Volume
    parts: list[str] = []
    if marque:
        parts.append(marque)
    if product_type:
        parts.append(product_type)
    if volume_str:
        parts.append(volume_str)

    result = " ".join(parts)
    if not result:
        return ""

    # Title case sauf les unités (cL, mL, L, g, kg) qu'on préserve
    titled = _title_case_smart(result)
    # Restaurer le volume à la fin avec la bonne casse
    if volume_str:
        titled = re.sub(
            re.escape(volume_str).replace(r'\-', '-'),
            volume_str,
            titled,
            flags=re.I,
        )
    return _cleanup_designation_final(titled)


def _title_case_smart(text: str) -> str:
    """Title case en préservant les sigles connus en majuscules."""
    words = text.split()
    result: list[str] = []
    for w in words:
        if w.upper() in _UPPERCASE_KEEP:
            result.append(w.upper())
        elif len(w) <= 1:
            result.append(w.lower())
        else:
            result.append(w.capitalize())
    return " ".join(result)


def _normaliser(texte: str) -> str:
    """Normalise une désignation brute fournisseur pour affichage épicerie.

    Transformations :
      1. Suppression mots-bruit fournisseur (METRO, REF, ART.)
      2. Suppression code article numérique en tête
      3. Suppression conditionnement (SAC, BOITE, LOT DE...)
      4. Suppression quantités + unités (600 GR, 1.5KG, 33CL)
      5. Suppression multiplicateurs (X12, X 24)
      6. Suppression nombres orphelins résiduels en fin
      7. Title case intelligent (préserve sigles AOC, BIO, IGP...)
    """
    if not texte or not texte.strip():
        return ""

    # Phase 1 : nettoyage OCR sur texte original (mixed case)
    s = " ".join(texte.split())
    # Réparer lettres collées OCR : "lDIVINIUM" → "DIVINIUM"
    s = _RE_OCR_MERGED_LETTER.sub(r"\2", s)
    # Supprimer lettres isolées minuscules (TVA code leak : "125G t", "SPRAY i")
    s = _RE_ISOLATED_LETTER.sub("", s)

    # Phase 2 : normalisation principale (en uppercase pour regex robustes)
    s = " ".join(s.upper().split())

    s = _NOISE_WORDS.sub("", s)
    s = _RE_LEADING_CODE.sub("", s)
    s = _RE_STAR_CODE.sub("", s)
    s = _RE_COMBINED_MULT_UNIT.sub("", s)
    s = _RE_CONTAINER.sub("", s)
    s = _RE_QTY_UNIT.sub("", s)
    s = _RE_MULTIPLIER.sub("", s)
    s = _RE_PERCENTAGE.sub("", s)
    s = _RE_DEGREE_OCR.sub("", s)
    s = _RE_TRAILING_NUMBER.sub("", s)
    s = _RE_LEADING_NUMBER.sub("", s)
    s = _RE_ARTEFACT_SEPS.sub(" ", s)
    s = _RE_TRAILING_SINGLE_LETTER.sub("", s)
    s = _RE_LEADING_SINGLE_LETTER.sub("", s)

    s = " ".join(s.split()).strip()

    if not s:
        return ""

    # Phase 3 : mise en forme
    s_mixed = _title_case_smart(s)

    # Rejeter si trop peu de contenu alpha (résidu OCR pur)
    alpha_chars = sum(1 for c in s_mixed if c.isalpha())
    if alpha_chars < _MIN_DESIGNATION_ALPHA:
        return ""

    return _cleanup_designation_final(s_mixed)[:_DESIGNATION_MAXLEN]


# -- Upsert helpers -----------------------------------------------------------


_DEFAULT_UNITE_VENTE = "U"
_DEFAULT_TVA = 2000


async def _upsert_par_ean(
    db: AsyncSession,
    tenant_id: int,
    ean: str,
    designation_clean: str,
    categorie: Optional[str],
    vendor_id: Optional[int],
    prix_unitaire_cts: Optional[int],
    taux_tva: Optional[int],
    conditionnement: Optional[str],
    unite_base: Optional[str],
    catalogue_unite_base: Optional[str] = None,
    catalogue_colisage: Optional[int] = None,
    catalogue_volume_ml: Optional[int] = None,
) -> tuple[str, Optional[int]]:
    """Upsert par EAN (mode conservateur).

    Données fournisseur (prix, tva) : toujours mises à jour.
    Données manuelles (nom_court, description, categorie) : jamais écrasées.
    unite_vente : mise à jour seulement si encore au défaut "U".
    description : remplie depuis conditionnement seulement si vide.
    unite_base + colisage : propagés depuis catalogue (toujours mis à jour si
    disponibles) pour rendre "1 U" lisible côté épicerie.
    """
    result = await db.execute(
        select(EpicerieProduit).where(
            EpicerieProduit.tenant_id == tenant_id,
            EpicerieProduit.ean == ean,
        )
    )
    existing = result.scalar_one_or_none()
    if existing is None:
        achat = prix_unitaire_cts or 0
        produit = EpicerieProduit(
            tenant_id=tenant_id,
            ean=ean,
            designation_clean=designation_clean,
            categorie=categorie,
            vendor_id=vendor_id,
            prix_achat_cts=achat,
            prix_unitaire_cts=achat,  # sera recalculé par recalculate-prices
            taux_tva=taux_tva or _DEFAULT_TVA,
            unite_vente=unite_base or _DEFAULT_UNITE_VENTE,
            unite_base=catalogue_unite_base,
            colisage=catalogue_colisage,
            volume_unitaire_ml=catalogue_volume_ml,
            description=conditionnement,
            actif=True,
        )
        db.add(produit)
        await db.flush()
        return "insert", produit.id

    changed = False
    # Designation : toujours mettre à jour (normalisation améliorée)
    if existing.designation_clean != designation_clean:
        existing.designation_clean = designation_clean
        changed = True
    # Categorie : seulement si pas encore renseignée
    if categorie and not existing.categorie:
        existing.categorie = categorie
        changed = True
    # Vendor : toujours (donnée fournisseur)
    if vendor_id is not None and existing.vendor_id != vendor_id:
        existing.vendor_id = vendor_id
        changed = True
    # Prix : toujours (donnée fournisseur fraîche)
    if prix_unitaire_cts is not None and existing.prix_unitaire_cts != prix_unitaire_cts:
        existing.prix_unitaire_cts = prix_unitaire_cts
        changed = True
    # TVA : toujours
    if taux_tva is not None and existing.taux_tva != taux_tva:
        existing.taux_tva = taux_tva
        changed = True
    # Unite : seulement si encore au défaut
    if unite_base and existing.unite_vente == _DEFAULT_UNITE_VENTE:
        existing.unite_vente = unite_base
        changed = True
    # Description : seulement si vide (ne pas écraser seed manuel)
    if conditionnement and not existing.description:
        existing.description = conditionnement
        changed = True
    # unite_base physique : propagée depuis catalogue (update si changement)
    if catalogue_unite_base and existing.unite_base != catalogue_unite_base:
        existing.unite_base = catalogue_unite_base
        changed = True
    # colisage : propagé depuis catalogue (update si changement)
    if catalogue_colisage is not None and existing.colisage != catalogue_colisage:
        existing.colisage = catalogue_colisage
        changed = True
    # volume_unitaire_ml : propagé depuis catalogue (update si changement)
    if catalogue_volume_ml is not None and existing.volume_unitaire_ml != catalogue_volume_ml:
        existing.volume_unitaire_ml = catalogue_volume_ml
        changed = True

    return ("update" if changed else "skip"), existing.id


async def _insert_if_absent(
    db: AsyncSession,
    tenant_id: int,
    designation_clean: str,
    categorie: Optional[str],
    vendor_id: Optional[int],
    prix_unitaire_cts: Optional[int],
    taux_tva: Optional[int],
    conditionnement: Optional[str],
    unite_base: Optional[str],
    catalogue_unite_base: Optional[str] = None,
    catalogue_colisage: Optional[int] = None,
    catalogue_volume_ml: Optional[int] = None,
) -> tuple[str, Optional[int]]:
    """Insert si absent (case-insensitive). Retourne (action, produit_id)."""
    result = await db.execute(
        select(EpicerieProduit).where(
            EpicerieProduit.tenant_id == tenant_id,
            EpicerieProduit.ean.is_(None),
            EpicerieProduit.designation_clean.ilike(designation_clean),
        ).limit(1)
    )
    if result.scalar_one_or_none() is not None:
        return "skip", None
    achat = prix_unitaire_cts or 0
    produit = EpicerieProduit(
        tenant_id=tenant_id,
        ean=None,
        designation_clean=designation_clean,
        categorie=categorie,
        vendor_id=vendor_id,
        prix_achat_cts=achat,
        prix_unitaire_cts=achat,  # sera recalculé par recalculate-prices
        taux_tva=taux_tva or _DEFAULT_TVA,
        unite_vente=unite_base or _DEFAULT_UNITE_VENTE,
        unite_base=catalogue_unite_base,
        colisage=catalogue_colisage,
        volume_unitaire_ml=catalogue_volume_ml,
        description=conditionnement,
        actif=True,
    )
    db.add(produit)
    await db.flush()
    return "insert", produit.id


# -- Stock creation helper -----------------------------------------------------


async def _ensure_stock(
    db: AsyncSession,
    tenant_id: int,
    produit_id: int,
) -> bool:
    """Crée une entrée EpicerieStock si absente. Retourne True si créée."""
    result = await db.execute(
        select(EpicerieStock.id).where(
            EpicerieStock.tenant_id == tenant_id,
            EpicerieStock.produit_id == produit_id,
        ).limit(1)
    )
    if result.scalar_one_or_none() is not None:
        return False
    db.add(EpicerieStock(
        tenant_id=tenant_id,
        produit_id=produit_id,
        quantite=0,
        seuil_alerte=0,
    ))
    return True


# -- Core sync ----------------------------------------------------------------


async def sync(
    db: AsyncSession,
    tenant_id: int,
    vendor_id: Optional[int],
    source: str,
    dry_run: bool,
) -> _Stats:
    """Lit catalogue_produits[source] et upsert dans epicerie_produits + stock."""
    q = select(CatalogueProduit)
    if source:
        q = q.where(CatalogueProduit.source_fournisseur == source.upper())

    result = await db.execute(q)
    produits = result.scalars().all()
    stats = _Stats(catalogue_lus=len(produits))

    logger.info("%d produits catalogue trouvés (source=%s)", len(produits), source)

    for cp in produits:
        # Skip les produits fusionnés (conflit résolu en MERGED)
        if cp.merged_into_id is not None:
            stats.ignores += 1
            continue

        designation_clean = _build_designation_vente(
            marque=cp.marque,
            designation_raw=cp.designation,
            conditionnement=cp.conditionnement,
        )
        if not designation_clean:
            stats.ignores += 1
            continue

        categorie = cp.categorie_code
        prix_cts = cp.prix_unitaire_cts
        taux_tva = cp.taux_tva_centieme
        conditionnement = cp.conditionnement
        # Toujours vendre à la pièce (bouteille, canette, paquet)
        unite_base = "U"

        if dry_run:
            logger.debug(
                "DRY-RUN ean=%s designation=%r prix=%s tva=%s condit=%s unite=%s",
                cp.ean, designation_clean, prix_cts, taux_tva,
                conditionnement, unite_base,
            )
            stats.inseres += 1
            continue

        if cp.ean:
            action, produit_id = await _upsert_par_ean(
                db, tenant_id, cp.ean, designation_clean,
                categorie, vendor_id, prix_cts, taux_tva,
                conditionnement, unite_base,
                catalogue_unite_base=cp.unite_base,
                catalogue_colisage=cp.colisage,
                catalogue_volume_ml=cp.volume_unitaire_ml,
            )
        else:
            action, produit_id = await _insert_if_absent(
                db, tenant_id, designation_clean,
                categorie, vendor_id, prix_cts, taux_tva,
                conditionnement, unite_base,
                catalogue_unite_base=cp.unite_base,
                catalogue_colisage=cp.colisage,
                catalogue_volume_ml=cp.volume_unitaire_ml,
            )

        if action == "insert":
            stats.inseres += 1
        elif action == "update":
            stats.mis_a_jour += 1
        else:
            stats.ignores += 1

        # Créer l'entrée stock si elle n'existe pas
        if produit_id is not None:
            created = await _ensure_stock(db, tenant_id, produit_id)
            if created:
                stats.stock_crees += 1

            # Propager les EANs secondaires catalogue → épicerie (multi-EAN scan caisse)
            await _sync_secondary_eans(db, tenant_id, cp.id, produit_id)

    return stats


async def _sync_secondary_eans(
    db: AsyncSession,
    tenant_id: int,
    catalogue_produit_id: int,
    epicerie_produit_id: int,
) -> int:
    """Copie les EANs secondaires catalogue_produit_eans → epicerie_produit_eans.

    Idempotent : skip les EANs déjà présents (contrainte UNIQUE(tenant_id, ean)).
    Retourne le nb d'EANs ajoutés.
    """
    from app.models.catalogue.catalogue_produit_ean import CatalogueProduitEan
    from app.models.epicerie.produit_ean import EpicerieProduitEan

    result = await db.execute(
        select(CatalogueProduitEan).where(
            CatalogueProduitEan.catalogue_produit_id == catalogue_produit_id
        )
    )
    added = 0
    for sec in result.scalars().all():
        # Idempotence : check EAN déjà présent pour ce tenant (principal ou secondaire)
        exists = await db.execute(
            select(EpicerieProduitEan.id).where(
                EpicerieProduitEan.tenant_id == tenant_id,
                EpicerieProduitEan.ean == sec.ean,
            ).limit(1)
        )
        if exists.scalar_one_or_none() is not None:
            continue
        # Check aussi l'EAN principal épicerie
        main_exists = await db.execute(
            select(EpicerieProduit.id).where(
                EpicerieProduit.tenant_id == tenant_id,
                EpicerieProduit.ean == sec.ean,
            ).limit(1)
        )
        if main_exists.scalar_one_or_none() is not None:
            continue
        db.add(EpicerieProduitEan(
            produit_id=epicerie_produit_id,
            ean=sec.ean,
            tenant_id=tenant_id,
            source_fournisseur=sec.source_fournisseur,
        ))
        added += 1
    if added:
        await db.flush()
    return added


async def run(
    tenant_id: int,
    vendor_id: Optional[int],
    source: str,
    dry_run: bool,
) -> _Stats:
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        stats = await sync(db, tenant_id, vendor_id, source, dry_run)
        if not dry_run:
            await db.commit()
            logger.info(
                "Commit OK — %d insérés, %d mis à jour, %d stock créés",
                stats.inseres, stats.mis_a_jour, stats.stock_crees,
            )
    return stats


# -- CLI ----------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Sync catalogue_produits → epicerie_produits",
    )
    p.add_argument("--tenant-id", type=int, default=1, dest="tenant_id",
                   help="ID du tenant épicerie (défaut: 1).")
    p.add_argument("--vendor-id", type=int, default=None, dest="vendor_id",
                   help="FK finance_vendors.id (optionnel).")
    p.add_argument("--source", default="METRO",
                   help="Filtre source_fournisseur (défaut: METRO). Laisser vide pour tout.")
    p.add_argument("--dry-run", action="store_true", dest="dry_run",
                   help="Lit et compte sans écrire en base.")
    return p


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    args = _build_parser().parse_args()
    stats = asyncio.run(run(
        tenant_id=args.tenant_id,
        vendor_id=args.vendor_id,
        source=args.source,
        dry_run=args.dry_run,
    ))
    print("\n=== Résultat sync catalogue → epicerie_produits ===")
    print(f"  Catalogue lus  : {stats.catalogue_lus}")
    print(f"  Insérés        : {stats.inseres}")
    print(f"  Mis à jour     : {stats.mis_a_jour}")
    print(f"  Ignorés        : {stats.ignores}")
    print(f"  Stock créés    : {stats.stock_crees}")
    if args.dry_run:
        print("  [DRY-RUN — aucune écriture en base]")


if __name__ == "__main__":
    main()
