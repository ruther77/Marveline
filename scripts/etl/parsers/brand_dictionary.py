"""Brand dictionary vivant — marques alimentaires avec apprentissage.

Architecture :
  - Marques multi-mots ("RED BULL", "JACK DANIEL'S", "COCA COLA")
  - Marque → set de catégories (GILBERT peut être BOIS_JUS et COND_SAUCE)
  - Auto-enrichissement à chaque import validé
  - Persistance JSON dans data/brand_dictionary.json

Le dictionnaire est le composant transversal qui irrigue toute la chaîne ETL :
  parser → tokenizer → classification → déduplication.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_DICT_PATH = Path(__file__).parent.parent.parent.parent / "data" / "brand_dictionary.json"

# ── Seed : marques connues multi-catégories ──────────────────────────────────

SEED_BRANDS: dict[str, list[str]] = {
    # Bières
    "1664": ["ALC_BIERE"],
    "86": ["ALC_BIERE"],
    "33 EXPORT": ["ALC_BIERE"],
    "HEINEKEN": ["ALC_BIERE"],
    "KRONENBOURG": ["ALC_BIERE"],
    "LEFFE": ["ALC_BIERE"],
    "GRIMBERGEN": ["ALC_BIERE"],
    "STELLA ARTOIS": ["ALC_BIERE"],
    "CORONA": ["ALC_BIERE"],
    "DESPERADOS": ["ALC_BIERE"],
    "AFFLIGEM": ["ALC_BIERE"],
    "BUDWEISER": ["ALC_BIERE"],
    "CARLSBERG": ["ALC_BIERE"],
    "GUINNESS": ["ALC_BIERE"],
    "HOEGAARDEN": ["ALC_BIERE"],
    "JUPILER": ["ALC_BIERE"],
    "PELFORTH": ["ALC_BIERE"],
    "FISCHER": ["ALC_BIERE"],
    "AMSTEL": ["ALC_BIERE"],
    "BECK": ["ALC_BIERE"],
    "TUBORG": ["ALC_BIERE"],
    "HINANO": ["ALC_BIERE"],
    "NUMBER ONE": ["ALC_BIERE"],
    "PRIMUS": ["ALC_BIERE"],
    "MANTA": ["ALC_BIERE"],
    "SUPER BOCK": ["ALC_BIERE"],
    "PERONI": ["ALC_BIERE"],
    "SKOL": ["ALC_BIERE"],
    # Spiritueux
    "JACK DANIEL'S": ["ALC_SPIRITUEUX"],
    "ABSOLUT": ["ALC_SPIRITUEUX"],
    "SMIRNOFF": ["ALC_SPIRITUEUX"],
    "GREY GOOSE": ["ALC_SPIRITUEUX"],
    "BACARDI": ["ALC_SPIRITUEUX"],
    "CAPTAIN MORGAN": ["ALC_SPIRITUEUX"],
    "HAVANA CLUB": ["ALC_SPIRITUEUX"],
    "MALIBU": ["ALC_SPIRITUEUX"],
    "BALLANTINE'S": ["ALC_SPIRITUEUX"],
    "JOHNNIE WALKER": ["ALC_SPIRITUEUX"],
    "CHIVAS": ["ALC_SPIRITUEUX"],
    "GLENFIDDICH": ["ALC_SPIRITUEUX"],
    "HENNESSY": ["ALC_SPIRITUEUX"],
    "COURVOISIER": ["ALC_SPIRITUEUX"],
    "REMY MARTIN": ["ALC_SPIRITUEUX"],
    "MARTELL": ["ALC_SPIRITUEUX"],
    "CIROC": ["ALC_SPIRITUEUX"],
    "BELVEDERE": ["ALC_SPIRITUEUX"],
    "POLIAKOV": ["ALC_SPIRITUEUX"],
    "ERISTOFF": ["ALC_SPIRITUEUX"],
    "BOMBAY": ["ALC_SPIRITUEUX"],
    "TANQUERAY": ["ALC_SPIRITUEUX"],
    "HENDRICK'S": ["ALC_SPIRITUEUX"],
    "BEEFEATER": ["ALC_SPIRITUEUX"],
    "JAGERMEISTER": ["ALC_SPIRITUEUX"],
    "GET 27": ["ALC_SPIRITUEUX"],
    "GET": ["ALC_SPIRITUEUX"],
    "RICARD": ["ALC_SPIRITUEUX"],
    "PASTIS 51": ["ALC_SPIRITUEUX"],
    "BAILEYS": ["ALC_SPIRITUEUX"],
    "COINTREAU": ["ALC_SPIRITUEUX"],
    "GRAND MARNIER": ["ALC_SPIRITUEUX"],
    "LA MAUNY": ["ALC_SPIRITUEUX"],
    "LM": ["ALC_SPIRITUEUX"],
    # Champagne / vins
    "MOET": ["ALC_CHAMPAGNE"],
    "VEUVE CLICQUOT": ["ALC_CHAMPAGNE"],
    "DOM PERIGNON": ["ALC_CHAMPAGNE"],
    "RUINART": ["ALC_CHAMPAGNE"],
    "TAITTINGER": ["ALC_CHAMPAGNE"],
    "MUMM": ["ALC_CHAMPAGNE"],
    "NICOLAS FEUILLATTE": ["ALC_CHAMPAGNE"],
    # Sodas
    "COCA COLA": ["BOIS_SODA"],
    "PEPSI": ["BOIS_SODA"],
    "FANTA": ["BOIS_SODA"],
    "SPRITE": ["BOIS_SODA"],
    "ORANGINA": ["BOIS_SODA"],
    "SCHWEPPES": ["BOIS_SODA"],
    "7UP": ["BOIS_SODA"],
    "OASIS": ["BOIS_SODA"],
    "CAPRI SUN": ["BOIS_SODA"],
    "CAPRISUN": ["BOIS_SODA"],
    "RED BULL": ["BOIS_ENERG"],
    "MONSTER": ["BOIS_ENERG"],
    "POWERADE": ["BOIS_ENERG"],
    # Eaux
    "EVIAN": ["BOIS_EAU"],
    "VOLVIC": ["BOIS_EAU"],
    "VITTEL": ["BOIS_EAU"],
    "CRISTALINE": ["BOIS_EAU"],
    "BADOIT": ["BOIS_EAU"],
    "PERRIER": ["BOIS_EAU"],
    "SAN PELLEGRINO": ["BOIS_EAU"],
    "SAN PELL": ["BOIS_EAU"],
    # Jus — marques multi-catégories
    "TROPICANA": ["BOIS_JUS"],
    "JOKER": ["BOIS_JUS"],
    "GILBERT": ["BOIS_JUS", "BOIS_SIROP", "COND_SAUCE"],
    "MAAZA": ["BOIS_JUS"],
    # Snacks / confiserie
    "KINDER": ["SUCR_BONBON", "SUCR_CHOCO"],
    "LAY'S": ["SNACK_CHIPS"],
    "LAYS": ["SNACK_CHIPS"],
    "MALABAR": ["SUCR_BONBON"],
    "ROCHAMBEAU": ["SUCR_GATEAU", "CONS_LEGUME", "BOUL_PAIN", "SUCR_BONBON"],
    "ROCH": ["SUCR_GATEAU", "CONS_LEGUME", "BOUL_PAIN", "SUCR_BONBON"],
    "TRANCHE DOREE": ["BOUL_PAIN"],
    "KER SUZEL": ["SUCR_GATEAU", "SUCR_BISC"],
    # Eaux privées METRO
    "ROCHE DES ECRINS": ["BOIS_EAU"],
    "ROCHES DES ECRINS": ["BOIS_EAU"],
    # Condiments
    "BALEINE": ["COND_SEL"],
    "HEINZ": ["COND_SAUCE"],
    "AMORA": ["COND_SAUCE"],
    "MAILLE": ["COND_SAUCE"],
    "MAUREL": ["COND_HUILE"],
    # Laitiers
    "PRESIDENT": ["LAIT_FROMAGE"],
    # Chocolat
    "NUTELLA": ["SUCR_CONF"],
    "NESTLE": ["BOIS_CHOCO", "SUCR_CHOCO", "SURG_GLACE"],
    # Café
    "NESPRESSO": ["BOIS_CAFE"],
    "DOLCE GUSTO": ["BOIS_CAFE"],
    "SENSEO": ["BOIS_CAFE"],
    # Marque propre METRO — catégorie résolue par contexte produit, pas par marque
    "MARQUE COMMUNE": ["_PRIVATE_LABEL"],
    "ARO": ["_PRIVATE_LABEL"],
    "MPRO": ["_PRIVATE_LABEL"],
    "METRO PROFESSIONAL": ["_PRIVATE_LABEL"],
    "METRO CHEF": ["_PRIVATE_LABEL"],
    # ── Marques TAIYAT (produits asiatiques/africains) ────────────────────
    "STARLING": ["BOIS_THE"],
    "NOLLENS": ["FRAIS_VOLAILLE"],
    "ZWAN": ["FRAIS_VOLAILLE", "FRAIS_CHARCUT"],
    "VAN BEL": ["FRAIS_VOLAILLE"],
    "VIVA": ["LAIT_FROMAGE"],
    "EXETER": ["FRAIS_VOLAILLE", "CONSERVE_VIANDE"],
    "ANNY": ["CONSERVE_POISSON"],
    "WESTCOAST": ["FROID_POIS"],
    "GOLDEN RIVER": ["NON_ALI_DROGUERIE"],
    "DE RICA": ["COND_SAUCE"],
    "MAMA-AFRICA": ["MONDE_AFRIQUE"],
    "MOGU": ["BOIS_SODA"],
    "BEGUE": ["MONDE_AFRIQUE"],
    "AROMA": ["COND_SAUCE"],
    # ── Marques ETHAN (boissons ethniques/soda) ───────────────────────────
    "VIMTO": ["BOIS_SODA"],
    "MINUTE MAID": ["BOIS_JUS"],
    "HAWAI": ["BOIS_SODA"],
    "CAMBODGE": ["BOIS_SODA"],
    "LOTUS": ["SUCR_FARINE"],
    "AKASH": ["SUCR_FARINE"],
    "TAS": ["BOIS_SODA"],
    "COCA ZERO": ["BOIS_SODA"],
    "OASIS": ["BOIS_SODA"],
    "SCHWEPPES": ["BOIS_SODA"],
    "MOGU": ["BOIS_SODA"],
    "CRISTALLINE": ["BOIS_EAU"],
    "MAAZA": ["BOIS_JUS"],
    "TILDA": ["SUCR_FARINE"],
    "FAMILY ELEPHANT": ["SUCR_FARINE"],
    "COCA CHERRY": ["BOIS_SODA"],
    "COCA": ["BOIS_SODA"],
}


class BrandEntry:
    """Entrée du dictionnaire : marque → catégories possibles + compteur d'usage."""

    __slots__ = ("categories", "usage_count", "source")

    def __init__(self, categories: list[str], source: str = "seed") -> None:
        self.categories = list(categories)
        self.usage_count = 0
        self.source = source

    def primary_category(self) -> Optional[str]:
        """Retourne la catégorie la plus probable (première)."""
        return self.categories[0] if self.categories else None

    def matches_category(self, cat: str) -> bool:
        return cat in self.categories

    def to_dict(self) -> dict:
        return {
            "categories": self.categories,
            "usage_count": self.usage_count,
            "source": self.source,
        }

    @staticmethod
    def from_dict(d: dict) -> "BrandEntry":
        entry = BrandEntry(d.get("categories", []), d.get("source", "loaded"))
        entry.usage_count = d.get("usage_count", 0)
        return entry


class BrandDictionary:
    """Dictionnaire vivant de marques alimentaires."""

    def __init__(self) -> None:
        self._brands: dict[str, BrandEntry] = {}
        # Index inversé pour lookup rapide multi-mots
        self._first_word_index: dict[str, list[str]] = {}
        # Charger seed puis fichier persisté
        for name, cats in SEED_BRANDS.items():
            self._brands[name.upper()] = BrandEntry(cats, source="seed")
        self._load()
        self._rebuild_index()

    def _rebuild_index(self) -> None:
        """Reconstruit l'index du premier mot pour le matching multi-mots."""
        self._first_word_index.clear()
        for name in self._brands:
            first = name.split()[0] if " " in name else name
            self._first_word_index.setdefault(first, []).append(name)
        # Trier par longueur décroissante (match le plus long d'abord)
        for key in self._first_word_index:
            self._first_word_index[key].sort(key=len, reverse=True)

    def _load(self) -> None:
        if not _DICT_PATH.exists():
            return
        try:
            with open(_DICT_PATH) as f:
                data = json.load(f)
            for name, entry_data in data.items():
                upper = name.upper()
                if isinstance(entry_data, dict):
                    self._brands[upper] = BrandEntry.from_dict(entry_data)
                elif isinstance(entry_data, str):
                    # Ancien format : brand → single category
                    self._brands[upper] = BrandEntry([entry_data], source="migrated")
                elif isinstance(entry_data, list):
                    self._brands[upper] = BrandEntry(entry_data, source="loaded")
            logger.debug("Brand dictionary loaded: %d entries", len(self._brands))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Brand dictionary load failed: %s", e)

    def save(self) -> None:
        _DICT_PATH.parent.mkdir(parents=True, exist_ok=True)
        data = {name: entry.to_dict() for name, entry in sorted(self._brands.items())}
        with open(_DICT_PATH, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, sort_keys=True)

    # ── Lookup ────────────────────────────────────────────────────────────

    def lookup(self, token: str) -> Optional[BrandEntry]:
        """Lookup exact d'un token (1 mot)."""
        return self._brands.get(token.upper())

    def lookup_multiword(self, tokens: list[str], start_idx: int) -> Optional[tuple[str, BrandEntry, int]]:
        """Essaie de matcher une marque multi-mots à partir de start_idx.

        Retourne (nom_marque, entry, nb_tokens_consommés) ou None.
        Teste les marques les plus longues d'abord (greedy).
        """
        if start_idx >= len(tokens):
            return None
        first = tokens[start_idx].upper()
        candidates = self._first_word_index.get(first, [])
        for brand_name in candidates:
            brand_words = brand_name.split()
            n = len(brand_words)
            if start_idx + n > len(tokens):
                continue
            window = " ".join(t.upper() for t in tokens[start_idx:start_idx + n])
            if window == brand_name:
                entry = self._brands[brand_name]
                entry.usage_count += 1
                return brand_name, entry, n
        return None

    def contains(self, token: str) -> bool:
        return token.upper() in self._brands

    def as_frozenset(self) -> frozenset[str]:
        """Noms de marques (1 mot, non-numériques) pour le tokenizer.

        Les marques numériques (1664, 86) sont exclues du frozenset car
        le tokenizer les traite via NUMERIC → détection marque en position 0 dans core.py.
        """
        return frozenset(
            name for name in self._brands
            if " " not in name and not name.isdigit()
        )

    def multiword_first_words(self) -> frozenset[str]:
        """Premiers mots des marques multi-mots (pour déclencher le lookup)."""
        return frozenset(
            name.split()[0] for name in self._brands if " " in name
        )

    def resolve_category(
        self,
        brand_name: str,
        context_tokens: list[str],
    ) -> Optional[str]:
        """Résout la catégorie d'une marque en fonction du contexte.

        Pour les marques multi-catégories (GILBERT → BOIS_JUS ou COND_SAUCE),
        utilise les tokens voisins pour désambiguïser.
        """
        entry = self._brands.get(brand_name.upper())
        if entry is None:
            return None
        if len(entry.categories) == 1:
            return entry.categories[0]

        # Désambiguïsation par contexte : chercher des keywords
        ctx = " ".join(t.lower() for t in context_tokens)
        # Mapping contexte → catégorie préférée
        _CONTEXT_HINTS: list[tuple[list[str], str]] = [
            (["mayo", "mayonnaise", "sauce", "ketchup", "moutarde", "vinaigre"], "COND_SAUCE"),
            (["sirop", "grenadine", "menthe", "fraise", "orgeat"], "BOIS_SIROP"),
            (["sucre", "buchette", "cassonade", "sucr"], "SUCR_SUCRE"),
            (["jus", "nectar", "ananas", "orange", "pomme", "banane", "tropical", "mangue", "goyave", "abricot"], "BOIS_JUS"),
            (["cafe", "expresso", "cappuccino", "latte", "lungo"], "BOIS_CAFE"),
            (["glace", "sorbet", "bac"], "SURG_GLACE"),
            (["chocolat", "cacao", "praline"], "SUCR_CHOCO"),
            (["sucre", "buchette", "cassonade"], "SUCR_SUCRE"),
            # Désambiguïsation ROCH/ROCHAMBEAU multi-catégories
            (["mais", "haricot", "epinard", "legume", "tomate conserve"], "CONS_LEGUME"),
            (["pain", "mie", "brioche", "baguette", "chocolat pain"], "BOUL_PAIN"),
            (["crocodile", "bonbon", "dragee", "confiserie", "sucette"], "SUCR_BONBON"),
            (["gateau", "cake", "barre", "marbr", "palet"], "SUCR_GATEAU"),
        ]
        for keywords, cat in _CONTEXT_HINTS:
            if cat in entry.categories and any(kw in ctx for kw in keywords):
                return cat

        return entry.primary_category()

    # ── Enrichissement ────────────────────────────────────────────────────

    def add(self, brand: str, categories: list[str], source: str = "auto") -> bool:
        upper = brand.upper()
        if upper in self._brands:
            # Ajouter les nouvelles catégories
            existing = self._brands[upper]
            added = False
            for cat in categories:
                if cat not in existing.categories:
                    existing.categories.append(cat)
                    added = True
            return added
        self._brands[upper] = BrandEntry(categories, source=source)
        self._rebuild_index()
        return True

    def enrich_from_validated_product(
        self,
        designation: str,
        categorie_code: Optional[str],
    ) -> int:
        """Auto-enrichissement après validation d'un produit.

        Ajoute les tokens numériques ≥2 chars comme marques potentielles.
        """
        # L'auto-enrichissement numérique est désactivé — les marques
        # numériques (1664, 86) sont dans le seed. Les nombres auto-détectés
        # (50, 100, 250) sont trop souvent des quantités.
        # Seul l'enrichissement de marques textuelles est supporté via add().
        return 0

    @property
    def size(self) -> int:
        return len(self._brands)


# Singleton
_instance: Optional[BrandDictionary] = None


def get_brand_dictionary() -> BrandDictionary:
    global _instance
    if _instance is None:
        _instance = BrandDictionary()
    return _instance
