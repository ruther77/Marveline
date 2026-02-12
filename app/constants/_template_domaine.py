"""Template pour créer un nouveau domaine de constantes.

INSTRUCTIONS :
1. Copier ce fichier vers app/constants/nouveau_domaine.py
2. Remplacer "NomDomaine" par le nom approprié (ex: Notifications, Emails, Files)
3. Définir les Enums/classes de constantes
4. Ajouter les exports dans __all__
5. Importer dans app/constants/__init__.py
6. Tester les imports

EXEMPLE D'USAGE :
    from app.constants import MonEnum
    valeur = MonEnum.VALEUR1
"""

from enum import Enum


# ═══════════════════════════════════════════════════════════════════════════
# ENUMS DU DOMAINE
# ═══════════════════════════════════════════════════════════════════════════


class MonEnum(str, Enum):
    """Description de l'Enum.

    Utilisé dans :
        - models.MonModele.mon_champ
        - schemas.MonSchema.mon_champ
        - services.MonService (transitions de statut)
    """

    VALEUR1 = "valeur1"
    VALEUR2 = "valeur2"
    VALEUR3 = "valeur3"


class MonAutreEnum(str, Enum):
    """Description de l'autre Enum.

    Workflow (si applicable) :
        ETAT1 → ETAT2 → ETAT3

    Utilisé dans :
        - models.MonModele.autre_champ
    """

    ETAT1 = "etat1"
    ETAT2 = "etat2"
    ETAT3 = "etat3"


# ═══════════════════════════════════════════════════════════════════════════
# CLASSES DE CONSTANTES (si applicable)
# ═══════════════════════════════════════════════════════════════════════════


class MesConstantes:
    """Constantes non-Enum du domaine.

    Usage :
        valeur = MesConstantes.MA_CONSTANTE
    """

    MA_CONSTANTE = "valeur_constante"
    AUTRE_CONSTANTE = 42

    @staticmethod
    def generer_cle(param: str) -> str:
        """Helper pour générer une clé composite."""
        return f"prefixe:{param}"


# ═══════════════════════════════════════════════════════════════════════════
# EXPORTS
# ═══════════════════════════════════════════════════════════════════════════

__all__ = [
    "MonEnum",
    "MonAutreEnum",
    "MesConstantes",
]
