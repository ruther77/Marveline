"""Parser fournisseur GNANAM — photos HEIC via Tesseract OCR.

L'Excel consolidé `Factures_GNANAM_NOUTAM_Complet.xlsx` est NON FIABLE (consolidation
manuelle côté client). On repart des photos HEIC sources.

Approche :
  1. HEIC → greyscale + autocontrast (PIL + pillow-heif)
  2. Tesseract OCR (langue fra+eng, psm 6)
  3. Regex sur texte OCR : header (numero, date) + lignes tabulaires (pipes)
  4. Construction LigneParsee + FactureMetadata — pipeline commun identique

Format facture GNANAM EXOTIQUE :
    SARL GNANAM EXOTIQUE / Code client 3989 / S.A.S. NOUTAM
    FACTURE <numero>
    Table: CODE | DESIGNATION | QTÉ | PU_HT | PU_TTC | REMISE | TVA% | TOTAL_TTC

Les photos floues/obliques donnent un OCR pauvre → quality_score=0, l'opérateur
peut alors re-prendre la photo ou saisir manuellement.

GNANAM = NOUTAM (épicerie, tenant 2) exclusivement.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date as date_cls, datetime
from pathlib import Path
from typing import Optional

from app.etl_types import FactureMetadata, LigneParsee

logger = logging.getLogger(__name__)

_SOURCE_FOURNISSEUR = "GNANAM"
_DEFAULT_TARGET_TENANT = 2  # NOUTAM épicerie
_DEFAULT_CLIENT_NAME = "NOUTAM"

_MAX_IMAGE_DIM = 2200  # px — limite pour tesseract (équilibre qualité/temps)

# Regex header
_RE_FACTURE_NUM = re.compile(r"FACTURE\s+([A-Z0-9/\-]{4,})", re.IGNORECASE)
_RE_NUMERO_ALT = re.compile(r"(?:N°|No|N[oO])\s*(?:facture|fact)\s*:?\s*([A-Z0-9/\-]{4,})", re.IGNORECASE)
_RE_DATE_DMY = re.compile(r"\b(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})\b")

# Ligne produit : les colonnes OCR sont souvent séparées par "|" (lignes de tableau)
# Format : [CODE] DESIGNATION Qté PU_HT PU_TTC REMISE TVA TOTAL_TTC
# Ex tesseract : "05038463587 | DUREX GEL SENSITIVE 50CL 12 | 1,000 | 37,42 | 44,90 | 0,00 | 20.00 | 44,90"
_RE_NUMBER = re.compile(r"-?\d+(?:[.,]\d+)?")
_RE_CODE = re.compile(r"^\s*(\d{3,15}|[A-Z]{1,4}\d{0,3})")


@dataclass
class _OcrLigne:
    code: Optional[str]
    designation: str
    quantite: Optional[float]
    prix_ht: Optional[float]
    prix_ttc: Optional[float]
    remise_pct: Optional[float]
    taux_tva: Optional[float]
    total_ttc: Optional[float]


def _require_pillow_heif():
    try:
        import pillow_heif
        pillow_heif.register_heif_opener()
    except ImportError as exc:
        raise ImportError("pillow-heif requis : pip install pillow-heif") from exc


def _require_tesseract():
    try:
        import pytesseract
        return pytesseract
    except ImportError as exc:
        raise ImportError("pytesseract requis + binaire tesseract-ocr") from exc


def _preprocess_image(img):
    """Pré-traitement image pour OCR : grayscale + autocontrast + sharpen + deskew léger.

    Deskew basé sur projection horizontale : on teste -2° à +2° (pas 0.5°) et
    on choisit l'angle maximisant la variance de projection horizontale
    (texte bien aligné = pics de lignes nets).
    """
    from PIL import Image, ImageFilter, ImageOps
    import numpy as np

    gray = ImageOps.autocontrast(img.convert("L"))
    # Sharpen doux — accentue les bords sans amplifier le bruit
    gray = gray.filter(ImageFilter.UnsharpMask(radius=1.5, percent=120, threshold=3))

    # Deskew : chercher angle maximisant la variance de projection horizontale
    arr = np.asarray(gray, dtype=np.uint8)
    # Binariser (Otsu-like : seuil = moyenne - 15%)
    threshold = max(80, int(arr.mean() * 0.85))
    binary = (arr < threshold).astype(np.uint8)

    # Deskew rapide : 4 angles testés (au lieu de 8). La plupart des photos
    # GNANAM sont à moins de ±1,5° de la verticale.
    best_angle = 0.0
    best_score = binary.sum(axis=1).var()
    for angle in (-1.5, -0.7, 0.7, 1.5):
        rotated = gray.rotate(angle, resample=Image.BILINEAR, fillcolor=255)
        rot_arr = np.asarray(rotated, dtype=np.uint8)
        rot_bin = (rot_arr < threshold).astype(np.uint8)
        score = rot_bin.sum(axis=1).var()
        if score > best_score * 1.08:  # 8% threshold pour éviter micro-rotations
            best_score = score
            best_angle = angle

    if abs(best_angle) > 0.1:
        gray = gray.rotate(best_angle, resample=Image.BILINEAR, fillcolor=255)

    return gray


def _ocr_image(fichier: str) -> str:
    """HEIC/JPG → OCR texte (fra+eng, multi-PSM).

    Essaie psm=6 (uniform block) ET psm=4 (single column tabular), retourne
    le texte avec le plus de pipes + alphanum (meilleur pour tables).
    """
    from PIL import Image
    path = Path(fichier)
    if not path.exists():
        raise FileNotFoundError(f"Image introuvable: {fichier}")

    if path.suffix.lower() in (".heic", ".heif"):
        _require_pillow_heif()

    pytesseract = _require_tesseract()
    img = Image.open(path)
    if max(img.size) > _MAX_IMAGE_DIM:
        img.thumbnail((_MAX_IMAGE_DIM, _MAX_IMAGE_DIM), Image.LANCZOS)

    processed = _preprocess_image(img)

    # OCR adaptatif : PSM=6 en premier. Fallback PSM=4 (tabular) SEULEMENT si
    # résultat pauvre. Évite de doubler le temps OCR sur les photos bien lues.
    try:
        text = pytesseract.image_to_string(processed, lang="fra+eng", config="--psm 6")
    except Exception as exc:
        logger.debug("Tesseract psm=6 failed: %s", exc)
        text = ""

    pipes = text.count("|")
    alphanum = sum(1 for c in text if c.isalnum())

    # Fallback PSM 4 (single column tabular) si pas assez de signal.
    if alphanum < 100 or pipes < 3:
        try:
            alt = pytesseract.image_to_string(processed, lang="fra+eng", config="--psm 4")
            alt_pipes = alt.count("|")
            alt_alphanum = sum(1 for c in alt if c.isalnum())
            if (alt_pipes * 5 + alt_alphanum) > (pipes * 5 + alphanum):
                text = alt
        except Exception as exc:
            logger.debug("Tesseract psm=4 fallback failed: %s", exc)

    return text


def _parse_fr_number(raw: str) -> Optional[float]:
    if not raw:
        return None
    s = raw.replace(" ", "").replace(",", ".")
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _parse_date(raw: str) -> Optional[date_cls]:
    if not raw:
        return None
    raw = raw.replace("-", "/")
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _extract_header(text: str) -> tuple[Optional[str], Optional[date_cls]]:
    """Extrait numéro facture + date depuis le texte OCR."""
    numero = None
    m = _RE_FACTURE_NUM.search(text) or _RE_NUMERO_ALT.search(text)
    if m:
        candidate = m.group(1).strip()
        # Filtrer les valeurs évidentes non-numéro (ex. "DUPLICATA", "NO525")
        if candidate.upper() not in {"DUPLICATA", "NF525"} and len(candidate) >= 4:
            numero = candidate

    # Chercher une date proche du mot FACTURE ou au début du document
    date = None
    for m in _RE_DATE_DMY.finditer(text[:2000]):
        d = _parse_date(m.group(1))
        if d and 2020 <= d.year <= 2030:
            date = d
            break
    return numero, date


def _parse_ligne_from_pipes(raw: str) -> Optional[_OcrLigne]:
    """Parse une ligne tabulaire séparée par '|' vers _OcrLigne."""
    # Normaliser bruit Tesseract : supprimer guillemets/étoiles parasites
    cleaned = re.sub(r'[""\']', "", raw)
    cleaned = re.sub(r"\*{2,}", "", cleaned)
    parts = [p.strip() for p in cleaned.split("|") if p.strip()]
    if len(parts) < 4:
        return None

    # Détecter code au début de la première partie
    code_match = _RE_CODE.match(parts[0])
    code = code_match.group(1) if code_match else None

    # Extraire tous les nombres des parties
    # Stratégie : les 2 derniers nombres = TVA% et TOTAL_TTC
    # Avant ça, on trouve PU_HT, PU_TTC, REMISE, QTÉ (ordre variable)
    all_nums_with_pos: list[tuple[int, float]] = []  # (part_idx, num)
    for idx, p in enumerate(parts):
        for m in _RE_NUMBER.finditer(p):
            val = _parse_fr_number(m.group(0))
            if val is not None:
                all_nums_with_pos.append((idx, val))

    if len(all_nums_with_pos) < 3:
        return None

    nums = [v for _, v in all_nums_with_pos]
    # Le dernier est le total_ttc
    total_ttc = nums[-1]
    # L'avant-dernier = taux_tva (valeur dans {5.5, 10, 20} typiquement)
    taux_tva = nums[-2] if nums[-2] in (5.5, 10.0, 20.0) or 1 <= nums[-2] <= 25 else None
    # Chercher quantité : premier nombre non-code (>0, < 9999)
    quantite = None
    for idx, v in all_nums_with_pos:
        if idx >= 1 and 0 < v < 9999 and v != taux_tva and v != total_ttc:
            quantite = v
            break

    # PU_HT et PU_TTC : entre qté et taux_tva
    mid_nums = [v for _, v in all_nums_with_pos if v not in (quantite, taux_tva, total_ttc)]
    prix_ht = mid_nums[0] if len(mid_nums) >= 1 else None
    prix_ttc = mid_nums[1] if len(mid_nums) >= 2 else None

    # Désignation : texte de la 2e partie (après code) nettoyé de nombres
    if len(parts) >= 2:
        desig_raw = parts[1]
    else:
        desig_raw = re.sub(r"^\s*\d{3,}\s*", "", parts[0])
    designation = re.sub(r"\s+\d[\d.,]*\s*$", "", desig_raw).strip()
    designation = re.sub(r"\s+", " ", designation)

    if len(designation) < 3:
        return None

    # Validation croisée qty × pu_ttc ≈ total_ttc (±2% tolérance)
    # Filtre les lignes où Tesseract a mal extrait des nombres (OCR corrupt).
    # Si quantite ou prix_ttc manque, on garde quand même (la validation humaine tranchera).
    if quantite and prix_ttc and total_ttc and quantite > 0 and prix_ttc > 0:
        expected = quantite * prix_ttc
        if expected > 0:
            delta_pct = abs(total_ttc - expected) / expected
            if delta_pct > 0.03:  # > 3% d'écart = probable erreur OCR
                # Essayer de réconcilier : peut-être que prix_ht a été pris pour prix_ttc
                if prix_ht and prix_ht > 0:
                    expected_ht = quantite * prix_ht
                    if expected_ht > 0 and abs(total_ttc - expected_ht) / expected_ht <= 0.03:
                        # C'était prix_ht×qty qui matchait → échange prix_ht/ttc
                        prix_ht, prix_ttc = prix_ttc, prix_ht
                    else:
                        # Vraiment incohérent → rejet de la ligne
                        logger.debug(
                            "GNANAM ligne rejetée : qty=%s pu_ttc=%s total=%s delta=%.1f%%",
                            quantite, prix_ttc, total_ttc, delta_pct * 100,
                        )
                        return None

    return _OcrLigne(
        code=code,
        designation=designation,
        quantite=quantite,
        prix_ht=prix_ht,
        prix_ttc=prix_ttc,
        remise_pct=None,
        taux_tva=taux_tva,
        total_ttc=total_ttc,
    )


def _extract_lignes(text: str) -> list[_OcrLigne]:
    """Extrait la liste des lignes produits du texte OCR."""
    lignes: list[_OcrLigne] = []
    for raw_line in text.splitlines():
        if "|" not in raw_line:
            continue
        if _parse_ligne_from_pipes(raw_line):
            parsed = _parse_ligne_from_pipes(raw_line)
            if parsed:
                lignes.append(parsed)
    return lignes


def _extract_totaux(text: str) -> tuple[Optional[int], Optional[int], Optional[int]]:
    """Cherche 'Total HT / TVA / TTC' dans le texte. Retourne (ht, tva, ttc) en centimes."""
    # Patterns tolérants
    ht = tva = ttc = None
    for m in re.finditer(r"Total\s+HT\s*:?\s*(\d+[.,]\d+)", text, re.IGNORECASE):
        ht = _parse_fr_number(m.group(1))
        break
    for m in re.finditer(r"Total\s+TVA\s*:?\s*(\d+[.,]\d+)", text, re.IGNORECASE):
        tva = _parse_fr_number(m.group(1))
        break
    for m in re.finditer(r"(?:Total\s+TTC|Net\s+[àa]\s+payer)\s*:?\s*(\d+[.,]\d+)", text, re.IGNORECASE):
        ttc = _parse_fr_number(m.group(1))
        break
    return (
        round(ht * 100) if ht else None,
        round(tva * 100) if tva else None,
        round(ttc * 100) if ttc else None,
    )


def _build_lignes_parsees(ocr_lignes: list[_OcrLigne]) -> list[LigneParsee]:
    result: list[LigneParsee] = []
    for ol in ocr_lignes:
        taux_tva_centieme = round(ol.taux_tva * 100) if ol.taux_tva else 550
        prix_ttc_cts = round(ol.prix_ttc * 100) if ol.prix_ttc else None
        prix_ht_cts = round(ol.prix_ht * 100) if ol.prix_ht else None
        if prix_ttc_cts is None and prix_ht_cts is not None:
            prix_ttc_cts = round(prix_ht_cts * (1 + taux_tva_centieme / 10000))
        total_ttc_cts = round(ol.total_ttc * 100) if ol.total_ttc else None
        total_ht_cts = None
        if total_ttc_cts is not None:
            total_ht_cts = round(total_ttc_cts / (1 + taux_tva_centieme / 10000))

        result.append(LigneParsee(
            designation=ol.designation,
            unite_base="U",
            source_fournisseur=_SOURCE_FOURNISSEUR,
            ean=None,
            quantite=ol.quantite,
            prix_unitaire_cts=prix_ttc_cts,
            montant_ht_cts=total_ht_cts,
            montant_ttc_cts=total_ttc_cts,
            taux_tva_centieme=taux_tva_centieme,
            article_fournisseur=ol.code,
            designation_raw=ol.designation,
        ))
    return result


def parse_with_facture_metrics(fichier: str) -> tuple[list[LigneParsee], dict]:
    """Parse une photo GNANAM via Tesseract. Retourne lignes + métriques."""
    try:
        text = _ocr_image(fichier)
    except Exception as exc:
        return [], {"file": str(fichier), "error": f"ocr_failed: {exc}", "quality_score": 0}

    alphanum_count = sum(1 for c in text if c.isalnum())
    # Seuil abaissé de 100 à 60 : tolérance accrue pour photos partiellement lisibles
    if alphanum_count < 60:
        return [], {
            "file": str(fichier), "quality_score": 0,
            "error": f"ocr_too_poor: {alphanum_count} alphanum chars",
            "ocr_text": text[:300],
        }

    numero, date = _extract_header(text)
    ocr_lignes = _extract_lignes(text)
    lignes = _build_lignes_parsees(ocr_lignes)

    declared_ht_cts, declared_tva_cts, declared_ttc_cts = _extract_totaux(text)
    computed_ttc_cts = sum(l.montant_ttc_cts or 0 for l in lignes)
    ecart_eur = ((declared_ttc_cts or 0) - computed_ttc_cts) / 100.0

    is_coherent = bool(declared_ttc_cts) and abs(ecart_eur) <= 1.0

    quality = 0
    if numero:
        quality += 20
    if date:
        quality += 20
    if declared_ttc_cts:
        quality += 20
    if lignes:
        quality += 20
    if is_coherent:
        quality += 20

    metrics = {
        "file": str(fichier),
        "invoice_number": numero,
        "invoice_date": date.isoformat() if date else None,
        "client_name": _DEFAULT_CLIENT_NAME,
        "line_count_output": len(lignes),
        "line_count_rejected": 0,
        "line_coherence_outlier_count": 0,
        "total_ht_declared_cts": declared_ht_cts,
        "total_tva_declared_cts": declared_tva_cts,
        "total_ttc_declared": declared_ttc_cts / 100.0 if declared_ttc_cts else None,
        "total_ttc_computed": computed_ttc_cts / 100.0,
        "ecart_ttc": ecart_eur,
        "ecart_ttc_abs": abs(ecart_eur),
        "is_total_coherent": is_coherent,
        "quality_score": quality,
        "ocr_char_count": alphanum_count,
    }
    return lignes, metrics


def parse_facture(fichier: str) -> tuple[list[LigneParsee], FactureMetadata]:
    lignes, metrics = parse_with_facture_metrics(fichier)

    date_iso = metrics.get("invoice_date")
    date_obj = None
    if date_iso:
        try:
            date_obj = date_cls.fromisoformat(date_iso)
        except (ValueError, TypeError):
            pass

    metadata = FactureMetadata(
        vendor_code=_SOURCE_FOURNISSEUR,
        numero_facture=metrics.get("invoice_number"),
        date_facture=date_obj,
        montant_ht_total=metrics.get("total_ht_declared_cts"),
        montant_tva_total=metrics.get("total_tva_declared_cts"),
        montant_ttc_total=(round(metrics["total_ttc_declared"] * 100)
                            if metrics.get("total_ttc_declared") else None),
        quality_score=min(round(metrics.get("quality_score", 0)), 100),
        ecart_reconciliation=metrics.get("ecart_ttc"),
        lignes_brutes=len(lignes),
        client_name=_DEFAULT_CLIENT_NAME,
        target_tenant_id=_DEFAULT_TARGET_TENANT,
    )
    return lignes, metadata


def parse(fichier: str) -> list[LigneParsee]:
    lignes, _ = parse_with_facture_metrics(fichier)
    return lignes


__all__ = ["parse", "parse_facture", "parse_with_facture_metrics"]
