"""Service de récupération automatique d'images produits.

Sources par priorité :
  1. Open Food Facts (par EAN) — plusieurs champs tentés (image_front_url, selected_images…)
  2. Bing Images (par "marque designation") — scraping HTML stable
  3. DuckDuckGo Images — fallback si Bing bloque

Les images sont stockées dans uploads/products/epicerie/{product_id}.jpg
et le chemin relatif est persisté dans epicerie_produits.image_url.
"""
import html
import logging
import os
import re
import time
from io import BytesIO
from typing import Optional
from urllib.parse import quote_plus

import requests
from PIL import Image

logger = logging.getLogger(__name__)

_USER_AGENT = "CaroCorp-ETL/1.0 (image-fetcher; contact@devup.fr)"
_BROWSER_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
_TIMEOUT = 10
_MAX_IMG_SIZE = 512  # px — thumbnail max
_MIN_IMG_SIZE = 50   # px — reject too small
_IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp")


def _get_products_img_dir() -> str:
    """Répertoire persistant pour les images produits."""
    from app.core.config import settings
    base = settings.UPLOAD_DIR or "uploads"
    if not os.path.isabs(base):
        base = os.path.abspath(base)
    try:
        os.makedirs(base, exist_ok=True)
    except PermissionError:
        base = os.path.abspath("uploads")
        os.makedirs(base, exist_ok=True)
    img_dir = os.path.join(base, "products", "epicerie")
    os.makedirs(img_dir, exist_ok=True)
    return img_dir


def _download_and_resize(url: str, dest_path: str) -> bool:
    """Télécharge une image, la redimensionne en thumbnail et la sauvegarde."""
    try:
        resp = requests.get(
            url,
            timeout=_TIMEOUT,
            headers={"User-Agent": _BROWSER_UA, "Accept": "image/*,*/*"},
            allow_redirects=True,
        )
        resp.raise_for_status()
        content = resp.content
        ct = resp.headers.get("content-type", "").lower()
        url_lower = url.lower()
        looks_like_image = (
            "image" in ct
            or any(url_lower.split("?")[0].endswith(ext) for ext in _IMAGE_EXTS)
        )
        if not looks_like_image and not content.startswith((b"\xff\xd8", b"\x89PNG", b"RIFF", b"GIF")):
            return False

        img = Image.open(BytesIO(content))
        if img.width < _MIN_IMG_SIZE or img.height < _MIN_IMG_SIZE:
            return False

        if img.mode in ("RGBA", "P", "LA"):
            img = img.convert("RGB")

        img.thumbnail((_MAX_IMG_SIZE, _MAX_IMG_SIZE), Image.LANCZOS)
        img.save(dest_path, "JPEG", quality=85, optimize=True)
        return True
    except Exception as exc:
        logger.debug("Image download failed %s: %s", url[:60], exc)
        return False


# ── Source 1 : Open Food Facts ────────────────────────────────────────────────


_OFF_FIELDS = (
    "image_front_url",
    "image_url",
    "image_front_small_url",
    "image_small_url",
    "image_ingredients_url",
    "image_nutrition_url",
)


def _extract_off_image(product: dict) -> Optional[str]:
    """Scanne tous les champs image pertinents d'un produit OFF."""
    for field in _OFF_FIELDS:
        url = product.get(field)
        if url and isinstance(url, str) and url.startswith("http"):
            return url
    # Essai selected_images (nouvelle structure OFF)
    selected = product.get("selected_images") or {}
    for key in ("front", "ingredients", "nutrition"):
        node = selected.get(key) or {}
        display = node.get("display") or {}
        if not isinstance(display, dict):
            continue
        for lang in ("fr", "en", "main"):
            url = display.get(lang)
            if url and isinstance(url, str) and url.startswith("http"):
                return url
    return None


def fetch_from_openfoodfacts(ean: str) -> Optional[str]:
    """Cherche l'image produit sur Open Food Facts par EAN.

    Tente plusieurs champs (front, ingredients, nutrition, selected_images).
    Returns: URL de l'image ou None.
    """
    if not ean or len(ean) < 8:
        return None
    try:
        fields = ",".join((*_OFF_FIELDS, "selected_images"))
        url = f"https://world.openfoodfacts.org/api/v2/product/{ean}.json?fields={fields}"
        resp = requests.get(url, timeout=_TIMEOUT, headers={"User-Agent": _USER_AGENT})
        if resp.status_code != 200:
            return None
        data = resp.json()
        if data.get("status") != 1:
            return None
        return _extract_off_image(data.get("product", {}))
    except Exception as exc:
        logger.debug("OFF lookup failed for %s: %s", ean, exc)
        return None


# ── Source 2 : Bing Images (HTML scraping) ────────────────────────────────────


_BING_IMG_RE = re.compile(r'"murl":"([^"]+)"')


def fetch_from_bing(query: str) -> Optional[str]:
    """Cherche la première image via Bing Image Search (scraping HTML).

    Bing inline le JSON dans attr `m='...'` avec entities HTML (`&quot;`),
    d'où le passage par html.unescape avant regex.
    Returns: URL de l'image ou None.
    """
    if not query or len(query) < 3:
        return None
    try:
        url = f"https://www.bing.com/images/search?q={quote_plus(query)}&form=HDRSC2&first=1"
        resp = requests.get(
            url,
            timeout=_TIMEOUT,
            headers={
                "User-Agent": _BROWSER_UA,
                "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
            },
        )
        if resp.status_code != 200:
            return None
        decoded = html.unescape(resp.text)
        for match in _BING_IMG_RE.finditer(decoded):
            img_url = match.group(1).replace("\\/", "/")
            if img_url.startswith("http") and not img_url.endswith(".svg"):
                return img_url
        return None
    except Exception as exc:
        logger.debug("Bing image search failed for %s: %s", query[:30], exc)
        return None


# ── Source 3 : DuckDuckGo Images (fallback) ───────────────────────────────────


def fetch_from_duckduckgo(query: str) -> Optional[str]:
    """Cherche la première image via DuckDuckGo Image Search.

    Returns: URL de l'image ou None.
    """
    if not query or len(query) < 3:
        return None
    try:
        # Étape 1 : obtenir le token vqd
        search_url = f"https://duckduckgo.com/?q={quote_plus(query)}&iax=images&ia=images"
        resp = requests.get(
            search_url,
            timeout=_TIMEOUT,
            headers={"User-Agent": _BROWSER_UA},
        )
        if resp.status_code != 200:
            return None

        vqd_match = re.search(r'vqd="([^"]+)"', resp.text) or re.search(r'vqd=([^&"]+)', resp.text)
        if not vqd_match:
            return None
        vqd = vqd_match.group(1)

        # Étape 2 : fetch les résultats images JSON
        img_url = (
            f"https://duckduckgo.com/i.js?l=fr-fr&o=json"
            f"&q={quote_plus(query)}&vqd={vqd}&f=,,,&p=1"
        )
        resp2 = requests.get(
            img_url,
            timeout=_TIMEOUT,
            headers={"User-Agent": _BROWSER_UA},
        )
        results = resp2.json().get("results", [])
        for res in results[:5]:
            img = res.get("image")
            if img and img.startswith("http"):
                return img
        return None
    except Exception as exc:
        logger.debug("DuckDuckGo image search failed for %s: %s", query[:30], exc)
        return None


# ── Pipeline complet ──────────────────────────────────────────────────────────


def _build_search_query(designation: str, marque: Optional[str]) -> str:
    """Construit une requête de recherche image nettoyée des codes METRO."""
    clean = re.sub(r'\d+[A-Z]{1,2}\b', '', designation)
    clean = re.sub(r'\b\d{5,}\b', '', clean)
    clean = clean.strip()
    parts = [p for p in (marque, clean) if p]
    return " ".join(parts) + " produit" if parts else ""


def _try_source(url: Optional[str], dest_path: str, source: str) -> bool:
    """Tente de télécharger une URL, log le succès."""
    if not url:
        return False
    if _download_and_resize(url, dest_path):
        logger.info("Image fetched via %s", source)
        return True
    return False


def fetch_product_image(
    product_id: int,
    ean: Optional[str],
    designation: str,
    marque: Optional[str],
) -> Optional[str]:
    """Cherche et télécharge l'image d'un produit.

    Pipeline : OFF (par EAN) → Bing Images → DuckDuckGo.
    Essaie chaque source jusqu'à ce qu'un téléchargement réussisse réellement
    (pas juste une URL trouvée) — évite les faux positifs.

    Returns: chemin relatif de l'image stockée, ou None.
    """
    img_dir = _get_products_img_dir()
    dest_path = os.path.join(img_dir, f"{product_id}.jpg")
    rel_path = f"products/epicerie/{product_id}.jpg"

    if os.path.isfile(dest_path):
        return rel_path

    if ean and _try_source(fetch_from_openfoodfacts(ean), dest_path, f"OFF(ean={ean})"):
        return rel_path

    query = _build_search_query(designation, marque)
    if query:
        if _try_source(fetch_from_bing(query), dest_path, f"Bing('{query[:40]}')"):
            return rel_path
        if _try_source(fetch_from_duckduckgo(query), dest_path, f"DDG('{query[:40]}')"):
            return rel_path

    return None


def fetch_images_batch(
    products: list[dict],
    delay: float = 0.5,
) -> dict[int, str]:
    """Fetch images pour un batch de produits.

    Args:
        products: list de dicts avec keys: id, ean, designation, marque
        delay: délai entre chaque requête (politeness)

    Returns: dict product_id → chemin relatif image
    """
    results: dict[int, str] = {}
    for i, p in enumerate(products):
        pid = p["id"]
        path = fetch_product_image(
            product_id=pid,
            ean=p.get("ean"),
            designation=p.get("designation", ""),
            marque=p.get("marque"),
        )
        if path:
            results[pid] = path
        if i < len(products) - 1:
            time.sleep(delay)
        if (i + 1) % 10 == 0:
            logger.info("Image fetch progress: %d/%d (%d found)", i + 1, len(products), len(results))
    return results
