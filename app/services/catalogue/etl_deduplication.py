"""Déduplication catalogue alimentaire — Soft TF-IDF token-aware.

Remplace l'algorithme Jaro-Winkler global par Soft TF-IDF (Fellegi-Sunter) :
  1. EAN exact match  → MATCH direct (score 1.0, géré par l'appelant)
  2. Soft TF-IDF token-aware :
       - Tokenise les désignations normalisées
       - Tokens numériques (marques : 1664, 86) → exact match requis
       - Tokens textuels → Jaro-Winkler par token, pondéré par IDF
       score ≥ 0.85           → MATCH  (même produit, merge possible)
       0.75 ≤ score < 0.85    → CONFLICT (zone d'alerte, résolution manuelle)
       score < 0.75            → NEW    (nouveau produit à créer)
  3. EAN cross-supplier → EAN_COLLISION (géré par l'appelant)

Références :
    ADR-07 §"Déduplication catalogue produits"
    Fellegi-Sunter : Soft TF-IDF (Cohen et al., 2003)
"""
import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from rapidfuzz import distance as rf_distance

# ── Seuils ADR-07 ───────────────────────────────────────────────────────────

ETL_SEUIL_MATCH: float = 0.85
ETL_SEUIL_CONFLIT: float = 0.80
ETL_DESIGNATION_MAXLEN: int = 80

# Seuil Jaro-Winkler par token pour Soft TF-IDF :
# un token doit matcher à ≥ TOKEN_MATCH_SEUIL pour contribuer au score.
_TOKEN_MATCH_SEUIL: float = 0.80

_STOP_WORDS: frozenset[str] = frozenset({
    "le", "la", "les", "de", "du", "des", "en", "au",
    "un", "une", "et", "ou",
})

# Pays/provenances à exclure du matching (pollution TAIYAT legacy, METRO provenance)
# Ces tokens ne portent aucun signal produit → on les retire des signatures.
_COUNTRY_TOKENS: frozenset[str] = frozenset({
    "france", "espagne", "italie", "portugal", "allemagne", "belgique",
    "pays", "bas", "hollande", "pologne", "roumanie", "maroc", "tunisie",
    "egypte", "cameroun", "senegal", "cote", "ivoire", "ghana", "benin",
    "togo", "mali", "guinee", "nigeria", "congo", "kenya", "honduras",
    "bresil", "colombie", "rica", "costa", "mexique", "perou", "argentine",
    "chili", "equateur", "chine", "thailande", "vietnam", "inde", "indonesie",
    "japon", "norvege", "suede", "suriname", "burundi", "rwanda", "cambodge",
    "laos", "philippines", "malaisie", "bangladesh", "pakistan", "madagascar",
    "maurice", "reunion", "antilles", "martinique", "guadeloupe", "taiwan",
    "coree", "turquie", "iran", "liban", "israel", "royaume", "uni",
    # Métadonnées facture parasites
    "frais", "surgele", "conserve", "ctre",
})

# Tokens marketing non-distinctifs (pondération réduite, pas filtrés)
_GENERIC_TOKENS: frozenset[str] = frozenset({
    "bio", "nature", "naturel", "naturelle", "original", "ordinaire",
    "standard", "classique", "premium", "gourmand", "gourmande",
    "traditionnel", "tradition", "artisanal", "artisanale",
})

_VALID_EAN_LENGTHS: frozenset[int] = frozenset({8, 13})


# ── Types résultat ───────────────────────────────────────────────────────────

class DecisionDeduplication(str, Enum):
    MATCH = "MATCH"
    CONFLICT = "CONFLICT"
    NEW = "NEW"
    EAN_COLLISION = "EAN_COLLISION"


@dataclass(frozen=True)
class ResultatDeduplication:
    decision: DecisionDeduplication
    candidate_id: Optional[int]
    score: Optional[float]
    designation_norm: str


# ── Normalisation ────────────────────────────────────────────────────────────

def normalize_designation(designation: str) -> str:
    """Normalise une désignation (NFD→ASCII, lowercase, stop words, truncate).

    Backward-compatible : garde tous les tokens y compris pays (pour les
    designation_norm déjà persistés en DB). Pour un matching propre
    cross-vendor, utiliser `designation_signature()`.
    """
    nfd = unicodedata.normalize("NFD", designation)
    ascii_only = nfd.encode("ascii", "ignore").decode("ascii")
    lower = ascii_only.lower()
    alphanum_spaces = re.sub(r"[^a-z0-9 ]", " ", lower)
    tokens = [t for t in alphanum_spaces.split() if t not in _STOP_WORDS]
    return " ".join(tokens)[:ETL_DESIGNATION_MAXLEN]


def designation_signature(designation: str) -> list[str]:
    """Signature token-set pour matching cross-vendor.

    Retire : stop words, pays de provenance, chiffres isolés (≤ 2 chars),
    tokens 1 caractère.
    Garde : marques, descripteurs produit significatifs.

    Idéal pour classify_designation / S4 TF-IDF. Retourne une liste triée
    utilisable comme base de comparaison.
    """
    nfd = unicodedata.normalize("NFD", designation or "")
    ascii_only = nfd.encode("ascii", "ignore").decode("ascii")
    lower = ascii_only.lower()
    alphanum_spaces = re.sub(r"[^a-z0-9 ]", " ", lower)
    tokens: list[str] = []
    for t in alphanum_spaces.split():
        if t in _STOP_WORDS:
            continue
        if t in _COUNTRY_TOKENS:
            continue
        if len(t) <= 1:
            continue
        # Chiffres isolés courts (1-2 chars) = Cal/Cat TAIYAT → bruit
        if t.isdigit() and len(t) <= 2:
            continue
        tokens.append(t)
    return tokens


def _tokenize(norm: str) -> list[str]:
    """Tokenise une désignation normalisée en mots."""
    return norm.split() if norm else []


def _signature_of(norm_or_desig: str) -> list[str]:
    """Convertit un designation_norm OU une désignation brute en signature.

    Si la string contient des pays connus, les filtre (compatible avec les
    designation_norm historiquement persistés avec pollution).
    """
    return designation_signature(norm_or_desig)


def _is_numeric_token(token: str) -> bool:
    """Un token purement numérique (ex: '1664', '86') — exige un match exact."""
    return token.isdigit()


# ── Validation EAN ───────────────────────────────────────────────────────────

def is_ean_valid(ean: Optional[str]) -> bool:
    if not ean:
        return False
    stripped = ean.strip()
    return stripped.isdigit() and len(stripped) in _VALID_EAN_LENGTHS


# ── IDF Corpus ───────────────────────────────────────────────────────────────

class IdfCorpus:
    """Calcule et cache les poids IDF sur un corpus de désignations normalisées.

    IDF(token) = log(N / df(token)) où df = nombre de documents contenant le token.
    Les tokens rares (marques numériques, noms propres) ont un IDF élevé.
    Les tokens fréquents ("biere", "vin") ont un IDF bas.
    """

    def __init__(self) -> None:
        self._doc_freq: Counter[str] = Counter()
        self._num_docs: int = 0
        self._idf_cache: dict[str, float] = {}

    def build(self, corpus_norms: list[str]) -> None:
        """Construit l'index IDF depuis une liste de designation_norm."""
        self._doc_freq.clear()
        self._idf_cache.clear()
        self._num_docs = len(corpus_norms)

        for norm in corpus_norms:
            unique_tokens = set(_tokenize(norm))
            for token in unique_tokens:
                self._doc_freq[token] += 1

    def idf(self, token: str) -> float:
        """Retourne le poids IDF d'un token. Cache le résultat.

        Utilise un lissage de Laplace : log((N+1)/(df+0.5)) + 0.1 min.
        Garantit un poids non-nul même pour les tokens présents dans tous les
        documents (sinon un corpus de 1 document donnerait IDF=0 partout).
        """
        if token in self._idf_cache:
            return self._idf_cache[token]

        df = self._doc_freq.get(token, 0)
        n = max(self._num_docs, 1)
        if df == 0:
            # Token inconnu du corpus → IDF max (très distinctif)
            weight = math.log(n + 1)
        else:
            # Laplace smoothing : jamais 0, même si df == N
            weight = max(math.log((n + 1) / (df + 0.5)), 0.1)

        self._idf_cache[token] = weight
        return weight

    @property
    def size(self) -> int:
        return self._num_docs


# Singleton global IDF (reconstruit à chaque import batch)
_global_idf = IdfCorpus()


def build_idf_from_candidates(candidates: list[tuple[int, str]]) -> None:
    """Reconstruit l'index IDF global depuis les candidats du catalogue.

    Appelé au début de chaque batch d'import ETL.
    """
    _global_idf.build([norm for _, norm in candidates])


# ── Scoring Soft TF-IDF ─────────────────────────────────────────────────────

def _jaro_winkler(a: str, b: str) -> float:
    """Jaro-Winkler sur deux tokens individuels."""
    if not a or not b:
        return 0.0
    return rf_distance.JaroWinkler.similarity(a, b)


def _compute_similarity_tokens(tokens_a: list[str], tokens_b: list[str]) -> float:
    """Soft TF-IDF sur deux listes de tokens pré-extraites."""
    if not tokens_a or not tokens_b:
        return 0.0

    total_weight = 0.0
    matched_weight = 0.0

    for ta in tokens_a:
        idf_a = _global_idf.idf(ta)
        total_weight += idf_a

        if _is_numeric_token(ta):
            if ta in tokens_b:
                matched_weight += idf_a
        else:
            best_sim = 0.0
            for tb in tokens_b:
                if _is_numeric_token(tb):
                    continue
                sim = _jaro_winkler(ta, tb)
                if sim > best_sim:
                    best_sim = sim
            if best_sim >= _TOKEN_MATCH_SEUIL:
                matched_weight += best_sim * idf_a

    if total_weight <= 0:
        return 0.0

    return matched_weight / total_weight


def compute_similarity(norm_a: str, norm_b: str) -> float:
    """Soft TF-IDF : similarité token-aware pondérée par IDF.

    Backward compatible : tokenise sur la string raw (garde tokens y compris
    pays de provenance pour compatibilité designation_norm en DB).
    """
    if not norm_a or not norm_b:
        return 0.0
    return _compute_similarity_tokens(_tokenize(norm_a), _tokenize(norm_b))


def compute_similarity_smart(
    norm_a: str,
    norm_b: str,
    marque_a: Optional[str] = None,
    marque_b: Optional[str] = None,
) -> float:
    """Soft TF-IDF enrichi : filtre pays, bonus si marque identique.

    - Utilise designation_signature() pour filtrer les tokens parasites
      (pays, chiffres isolés Cal/Cat TAIYAT, tokens 1-char).
    - Si marque_a == marque_b (case-insensitive, non-null) : bonus +0.15 (cap 1.0).
    - Si marque_a != marque_b (toutes deux non-null et connues) : pénalité ×0.7.

    Cette fonction fait le matching cross-vendor (TAIYAT ↔ METRO) avec les
    désignations polluées et les marques détectées séparément.
    """
    if not norm_a or not norm_b:
        return 0.0

    tokens_a = _signature_of(norm_a)
    tokens_b = _signature_of(norm_b)
    if not tokens_a or not tokens_b:
        return 0.0

    base_score = _compute_similarity_tokens(tokens_a, tokens_b)

    ma = (marque_a or "").strip().upper() or None
    mb = (marque_b or "").strip().upper() or None

    if ma and mb:
        if ma == mb:
            # Même marque : bonus absolu + booster multiplicatif
            boosted = min(1.0, base_score + 0.15)
            # Si au moins un token principal matche, on remonte agressivement
            if base_score >= 0.30:
                boosted = min(1.0, boosted * 1.10)
            return boosted
        else:
            # Marques différentes explicites : pénalité (produits probablement distincts)
            return base_score * 0.7

    return base_score


def decide(score: float) -> DecisionDeduplication:
    if score >= ETL_SEUIL_MATCH:
        return DecisionDeduplication.MATCH
    if score >= ETL_SEUIL_CONFLIT:
        return DecisionDeduplication.CONFLICT
    return DecisionDeduplication.NEW


# ── Classification principale ─────────────────────────────────────────────────

def classify_designation(
    designation_entrante: str,
    candidates: list[tuple[int, str]],
    marque_entrante: Optional[str] = None,
    candidates_marques: Optional[dict[int, Optional[str]]] = None,
) -> ResultatDeduplication:
    """Classifie une désignation entrante via Soft TF-IDF contre les candidats.

    Args:
        designation_entrante: Désignation brute.
        candidates: Liste de (id, designation_norm) à comparer.
        marque_entrante: Marque de la ligne entrante (optionnel, pour bonus).
        candidates_marques: Map {id: marque} pour bonus cross-brand. Si fourni,
            utilise compute_similarity_smart.
    """
    norm_entrante = normalize_designation(designation_entrante)

    if not candidates:
        return ResultatDeduplication(
            decision=DecisionDeduplication.NEW,
            candidate_id=None,
            score=None,
            designation_norm=norm_entrante,
        )

    if _global_idf.size == 0:
        build_idf_from_candidates(candidates)

    best_id: Optional[int] = None
    best_score: float = 0.0

    use_smart = candidates_marques is not None or marque_entrante is not None
    marques_map = candidates_marques or {}

    for candidate_id, candidate_norm in candidates:
        if use_smart:
            marque_cand = marques_map.get(candidate_id)
            score = compute_similarity_smart(
                norm_entrante, candidate_norm,
                marque_a=marque_entrante, marque_b=marque_cand,
            )
        else:
            score = compute_similarity(norm_entrante, candidate_norm)
        if score > best_score:
            best_score = score
            best_id = candidate_id

    decision = decide(best_score)
    return ResultatDeduplication(
        decision=decision,
        candidate_id=best_id if decision != DecisionDeduplication.NEW else None,
        score=round(best_score, 3),
        designation_norm=norm_entrante,
    )


def classify_designation_top_n(
    designation_entrante: str,
    candidates: list[tuple[int, str]],
    seuil: float = 0.70,
    n: int = 5,
    marque_entrante: Optional[str] = None,
    candidates_marques: Optional[dict[int, Optional[str]]] = None,
) -> list[dict]:
    """Top-N produits similaires par Soft TF-IDF (smart si marques fournies).

    Returns:
        [{candidate_id, designation_norm, score}, ...] trié par score desc.
    """
    norm_entrante = normalize_designation(designation_entrante)
    if not candidates:
        return []

    if _global_idf.size == 0:
        build_idf_from_candidates(candidates)

    use_smart = candidates_marques is not None or marque_entrante is not None
    marques_map = candidates_marques or {}

    scored: list[dict] = []
    for candidate_id, candidate_norm in candidates:
        if use_smart:
            marque_cand = marques_map.get(candidate_id)
            score = compute_similarity_smart(
                norm_entrante, candidate_norm,
                marque_a=marque_entrante, marque_b=marque_cand,
            )
        else:
            score = compute_similarity(norm_entrante, candidate_norm)
        if score >= seuil:
            scored.append({
                "candidate_id": candidate_id,
                "designation_norm": candidate_norm,
                "score": round(score, 3),
            })

    scored.sort(key=lambda r: r["score"], reverse=True)
    return scored[:n]
