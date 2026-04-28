"""Validation securisee des fichiers uploades.

P2-16 : validation par magic bytes (pas Content-Type client).
P2-17 : sanitization CSV anti-formula injection.
P2-24 : limite taille avant lecture memoire.
"""
from fastapi import HTTPException

MAGIC_SIGNATURES = {
    b'\xff\xd8\xff': '.jpg',
    b'\x89PNG\r\n\x1a\n': '.png',
}
ALLOWED_EXTENSIONS = frozenset({'.jpg', '.jpeg', '.png', '.webp'})
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_CSV_ROWS = 10_000
FORMULA_CHARS = frozenset({'=', '+', '-', '@', '\t', '\r'})


def validate_image(content: bytes) -> str:
    """Valide image par magic bytes. Retourne extension reelle.

    Raises:
        HTTPException 413 si trop volumineux.
        HTTPException 400 si format non reconnu.
    """
    if len(content) > MAX_IMAGE_SIZE:
        raise HTTPException(413, detail=f"Fichier trop volumineux (max {MAX_IMAGE_SIZE // 1024 // 1024}MB)")

    for magic, ext in MAGIC_SIGNATURES.items():
        if content[:len(magic)] == magic:
            return ext

    # WebP : bytes 0-3 = RIFF, bytes 8-11 = WEBP
    if len(content) >= 12 and content[:4] == b'RIFF' and content[8:12] == b'WEBP':
        return '.webp'

    raise HTTPException(400, detail="Format image invalide. Acceptes : JPG, PNG, WebP")


def sanitize_csv_value(value: str) -> str:
    """Neutralise les formules CSV (=, +, @, -, tab, cr).

    Prefixe avec apostrophe pour empecher l'interpretation
    par Excel/LibreOffice comme formule.
    """
    if value and value[0] in FORMULA_CHARS:
        return "'" + value
    return value
