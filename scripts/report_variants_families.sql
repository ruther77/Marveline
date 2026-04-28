-- Variant/family audit report for a tenant.
-- Usage:
--   PGPASSWORD='***' psql -h 127.0.0.1 -p 5434 -U caro -d CaroCorp -v tenant_id=1 -f scripts/report_variants_families.sql
--
-- This script creates a temp view with one row per active variant and a classification:
--   - valid_dimensional
--   - technical_default_std
--   - technical_no_dimension

\set ON_ERROR_STOP on

DROP VIEW IF EXISTS tmp_variant_audit;

CREATE TEMP VIEW tmp_variant_audit AS
SELECT
  v.id AS variant_id,
  v.tenant_id,
  v.product_id,
  p.sku AS parent_sku,
  p.name AS parent_name,
  p.category AS parent_category,
  p.is_active AS parent_is_active,
  v.sku AS variant_sku,
  v.label,
  v.color,
  v.size,
  v.gamme,
  v.price_per_day,
  v.stock_quantity,
  v.available_quantity,
  v.created_at,
  CASE
    WHEN v.label = 'Standard'
      AND v.sku LIKE '%-STD'
      AND v.color IS NULL
      AND v.size IS NULL
      AND v.gamme IS NULL
    THEN 'technical_default_std'
    WHEN v.color IS NULL
      AND v.size IS NULL
      AND v.gamme IS NULL
    THEN 'technical_no_dimension'
    ELSE 'valid_dimensional'
  END AS variant_quality
FROM product_variants v
JOIN products p ON p.id = v.product_id
WHERE v.tenant_id = :tenant_id
  AND v.is_active = TRUE;

-- 1) High-level quality summary
SELECT
  tenant_id,
  variant_quality,
  count(*) AS variant_count
FROM tmp_variant_audit
GROUP BY tenant_id, variant_quality
ORDER BY tenant_id, variant_quality;

-- 2) Family summary (one row per parent product with variants)
SELECT
  tenant_id,
  parent_sku,
  parent_name,
  parent_category,
  parent_is_active,
  count(*) AS variants_total,
  count(*) FILTER (WHERE variant_quality = 'valid_dimensional') AS valid_count,
  count(*) FILTER (WHERE variant_quality LIKE 'technical_%') AS technical_count,
  count(*) FILTER (WHERE color IS NOT NULL) AS with_color,
  count(*) FILTER (WHERE size IS NOT NULL) AS with_size,
  count(*) FILTER (WHERE gamme IS NOT NULL) AS with_gamme
FROM tmp_variant_audit
GROUP BY tenant_id, parent_sku, parent_name, parent_category, parent_is_active
ORDER BY technical_count DESC, variants_total DESC, parent_sku;

-- 3) Detailed list (export-friendly)
SELECT
  tenant_id,
  variant_id,
  variant_quality,
  parent_sku,
  parent_name,
  parent_category,
  parent_is_active,
  variant_sku,
  label,
  color,
  size,
  gamme,
  price_per_day,
  stock_quantity,
  available_quantity,
  created_at
FROM tmp_variant_audit
ORDER BY variant_quality, parent_sku, variant_sku;

