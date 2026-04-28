"""Tracker de marques candidates — apprentissage passif depuis le flux ETL.

Complément du brand_dictionary. Objectif : détecter automatiquement les
marques récurrentes que l'opérateur ne saisit pas explicitement mais qui
apparaissent systématiquement en première position de la désignation
(ex : "MOGU Mangue 24x32cl" → "MOGU" candidate).

Stratégie :
  1. À chaque import validé, extraire les tokens WORD initiaux de chaque
     désignation (position 0 ou 1, après filtrage quantités/multipliers).
  2. Incrémenter un compteur (token, categorie_code) → occurrences.
  3. Dès qu'un token atteint PROMOTION_THRESHOLD (≥3) dans ≥2 imports distincts
     avec la même catégorie dominante (≥70%), le promouvoir au brand_dictionary
     avec source="auto_promoted".

Persistance : data/brand_candidates.json. Le contenu ne vise pas à être
interprétable par l'utilisateur final — c'est une pile d'apprentissage.

Format interne :
  {
    "token": {
      "categories": {"BOIS_SODA": 5, "BOIS_JUS": 1},
      "import_ids": [123, 456, 789],
      "last_seen": "2026-04-22T19:30:00",
      "promoted": false,
    },
    ...
  }

Le nombre d'import_ids est limité à MAX_IMPORT_IDS pour éviter la croissance
linéaire.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

logger = logging.getLogger(__name__)

_CANDIDATES_PATH = Path(__file__).parent.parent.parent.parent / "data" / "brand_candidates.json"

# Seuils de promotion (conservateurs : mieux vaut rater que polluer)
PROMOTION_MIN_COUNT = 4            # ≥4 occurrences totales
PROMOTION_MIN_DISTINCT_IMPORTS = 3 # ≥3 imports distincts
PROMOTION_CAT_DOMINANCE = 0.85     # ≥85% d'occurrences partagent la cat
MAX_IMPORT_IDS = 20                # rolling window

# Stop-list : tokens qui ne doivent JAMAIS devenir des marques.
# Vocabulaire générique : aliments, AOC, cépages, emballages, variantes.
_STOP_TOKENS: frozenset[str] = frozenset({
    # Emballages / contenants / mesures
    "LOT", "PACK", "BOX", "UNITE", "UNITÉ", "UNIT", "BTE", "BOUT",
    "BOUTEILLE", "CAISSE", "CARTON", "CL", "ML", "L", "KG", "G",
    "POT", "CUBE", "SAC", "FILET", "BARQUETTE", "BOITE", "PLATEAU",
    "CONTENANT", "BIDON", "FUT", "FÛT", "CANETTE", "BRIQUE", "TETRA",
    # Mots génériques produit
    "PRODUIT", "ARTICLE", "REFERENCE", "SPECIAL", "PREMIUM", "STANDARD",
    "NATURE", "NATUREL", "BIO", "CLASSIQUE", "ORIGINAL", "ORIG",
    "FRAIS", "FROID", "CHAUD", "CRU", "CUIT", "SURGELE", "SURGELÉ",
    "IMPORT", "EXPORT", "GROS", "DETAIL", "VRAC", "EMBALLE",
    # Couleurs / variantes
    "ROUGE", "BLANC", "BLC", "RGE", "ROSE", "RSE", "NOIR", "VERT", "BLEU", "JAUNE",
    "DORE", "DORÉE", "BRUN", "CLAIR", "FONCE", "FONCÉ",
    # Catégories alimentaires génériques
    "JUS", "NECTAR", "SODA", "EAU", "BOISSON", "VIN", "BIERE", "BIÈRE",
    "PAIN", "PATE", "PATES", "RIZ", "FARINE", "SUCRE", "SEL", "POIVRE",
    "LAIT", "CREME", "CRÈME", "BEURRE", "YAOURT", "FROMAGE", "OEUF", "ŒUF",
    "HUILE", "VINAIGRE", "SAUCE", "EPICE", "MOUTARDE", "KETCHUP", "MAYO",
    "VIANDE", "POISSON", "POULET", "BOEUF", "BŒUF", "PORC", "AGNEAU", "VEAU",
    "CREVETTE", "CREVETTES", "SAUMON", "THON", "MORUE", "CABILLAUD",
    # Légumes / fruits
    "TOMATE", "TOMATES", "OIGNON", "OIGNONS", "POMME", "POMMES",
    "CAROTTE", "CAROTTES", "SALADE", "LAITUE", "CONCOMBRE", "POIVRON",
    "AUBERGINE", "COURGETTE", "HARICOT", "HARICOTS", "EPINARD", "EPINARDS",
    "CHOU", "POIREAU", "POIREAUX", "MAIS", "MAÏS", "PATATE",
    "ORANGE", "ORANGES", "CITRON", "CITRONS", "BANANE", "BANANES",
    "FRAISE", "FRAISES", "MANGUE", "MANGUES", "ANANAS", "GOYAVE",
    "BRIOCHE", "TRANCHE", "BAGUETTE", "MIE",
    # AOC / régions viticoles
    "BORDEAUX", "BOURGOGNE", "CHAMPAGNE", "CHABLIS", "SANCERRE", "POUILLY",
    "COTES", "CÔTES", "BUZET", "MEDOC", "MÉDOC", "SAINT", "STE", "ST",
    "LOIRE", "RHONE", "RHÔNE", "ALSACE", "JURA", "PROVENCE", "LANGUEDOC",
    "BEAUJOLAIS", "COGNAC", "ARMAGNAC",
    "IGP", "AOC", "AOP", "VDT", "VDP", "VIGNOBLE",
    # Cépages
    "CHARDONNAY", "SAUVIGNON", "MERLOT", "CABERNET", "SYRAH", "PINOT",
    "RIESLING", "GEWURZ", "MUSCADET", "VIOGNIER", "GRENACHE", "MALBEC",
    "CHENIN", "CARIGNAN", "MOURVEDRE", "MOURVÈDRE",
    # Géographie / adjectifs
    "FRANCE", "FRANCAIS", "FRANÇAIS", "ITALIE", "ITALIEN", "ESPAGNE", "ESPAGNOL",
    "ALLEMAGNE", "PORTUGAL", "MAROC", "TUNISIE", "SENEGAL", "COTE",
    # Non-alimentaires fréquents
    "JAVEL", "SAVON", "SHAMPOING", "LESSIVE", "GEL", "PAPIER",
    # Abréviations / lieux-dits viticoles
    "BTLE", "BTL", "MIL", "SOL", "TOUR", "PRIEURE", "PRIEURÉ",
    "CHATEAU", "CHÂTEAU", "DOMAINE", "CLOS", "MAS", "CAVE", "MAISON",
    # Formes / états
    "RONDELLE", "MORCEAU", "COPEAU", "POUDRE", "LIQUIDE",
    # Parties / morceaux d'animaux
    "PILON", "CUISSE", "AILE", "AILERON", "FILET", "ESCALOPE", "COTE",
    "CÔTE", "CÔTELETTE", "GIGOT", "ROTI", "RÔTI", "STEAK", "ENTRECOTE",
    "ENTRECÔTE", "CONTREFILET", "FAUX", "JARRET", "CULOTTE", "POITRINE",
    "MANCHON", "GESIER", "GÉSIER", "COEUR", "CŒUR", "FOIE",
    # Langues étrangères fréquentes (non-marques)
    "MILK", "BEER", "GINGER", "WATER", "FRESH", "NEW", "OLD",
    # Dérivés d'aliments
    "MANIOC", "IGNAME", "ATTIÉKÉ", "ATTIEKE", "FONIO", "SEMOULE",
    "COUSCOUS", "BOULGOUR", "QUINOA", "POLENTA", "TAPIOCA",
    "PIMENT", "PIMENTS", "GINGEMBRE", "CURCUMA", "CUMIN",
    "PLANTAIN", "PLANTAINS", "AUBERGINES", "GOMBO", "GOMBOS",
    # Adjectifs / états produit
    "CONCENTRE", "CONCENTRÉ", "CONCENTREE", "CONCENTRÉE",
    "LIQUIDE", "SOLIDE", "PATEUX", "EMINCE", "ÉMINCÉ", "HACHE", "HACHÉ",
    "AROME", "ARÔME", "AROMATISE", "AROMATISÉ", "PARFUM", "PARFUMÉ",
    # Unités / packaging avec chiffre (fallback)
    "4KG", "5KG", "10KG", "20KG", "25KG", "1L", "2L", "5L", "10L",
    # Unités administratives 1 lettre
    "P", "R", "N", "M", "U",
})

_STOP_PREFIXES: tuple[str, ...] = (
    "CONFIT", "PUREE", "PURÉE", "SOUPE", "BOUILLON",
    "GATEAU", "GÂTEAU", "BISCUIT", "CROUTON", "CROÛTON",
    "SORBET", "GLACE", "YOGHURT",
)


def _is_stop_prefix(token: str) -> bool:
    for p in _STOP_PREFIXES:
        if token == p or token.startswith(p):
            return True
    return False


def _is_valid_candidate(token: str) -> bool:
    t = token.strip().upper()
    if not t or len(t) < 3:  # 2 chars = souvent du bruit (PP, LL, NN)
        return False
    if t in _STOP_TOKENS:
        return False
    if _is_stop_prefix(t):
        return False
    # Rejeter les tokens purement numériques (1-3 chiffres : bruit)
    if t.isdigit() and len(t) < 4:
        return False
    # Rejeter les tokens mix lettre + chiffre (probablement packaging type "6X33CL")
    if any(c.isdigit() for c in t) and any(c.isalpha() for c in t):
        digit_run = sum(1 for c in t if c.isdigit())
        if digit_run >= 2:
            return False
    return True


def _extract_first_tokens(designation: str, max_pos: int = 2) -> list[str]:
    """Retourne les tokens des max_pos premières positions, en majuscules."""
    out: list[str] = []
    for chunk in (designation or "").strip().split()[:max_pos]:
        t = chunk.upper().strip(".,;:()[]/")
        if _is_valid_candidate(t):
            out.append(t)
    return out


class BrandCandidates:
    """Pile d'apprentissage passif des marques candidates."""

    def __init__(self) -> None:
        self._data: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if not _CANDIDATES_PATH.exists():
            return
        try:
            with open(_CANDIDATES_PATH) as f:
                self._data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Brand candidates load failed: %s", e)
            self._data = {}

    def save(self) -> None:
        _CANDIDATES_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_CANDIDATES_PATH, "w") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False, sort_keys=True)

    def record(
        self,
        designation: str,
        categorie_code: Optional[str],
        import_id: Optional[int],
    ) -> None:
        """Enregistre les candidats d'une ligne validée."""
        if not categorie_code or categorie_code == "AUTRE":
            return
        for token in _extract_first_tokens(designation):
            entry = self._data.setdefault(token, {
                "categories": {},
                "import_ids": [],
                "last_seen": None,
                "promoted": False,
            })
            if entry.get("promoted"):
                continue
            entry["categories"][categorie_code] = entry["categories"].get(categorie_code, 0) + 1
            if import_id is not None and import_id not in entry["import_ids"]:
                entry["import_ids"].append(import_id)
                # Rolling window pour éviter croissance linéaire
                if len(entry["import_ids"]) > MAX_IMPORT_IDS:
                    entry["import_ids"] = entry["import_ids"][-MAX_IMPORT_IDS:]
            entry["last_seen"] = datetime.utcnow().isoformat(timespec="seconds")

    def promote_ready(self) -> list[tuple[str, str]]:
        """Retourne les candidats prêts à être promus (non encore promus).

        Liste de (token, categorie_code_dominante).
        """
        ready: list[tuple[str, str]] = []
        for token, entry in self._data.items():
            if entry.get("promoted"):
                continue
            cats = entry.get("categories", {})
            total = sum(cats.values())
            if total < PROMOTION_MIN_COUNT:
                continue
            if len(entry.get("import_ids", [])) < PROMOTION_MIN_DISTINCT_IMPORTS:
                continue
            # Catégorie dominante
            best_cat, best_count = max(cats.items(), key=lambda x: x[1])
            if best_count / total < PROMOTION_CAT_DOMINANCE:
                continue
            ready.append((token, best_cat))
        return ready

    def mark_promoted(self, token: str) -> None:
        entry = self._data.get(token)
        if entry is not None:
            entry["promoted"] = True

    def record_batch(self, lignes: Iterable[dict], import_id: Optional[int]) -> None:
        """Enregistre un batch de lignes d'un import validé."""
        for ligne in lignes:
            if not isinstance(ligne, dict):
                continue
            # Si la marque est déjà renseignée, on n'enrichit pas les candidats
            # (on suppose que l'opérateur a déjà désigné explicitement).
            if ligne.get("marque"):
                continue
            desig = ligne.get("designation") or ligne.get("designation_raw") or ""
            self.record(desig, ligne.get("categorie_code"), import_id)

    @property
    def size(self) -> int:
        return len(self._data)

    def stats(self) -> dict:
        """Statistiques pour audit / dashboard."""
        promoted = sum(1 for e in self._data.values() if e.get("promoted"))
        return {
            "total": self.size,
            "promoted": promoted,
            "pending": self.size - promoted,
            "ready_for_promotion": len(self.promote_ready()),
        }


# Singleton
_instance: Optional[BrandCandidates] = None


def get_brand_candidates() -> BrandCandidates:
    global _instance
    if _instance is None:
        _instance = BrandCandidates()
    return _instance


def run_promotion_cycle() -> int:
    """Exécute un cycle de promotion : candidats prêts → brand_dictionary.

    Retourne le nombre de marques promues. À appeler après chaque import
    validé ou via un cron.
    """
    from scripts.etl.parsers.brand_dictionary import get_brand_dictionary

    cands = get_brand_candidates()
    bd = get_brand_dictionary()
    promoted = 0
    for token, cat in cands.promote_ready():
        # Double-check : ne pas promouvoir si déjà dans le dict par ailleurs
        if bd.contains(token):
            cands.mark_promoted(token)
            continue
        if bd.add(token, [cat], source="auto_promoted"):
            cands.mark_promoted(token)
            promoted += 1
    if promoted > 0:
        bd.save()
        cands.save()
        logger.info("Brand auto-promotion: %d new brands added", promoted)
    else:
        # Toujours sauver pour persister les mark_promoted (dédup)
        cands.save()
    return promoted
