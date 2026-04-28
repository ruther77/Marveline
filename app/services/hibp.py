"""Service HaveIBeenPwned k-anonymity — vérification mots de passe compromis.

Architecture (CaroCorp §7.2 NIVEAU 5) :
    - SHA-1 du mot de passe → préfixe 5 chars → GET api.pwnedpasswords.com/range/{prefix}
    - Header Add-Padding: true (anti-timing attack)
    - FAIL-OPEN : toute Exception → log WARNING + return False
    - Synchrone (httpx.Client) — auth.py est synchrone

Le mot de passe n'est JAMAIS envoyé sur le réseau, seulement le préfixe SHA-1 (5 chars).
"""
import hashlib
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

HIBP_API_BASE = "https://api.pwnedpasswords.com/range/"
_HIBP_TIMEOUT = 3.0
_HIBP_USER_AGENT = "CaroCorp-AuthService/1.0"


def is_password_compromised(plain_password: str) -> bool:
    """Vérifie si le mot de passe apparaît dans des leaks via k-anonymity SHA-1.

    Args:
        plain_password: Mot de passe en clair à vérifier.

    Returns:
        True si le mot de passe est présent dans la base HIBP, False sinon.
        Retourne aussi False sur toute erreur réseau/API (FAIL-OPEN).

    Security:
        - Seul le préfixe SHA-1 (5 chars) est transmis — k-anonymity garantie.
        - Header Add-Padding=true envoyé pour masquer le préfixe exact.
        - Timeout 3s — ne jamais bloquer le flux d'authentification.
    """
    sha1_hash = hashlib.sha1(
        plain_password.encode("utf-8"), usedforsecurity=False
    ).hexdigest().upper()
    prefix = sha1_hash[:5]
    suffix = sha1_hash[5:]

    try:
        with httpx.Client(
            timeout=_HIBP_TIMEOUT,
            headers={"User-Agent": _HIBP_USER_AGENT, "Add-Padding": "true"},
        ) as client:
            response = client.get(f"{HIBP_API_BASE}{prefix}")
            response.raise_for_status()

        for line in response.text.splitlines():
            parts = line.split(":")
            if len(parts) == 2 and parts[0] == suffix:
                return True
        return False

    except Exception:
        logger.warning(
            "HIBP API unavailable — password compromise check skipped (FAIL-OPEN)"
        )
        return False
