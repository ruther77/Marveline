"""Service Carrier — integration Boxtal pour tarifs transporteurs.

Supporte 2 versions de l'API Boxtal :
- API v3 (api.boxtal.com) : JSON, OAuth2-like, prioritaire si configuree
- API v1 (envoimoinscher.com) : XML, Basic Auth, legacy

Fallback : grille tarifaire statique France si aucune API disponible.
Couvre Chronopost, Colissimo, UPS, DHL, FedEx, Mondial Relay, Colis Prive, etc.
"""
import logging
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from typing import Optional

import httpx
from pydantic import BaseModel

from app.core.config import settings
from app.services.carrier_rates import lookup_static_quotes

logger = logging.getLogger(__name__)

# ── URLs par version + environnement ──────────────────────────────────────────

BOXTAL_V1_URLS = {
    "prod": "https://www.envoimoinscher.com",
    "test": "https://test.envoimoinscher.com",
}
BOXTAL_V3_URLS = {
    "prod": "https://api.boxtal.com",
    "test": "https://api.boxtal.com",  # meme URL, credentials different
}
BOXTAL_TIMEOUT_SECONDS = 15
BOXTAL_CONTENT_CODE = 40110  # "Vaisselle, verrerie" (code EnvoiMoinsCher)


class CarrierQuote(BaseModel):
    """Devis transporteur retourne par Boxtal."""

    carrier_name: str
    carrier_code: str
    service_name: str
    price_cents: int
    delivery_days: Optional[int] = None
    currency: str = "EUR"


class CarrierQuoteRequest(BaseModel):
    """Parametres pour demander des devis transporteurs."""

    weight_grams: int
    length_cm: Optional[int] = None
    width_cm: Optional[int] = None
    height_cm: Optional[int] = None
    volume_cm3: Optional[int] = None
    origin_postal_code: str
    destination_postal_code: str
    origin_country: str = "FR"
    destination_country: str = "FR"


class CarrierService:
    """Service d'integration Boxtal v1+v3 pour les tarifs transporteurs.

    Strategie :
    1. Tente API v3 (api.boxtal.com) avec Bearer token si configuree
    2. Fallback API v1 (envoimoinscher.com) avec Basic Auth
    3. Fallback grille tarifaire statique France
    """

    def __init__(self):
        self.login = getattr(settings, "BOXTAL_LOGIN", "")
        self.password = getattr(settings, "BOXTAL_PASSWORD", "")
        env = getattr(settings, "BOXTAL_ENV", "test")
        self.v1_url = BOXTAL_V1_URLS.get(env, BOXTAL_V1_URLS["test"])
        self.v3_url = BOXTAL_V3_URLS.get(env, BOXTAL_V3_URLS["test"])

    @property
    def is_configured(self) -> bool:
        return bool(self.login and self.password)

    # ── API v3 (JSON) ─────────────────────────────────────────────────────────

    def _build_v3_body(self, request: CarrierQuoteRequest) -> dict:
        """Construit le body JSON pour l'API v3 /offers."""
        weight_kg = max(0.1, request.weight_grams / 1000)
        collect = date.today() + timedelta(days=2)
        if collect.weekday() == 6:
            collect += timedelta(days=1)

        return {
            "shipper": {
                "country": request.origin_country,
                "zipcode": request.origin_postal_code,
                "city": "Expedition",
                "type": "company",
            },
            "recipient": {
                "country": request.destination_country,
                "zipcode": request.destination_postal_code,
                "city": "Destination",
                "type": "individual",
            },
            "parcels": [
                {
                    "weight": round(weight_kg, 2),
                    "x": request.length_cm or 60,
                    "y": request.width_cm or 40,
                    "z": request.height_cm or 40,
                }
            ],
            "collection_date": collect.isoformat(),
            "content_code": BOXTAL_CONTENT_CODE,
        }

    def _parse_v3_offers(self, data: dict | list) -> list[CarrierQuote]:
        """Parse la reponse JSON v3 en liste de CarrierQuote."""
        quotes: list[CarrierQuote] = []
        offers = data if isinstance(data, list) else data.get("offers", data.get("data", []))
        if not isinstance(offers, list):
            return []

        for offer in offers:
            try:
                carrier_name = offer.get("operator", {}).get("label", offer.get("carrier_name", ""))
                carrier_code = offer.get("operator", {}).get("code", offer.get("carrier_code", ""))
                service_name = offer.get("service", {}).get("label", offer.get("service_name", "Standard"))
                price = offer.get("price", {})
                price_ttc = float(price.get("tax_inclusive", price.get("ttc", offer.get("price_ttc", 0))))
                price_cents = int(round(price_ttc * 100))
                delivery_days = offer.get("delivery", {}).get("max_days", offer.get("delivery_days"))

                if carrier_name and price_cents > 0:
                    quotes.append(CarrierQuote(
                        carrier_name=carrier_name,
                        carrier_code=carrier_code or carrier_name[:10].upper(),
                        service_name=service_name,
                        price_cents=price_cents,
                        delivery_days=int(delivery_days) if delivery_days else None,
                    ))
            except (ValueError, TypeError, KeyError) as e:
                logger.warning("Skipping malformed v3 offer: %s", e)
                continue

        return sorted(quotes, key=lambda q: q.price_cents)

    async def _try_v3(self, request: CarrierQuoteRequest) -> list[CarrierQuote] | None:
        """Tente l'API v3 avec Bearer token. Retourne None si echoue."""
        body = self._build_v3_body(request)
        try:
            async with httpx.AsyncClient(timeout=BOXTAL_TIMEOUT_SECONDS) as client:
                response = await client.post(
                    f"{self.v3_url}/v3/offers",
                    json=body,
                    auth=(self.login, self.password),
                    headers={"Accept": "application/json"},
                )
                if response.status_code == 200:
                    quotes = self._parse_v3_offers(response.json())
                    if quotes:
                        logger.info("Boxtal v3 returned %d offers", len(quotes))
                        return quotes
                logger.warning("Boxtal v3 %s: %s", response.status_code, response.text[:200])
                return None
        except Exception as e:
            logger.warning("Boxtal v3 error: %s", e)
            return None

    # ── API v1 (XML) ──────────────────────────────────────────────────────────

    def _build_v1_params(self, request: CarrierQuoteRequest) -> dict:
        """Construit les query params pour l'API cotation v1."""
        weight_kg = max(0.1, request.weight_grams / 1000)
        collect = date.today() + timedelta(days=2)
        if collect.weekday() == 6:
            collect += timedelta(days=1)

        return {
            "expediteur.pays": request.origin_country,
            "expediteur.code_postal": request.origin_postal_code,
            "expediteur.ville": "Expedition",
            "expediteur.type": "entreprise",
            "destinataire.pays": request.destination_country,
            "destinataire.code_postal": request.destination_postal_code,
            "destinataire.ville": "Destination",
            "destinataire.type": "particulier",
            "type_envoi": "colis",
            "code_contenu": str(BOXTAL_CONTENT_CODE),
            "colis_1.poids": f"{weight_kg:.2f}",
            "colis_1.longueur": str(request.length_cm or 60),
            "colis_1.largeur": str(request.width_cm or 40),
            "colis_1.hauteur": str(request.height_cm or 40),
            "collecte": collect.strftime("%Y-%m-%d"),
            "delai": "aucun",
        }

    def _parse_xml_offers(self, xml_text: str) -> list[CarrierQuote]:
        """Parse la reponse XML v1 en liste de CarrierQuote.

        Supporte les 2 formats :
        - Legacy FR : <offre>/<operateur label="">/<prix ttc="">/<service>/<delai>
        - Current EN : <offer>/<operator>/<label>/<price>/<tax-inclusive>/<service>/<delivery>/<date>
        """
        quotes: list[CarrierQuote] = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            logger.error("Boxtal v1 returned invalid XML")
            return []

        # Detect format: <offer> (EN) ou <offre> (FR)
        offers_en = list(root.iter("offer"))
        offers_fr = list(root.iter("offre"))
        offers = offers_en or offers_fr
        is_en = bool(offers_en)

        for offer in offers:
            try:
                if is_en:
                    # Format EN: <operator><label>X</label><code>Y</code></operator>
                    op_el = offer.find("operator")
                    price_el = offer.find("price")
                    svc_el = offer.find("service")
                    delivery_el = offer.find("delivery")

                    if op_el is None or price_el is None:
                        continue

                    carrier_name = (op_el.findtext("label") or "").strip()
                    carrier_code = (op_el.findtext("code") or "").strip()
                    service_name = (svc_el.findtext("label") or "Standard").strip() if svc_el is not None else "Standard"

                    ttc_text = price_el.findtext("tax-inclusive") or price_el.findtext("ttc") or "0"
                    price_ttc = float(ttc_text)
                    price_cents = int(round(price_ttc * 100))

                    delivery_days = None
                    if delivery_el is not None:
                        del_date_text = delivery_el.findtext("date")
                        col_date_text = offer.findtext("collection/date")
                        if del_date_text and col_date_text:
                            from datetime import date as _date
                            try:
                                d = _date.fromisoformat(del_date_text)
                                c = _date.fromisoformat(col_date_text)
                                delivery_days = (d - c).days
                            except ValueError:
                                pass
                else:
                    # Format FR legacy
                    carrier_el = offer.find("operateur")
                    price_el = offer.find("prix")
                    svc_el = offer.find("service")
                    delay_el = offer.find("delai")

                    if carrier_el is None or price_el is None:
                        continue

                    carrier_name = carrier_el.get("label", carrier_el.text or "")
                    carrier_code = carrier_el.get("code", "")
                    service_name = svc_el.text if svc_el is not None else "Standard"
                    price_ttc = float(price_el.get("ttc", price_el.text or "0"))
                    price_cents = int(round(price_ttc * 100))
                    delivery_days = None
                    if delay_el is not None and delay_el.text:
                        try:
                            delivery_days = int(delay_el.text)
                        except ValueError:
                            pass

                if carrier_name and price_cents > 0:
                    quotes.append(CarrierQuote(
                        carrier_name=carrier_name,
                        carrier_code=carrier_code or carrier_name[:10].upper(),
                        service_name=service_name,
                        price_cents=price_cents,
                        delivery_days=delivery_days,
                    ))
            except (ValueError, TypeError) as e:
                logger.warning("Skipping malformed v1 offer: %s", e)
                continue

        return sorted(quotes, key=lambda q: q.price_cents)

    async def _try_v1(self, request: CarrierQuoteRequest) -> list[CarrierQuote] | None:
        """Tente l'API v1 avec Basic Auth. Retourne None si echoue."""
        params = self._build_v1_params(request)
        try:
            async with httpx.AsyncClient(timeout=BOXTAL_TIMEOUT_SECONDS) as client:
                response = await client.get(
                    f"{self.v1_url}/api/v1/cotation",
                    params=params,
                    auth=(self.login, self.password),
                )
                if response.status_code == 200:
                    quotes = self._parse_xml_offers(response.text)
                    if quotes:
                        logger.info("Boxtal v1 returned %d offers", len(quotes))
                        return quotes
                logger.warning("Boxtal v1 %s: %s", response.status_code, response.text[:200])
                return None
        except Exception as e:
            logger.warning("Boxtal v1 error: %s", e)
            return None

    # ── Static fallback ───────────────────────────────────────────────────────

    def _compute_effective_weight(self, request: CarrierQuoteRequest) -> int:
        """Calcule le poids effectif (max entre réel et volumétrique)."""
        vol_weight = 0
        if request.length_cm and request.width_cm and request.height_cm:
            vol_weight = int(
                (request.length_cm * request.width_cm * request.height_cm) / 5000 * 1000
            )
        elif request.volume_cm3:
            vol_weight = int(request.volume_cm3 / 5000 * 1000)
        return max(request.weight_grams, vol_weight)

    def _static_fallback(self, request: CarrierQuoteRequest) -> list[CarrierQuote]:
        """Retourne les tarifs depuis la grille statique Boxtal France (ajustés par zone)."""
        effective_weight = self._compute_effective_weight(request)
        raw = lookup_static_quotes(
            weight_grams=effective_weight,
            destination_country=request.destination_country,
            destination_postal_code=request.destination_postal_code,
        )
        return [
            CarrierQuote(
                carrier_name=q["carrier_name"],
                carrier_code=q["carrier_code"],
                service_name=q["service_name"],
                price_cents=q["price_cents"],
                delivery_days=q["delivery_days"],
            )
            for q in raw
        ]

    # ── Orchestrateur ─────────────────────────────────────────────────────────

    async def get_quotes(
        self, request: CarrierQuoteRequest
    ) -> list[CarrierQuote]:
        """Recupere les devis transporteurs : v3 → v1 → statique.

        Cascade :
        1. API v3 (api.boxtal.com) — JSON, rapide
        2. API v1 (envoimoinscher.com) — XML, legacy
        3. Grille statique France — toujours disponible

        Returns:
            Liste de devis tries par prix croissant.
        """
        if not self.is_configured:
            logger.info("Boxtal not configured — using static rate grid")
            return self._static_fallback(request)

        # 1. Tenter API v3
        quotes = await self._try_v3(request)
        if quotes:
            return quotes

        # 2. Fallback API v1
        quotes = await self._try_v1(request)
        if quotes:
            return quotes

        # 3. Fallback statique
        logger.info("Both Boxtal APIs unavailable — using static rate grid")
        return self._static_fallback(request)
