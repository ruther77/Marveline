"""Moteur d'application des regles de pricing.

Applique les PricingRules actives a un calcul de prix.
Types de regles supportes :
- flat : prix fixe (remplace le prix unitaire)
- per_day : prix par jour de location
- tiered : paliers de quantite (via PricingTier)
- volume : remise volume (via PricingTier)
- seasonal : multiplicateur saisonnier (discount_pct = pourcentage d'ajustement)
- custom : remise personnalisee en % (discount_pct)
"""
import logging
from datetime import date
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.pricing import PricingRule, PricingTier

logger = logging.getLogger(__name__)


class PricingEngine:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def apply_rules(
        self,
        tenant_id: int,
        base_amount_cents: int,
        event_date: date,
        rental_days: int,
        product_id: int | None = None,
        category_id: int | None = None,
        quantity: int = 1,
    ) -> dict:
        """Applique toutes les regles actives et retourne le montant final.

        Returns:
            {
                "base_cents": int,
                "final_cents": int,
                "applied_rules": [{"rule_id": int, "name": str, "type": str, "adjustment_cents": int}],
            }
        """
        rules = await self._get_active_rules(tenant_id)
        applied: list[dict] = []
        amount = base_amount_cents

        for rule in rules:
            if not self._rule_applies(rule, event_date, product_id, category_id):
                continue

            adjustment = self._compute_adjustment(rule, amount, quantity)
            if adjustment == 0:
                continue

            amount += adjustment
            applied.append({
                "rule_id": rule.id,
                "name": rule.name,
                "type": rule.rule_type,
                "adjustment_cents": adjustment,
            })

        return {
            "base_cents": base_amount_cents,
            "final_cents": max(0, amount),
            "applied_rules": applied,
        }

    async def _get_active_rules(self, tenant_id: int) -> list[PricingRule]:
        result = await self.db.execute(
            select(PricingRule)
            .options(selectinload(PricingRule.tiers))
            .filter(
                PricingRule.tenant_id == tenant_id,
                PricingRule.active == True,  # noqa: E712
            )
        )
        return list(result.scalars().all())

    def _rule_applies(
        self,
        rule: PricingRule,
        event_date: date,
        product_id: int | None,
        category_id: int | None,
    ) -> bool:
        if rule.valid_from and event_date < rule.valid_from:
            return False
        if rule.valid_to and event_date > rule.valid_to:
            return False
        if rule.applies_to == "product" and rule.target_id:
            if product_id != rule.target_id:
                return False
        elif rule.applies_to == "category" and rule.target_id:
            if category_id != rule.target_id:
                return False
        return True

    def _compute_adjustment(self, rule: PricingRule, amount_cents: int, quantity: int) -> int:
        if rule.rule_type in ("flat", "per_day"):
            return 0

        if rule.rule_type in ("custom", "seasonal") and rule.discount_pct:
            discount = int(amount_cents * rule.discount_pct / 100)
            return -discount

        if rule.rule_type in ("tiered", "volume") and rule.tiers:
            tier = self._find_tier(rule.tiers, quantity)
            if tier:
                tier_amount = tier.unit_price_cents * quantity
                return tier_amount - amount_cents

        return 0

    @staticmethod
    def _find_tier(tiers: list[PricingTier], quantity: int) -> PricingTier | None:
        for tier in sorted(tiers, key=lambda t: t.min_qty, reverse=True):
            if quantity >= tier.min_qty:
                if tier.max_qty is None or quantity <= tier.max_qty:
                    return tier
        return None
