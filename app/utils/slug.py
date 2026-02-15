"""Utilitaire de generation de slugs URL-safe."""
import re
import unicodedata


def slugify(name: str) -> str:
    """Genere un slug URL-safe depuis un nom.

    Normalise: lowercase, accents supprimes, espaces et tirets convertis
    en underscores, caracteres speciaux supprimes.

    Args:
        name: Nom a convertir en slug

    Returns:
        Slug normalise

    Examples:
        >>> slugify("Vaisselle Service")
        'vaisselle_service'
        >>> slugify("Decoration Noel")
        'decoration_noel'
        >>> slugify("Mange-debout")
        'mange_debout'
        >>> slugify("  Candy  Bar  ")
        'candy_bar'
    """
    # Normaliser unicode (NFD decompose les accents)
    normalized = unicodedata.normalize("NFD", name)
    # Supprimer les diacritiques (accents)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    # Lowercase
    lower = ascii_text.lower()
    # Remplacer espaces, tirets et caracteres non-alphanumeriques par underscore
    slug = re.sub(r"[^a-z0-9]+", "_", lower)
    # Supprimer underscores en debut/fin
    slug = slug.strip("_")
    # Reduire underscores multiples
    slug = re.sub(r"_+", "_", slug)
    return slug
