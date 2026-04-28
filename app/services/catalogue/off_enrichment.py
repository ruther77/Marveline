"""Enrichissement EAN via OpenFoodFacts (API publique).

Source externe `off_import` déclarée dans AutoFillBadge.tsx mais jamais
implémentée avant ce module. Objectif : pour les lignes TAIYAT/EUROCIEL/ETHAN
avec marque+désignation connus mais sans EAN, interroger OFF pour récupérer
un EAN probable.

Contraintes respectées :
  - Rate limit : ~10 req/min par défaut (conservateur, OFF accepte 100/min)
  - Cache Redis 30 jours par (marque, query) normalisés
  - Timeout court (3s) — best-effort, n'échoue jamais silencieusement
  - Skip si marque ou désignation vide (pas la peine d'interroger)
  - Retourne None si aucun résultat fiable (score < 0.5 sur popularité OFF)

API OFF : https://wiki.openfoodfacts.org/API/Read/Search
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import unicodedata
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────────────

_OFF_SEARCH_URL = "https://search.openfoodfacts.org/search"
_OFF_PRODUCT_URL = "https://world.openfoodfacts.org/api/v2/product"
_OFF_USER_AGENT = "CaroCorp/1.0 (+https://futurproj.local)"

_CACHE_TTL_SECONDS = 30 * 24 * 3600  # 30 jours
_CACHE_PREFIX = "off:search:v1:"
_HTTP_TIMEOUT_SECONDS = 3.0
_MIN_POPULARITY_SCORE = 1  # produit OFF avec ≥1 scan pour considérer fiable


def _normalize_cache_key(marque: str, query: str) -> str:
    nfd = unicodedata.normalize("NFD", f"{marque}|{query}".lower())
    ascii_only = nfd.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9|]+", "_", ascii_only)[:160]


# ── Cache Redis best-effort ──────────────────────────────────────────────────

async def _cache_get(key: str) -> Optional[dict]:
    try:
        from app.core.redis import get_redis_client
        client = await get_redis_client()
        if client is None:
            return None
        raw = await client.get(_CACHE_PREFIX + key)
        if raw is None:
            return None
        return json.loads(raw if isinstance(raw, str) else raw.decode())
    except Exception as exc:
        logger.debug("OFF cache get failed: %s", exc)
        return None


async def _cache_set(key: str, value: dict) -> None:
    try:
        from app.core.redis import get_redis_client
        client = await get_redis_client()
        if client is None:
            return
        await client.set(
            _CACHE_PREFIX + key, json.dumps(value),
            ex=_CACHE_TTL_SECONDS,
        )
    except Exception as exc:
        logger.debug("OFF cache set failed: %s", exc)


# ── Appel API ────────────────────────────────────────────────────────────────


async def _search_off(marque: str, query: str) -> Optional[dict]:
    """Interroge l'endpoint v2 OFF search. Retourne le meilleur produit ou None.

    L'endpoint v1 `/cgi/search.pl` de world.openfoodfacts.org est devenu
    instable (503 fréquents). On utilise v2 search.openfoodfacts.org qui
    est plus rapide et fiable.
    """
    params = {
        "q": f"{marque} {query}".strip(),
        "page_size": 10,
    }
    try:
        async with httpx.AsyncClient(
            timeout=_HTTP_TIMEOUT_SECONDS,
            headers={"User-Agent": _OFF_USER_AGENT},
        ) as client:
            response = await client.get(_OFF_SEARCH_URL, params=params)
            if response.status_code != 200:
                return None
            data = response.json()
    except (httpx.HTTPError, asyncio.TimeoutError, json.JSONDecodeError) as exc:
        logger.debug("OFF search failed for %r %r: %s", marque, query, exc)
        return None

    # v2 renvoie "hits", chaque hit a : code, product_name, brands (list|str),
    # unique_scans_n éventuellement, scans_n, popularity_key.
    hits = data.get("hits") or []
    if not hits:
        return None

    marque_norm = marque.strip().upper()
    best = None
    best_score = -1
    for p in hits:
        code = p.get("code")
        if not code or not re.fullmatch(r"\d{8,14}", str(code)):
            continue
        scans = int(p.get("unique_scans_n") or p.get("scans_n") or 0)
        # On accepte scans=0 en fallback pour marques rares (score plus faible)
        raw_brands = p.get("brands") or ""
        if isinstance(raw_brands, list):
            brands = " ".join(raw_brands).upper()
        else:
            brands = str(raw_brands).upper()
        if marque_norm not in brands:
            continue
        score = scans if scans > 0 else 0
        if score > best_score:
            best_score = score
            best = {
                "ean": str(code),
                "product_name": p.get("product_name") or "",
                "brands": brands,
                "scans": scans,
            }
    return best


# ── Interface publique ───────────────────────────────────────────────────────


async def find_ean_by_brand_and_designation(
    marque: Optional[str],
    designation: Optional[str],
) -> Optional[dict]:
    """Cherche un EAN plausible dans OpenFoodFacts.

    Args:
        marque: Marque du produit (ex: "MAGGI"). Required.
        designation: Désignation textuelle (ex: "arome 100g"). Required.

    Returns:
        {"ean": "3033710074617", "source": "off", "score": 0.85,
         "product_name": "Arôme Maggi", "scans": 42} si trouvé, sinon None.
    """
    if not marque or not designation:
        return None
    marque = marque.strip()
    designation = designation.strip()
    if len(marque) < 2 or len(designation) < 3:
        return None

    cache_key = _normalize_cache_key(marque, designation)

    # Lookup cache
    cached = await _cache_get(cache_key)
    if cached is not None:
        # Négatifs cachés aussi ({}) pour éviter de re-hammer OFF
        return cached or None

    result = await _search_off(marque, designation)
    if result is None:
        await _cache_set(cache_key, {})  # cache négatif
        return None

    enriched = {
        "ean": result["ean"],
        "source": "off",
        "score": min(1.0, 0.5 + 0.05 * result["scans"]),  # capé à 1.0
        "product_name": result["product_name"],
        "scans": result["scans"],
    }
    await _cache_set(cache_key, enriched)
    return enriched


async def batch_enrich_lignes_with_off(
    lignes: list, max_lookups: int = 20,
) -> int:
    """Enrichit les lignes (list[dict] JSONB ou list[LigneParsee]) avec OFF.

    Ne touche QUE les lignes sans EAN qui ont marque+désignation.
    Limite le nb d'appels OFF (rate limit) via `max_lookups`.
    Retourne le nb de lignes enrichies.

    Best-effort : une erreur réseau n'interrompt pas l'enrichissement.
    """
    filled = 0
    lookups = 0
    for l in lignes:
        if lookups >= max_lookups:
            break
        is_dict = isinstance(l, dict)
        ean = l.get("ean") if is_dict else getattr(l, "ean", None)
        marque = l.get("marque") if is_dict else getattr(l, "marque", None)
        desig = l.get("designation") if is_dict else getattr(l, "designation", None)
        if ean or not marque or not desig:
            continue

        lookups += 1
        try:
            result = await find_ean_by_brand_and_designation(marque, desig)
        except Exception as exc:
            logger.debug("OFF batch enrich failed on line: %s", exc)
            continue

        if result is None:
            continue

        new_ean = result["ean"]
        if is_dict:
            l["ean"] = new_ean
            meta = l.setdefault("auto_applied_fields", {}) or {}
            if not isinstance(meta, dict):
                meta = {}
            meta["ean"] = {
                "source": "off_import",
                "score": result["score"],
                "candidate_id": None,
                "candidate_designation": result.get("product_name") or "",
            }
            l["auto_applied_fields"] = meta
        else:
            l.ean = new_ean
            meta = getattr(l, "auto_applied_fields", None) or {}
            meta["ean"] = {
                "source": "off_import",
                "score": result["score"],
                "candidate_id": None,
                "candidate_designation": result.get("product_name") or "",
            }
            l.auto_applied_fields = meta
        filled += 1

    if lookups > 0:
        logger.info(
            "OFF enrichment: %d EAN found / %d lookups / %d lines",
            filled, lookups, len(lignes),
        )
    return filled
