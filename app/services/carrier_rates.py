"""Grille tarifaire statique Boxtal France — tarifs du 13/03/2026.

Source : PDF tarifs-boxtal.pdf (prix HT en centimes, tout compris sauf douane).
Poids volumétrique = (L × l × H) / 5000 — prendre max(réel, volumétrique).

Tranches de poids en grammes : 250, 500, 1000, 2000, 3000, 5000, 7000, 10000, 15000, 20000, 30000.
None = offre indisponible pour cette tranche.
"""

WEIGHT_BRACKETS_GRAMS = [250, 500, 1000, 2000, 3000, 5000, 7000, 10000, 15000, 20000, 30000]

# Prix HT en centimes par tranche — index aligné sur WEIGHT_BRACKETS_GRAMS
# (carrier, code, offer, category, departure, delay_label, delay_days, prices[])

FRANCE_RATES: list[tuple[str, str, str, str, str, str, int | None, list[int | None]]] = [
    # ── En relais ──────────────────────────────────────────────────────────────
    ("Relais Colis", "RLCO", "Relais", "relais", "relais", "3-5 jours", 5,
     [363, 363, 371, 524, 545, 767, 956, 1096, 1392, 1632, None]),

    ("Mondial Relay", "MONR", "Point Relais", "relais", "relais", "3-4 jours", 4,
     [304, 314, 351, 490, 521, 944, 1036, 1036, 1616, 1626, 1860]),

    ("Chronopost", "CHRP", "2Shop Direct", "relais", "relais", "2-4 jours", 4,
     [299, 310, 366, 463, 510, 721, 849, 1042, 1364, 1686, None]),

    ("Colis Privé", "COPV", "Relais", "relais", "relais", "6 jours", 6,
     [370, 370, 426, 556, 579, 866, 1066, 1066, 1295, 1704, None]),

    ("Colissimo", "COLS", "Point Retrait", "relais", "bureau_poste", "48h", 2,
     [500, 582, 739, 846, 942, 1138, 1292, 1577, 2011, 2476, 3376]),

    # ── En relais express ──────────────────────────────────────────────────────
    ("UPS", "UPSE", "Economy Access Point", "relais_express", "relais", "48h", 2,
     [491, 491, 491, 490, 490, 741, 882, 1170, 1403, 1709, None]),

    ("Chronopost", "CHRP", "Chrono Relais", "relais_express", "bureau_poste", "24h", 1,
     [576, 576, 576, 670, 728, 863, 999, 1202, 1541, 1880, None]),

    ("UPS", "UPSE", "Standard Access Point", "relais_express", "collecte", "48h", 2,
     [491, 491, 492, 490, 490, 743, 886, 1173, 1406, 1713, None]),

    # ── Domicile sans signature ────────────────────────────────────────────────
    ("Colis Privé", "COPV", "Domicile Sans Signature", "domicile", "relais", "6 jours", 6,
     [552, 632, 819, 914, 1016, 1221, 1418, 1713, 2354, 3058, None]),

    ("Colissimo", "COLS", "Domicile Sans Signature", "domicile", "bureau_poste", "48h", 2,
     [656, 739, 894, 1003, 1099, 1294, 1448, 1734, 2168, 2633, 3530]),

    # ── Domicile avec signature ────────────────────────────────────────────────
    ("Colis Privé", "COPV", "Domicile Avec Signature", "domicile", "relais", "6 jours", 6,
     [665, 745, 928, 1020, 1119, 1331, 1537, 1829, 2674, 3232, None]),

    ("Colissimo", "COLS", "Domicile Avec Signature", "domicile", "bureau_poste", "48h", 2,
     [757, 839, 994, 1102, 1199, 1393, 1548, 1834, 2267, 2733, 3631]),

    ("Mondial Relay", "MONR", "Domicile France", "domicile", "relais", "5 jours", 5,
     [510, 555, 623, 726, 854, 1025, 1111, 1367, 1709, 2821, None]),

    # ── Domicile express ───────────────────────────────────────────────────────
    ("Chronopost", "CHRP", "Chrono 18", "domicile_express", "bureau_poste", "24h", 1,
     [940, 940, 940, 940, 1083, 1083, 1334, 1448, 1638, 1828, 2207]),

    ("Chronopost", "CHRP", "Chrono 13", "domicile_express", "bureau_poste", "24h", 1,
     [1244, 1244, 1244, 1244, 1257, 1257, 1333, 1447, 1636, 1826, 2205]),

    ("UPS", "UPSE", "Standard", "domicile_express", "collecte", "24h", 1,
     [975, 975, 991, 993, 1103, 1119, 2801, 3140, 3519, 3752, 6326]),

    ("DHL", "DHLE", "Domestic Express", "domicile_express", "collecte", "24h", 1,
     [2376, 2376, 2376, 2510, 2644, 2911, 3179, 3580, 4780, 5979, 11068]),

    ("FedEx", "FEDX", "Priority", "domicile_express", "collecte", "24h", 1,
     [1122, 1122, 1121, 1292, 1376, 1471, 1632, 1805, 2208, 2592, 5887]),
]

# Labels français pour les catégories
CATEGORY_LABELS = {
    "relais": "En relais",
    "relais_express": "En relais express",
    "domicile": "À domicile",
    "domicile_express": "À domicile express",
}


# ── Zones tarifaires France (surcharges réelles transporteurs) ────────────────
# Les tarifs de base sont France metropolitaine.
# Corse, DOM-TOM et IDF proche ont des ajustements.

# Departements IDF (meme zone que Paris — parfois moins cher en proximite)
_IDF_DEPTS = {"75", "77", "78", "91", "92", "93", "94", "95"}
# Corse
_CORSE_DEPTS = {"20", "2A", "2B"}
# DOM-TOM
_DOM_DEPTS = {"97", "98"}
# Sud lointain (ajustement +5-10% selon transporteur)
_SUD_DEPTS = {"06", "13", "83", "84", "30", "34", "11", "66", "31", "32", "40", "64", "65", "09"}


def _get_zone(destination_postal_code: str) -> str:
    """Determine la zone tarifaire depuis le code postal."""
    dept = destination_postal_code[:2]
    if dept in _DOM_DEPTS:
        return "dom"
    if dept in _CORSE_DEPTS or destination_postal_code.startswith("20"):
        return "corse"
    if dept in _IDF_DEPTS:
        return "idf"
    if dept in _SUD_DEPTS:
        return "sud"
    return "province"


def _zone_multiplier(zone: str) -> float:
    """Coefficient multiplicateur par zone (approximation realiste)."""
    return {
        "idf": 0.95,       # IDF : -5% (proximite depots)
        "province": 1.0,   # Base
        "sud": 1.08,        # Sud lointain : +8%
        "corse": 1.35,     # Corse : +35% (ferry)
        "dom": 2.50,       # DOM-TOM : x2.5 (avion)
    }.get(zone, 1.0)


def _zone_delay_offset(zone: str) -> int:
    """Jours supplementaires par zone."""
    return {"idf": 0, "province": 0, "sud": 1, "corse": 2, "dom": 5}.get(zone, 0)


def lookup_static_quotes(
    weight_grams: int,
    destination_country: str = "FR",
    category: str | None = None,
    destination_postal_code: str = "",
) -> list[dict]:
    """Retourne les tarifs statiques ajustes par zone geographique.

    Args:
        weight_grams: Poids en grammes (réel ou volumétrique, le max)
        destination_country: Code pays destination (seul FR supporté)
        category: Filtre optionnel (relais, domicile, domicile_express, etc.)
        destination_postal_code: Code postal destination (pour ajustement zone)

    Returns:
        Liste de devis triés par prix croissant.
    """
    if destination_country != "FR":
        return []

    # Trouver la tranche de poids applicable
    bracket_index = None
    for i, bracket in enumerate(WEIGHT_BRACKETS_GRAMS):
        if weight_grams <= bracket:
            bracket_index = i
            break

    if bracket_index is None:
        return []  # Au-delà de 30kg, pas de tarif statique

    zone = _get_zone(destination_postal_code) if destination_postal_code else "province"
    multiplier = _zone_multiplier(zone)
    delay_offset = _zone_delay_offset(zone)

    results: list[dict] = []
    for carrier, code, offer, cat, departure, delay_label, delay_days, prices in FRANCE_RATES:
        if category and cat != category:
            continue

        price = prices[bracket_index]
        if price is None:
            continue

        # Corse/DOM : pas de relais dispo pour certains transporteurs
        if zone in ("corse", "dom") and cat in ("relais", "relais_express"):
            if code not in ("COLS", "CHRP"):  # Seuls Colissimo et Chronopost desservent
                continue

        adjusted_price = int(round(price * multiplier))
        adjusted_days = (delay_days + delay_offset) if delay_days else None

        results.append({
            "carrier_name": carrier,
            "carrier_code": code,
            "service_name": offer,
            "category": cat,
            "category_label": CATEGORY_LABELS.get(cat, cat),
            "departure": departure,
            "delay_label": delay_label,
            "delivery_days": adjusted_days,
            "price_cents": adjusted_price,
            "currency": "EUR",
            "source": "static_grid",
            "zone": zone,
        })

    return sorted(results, key=lambda q: q["price_cents"])
