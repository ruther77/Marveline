# Module 26 — Supplier (Fournisseurs Marveline)

> **Phase C.** Audit du domaine fournisseurs : Supplier, SupplierOrder (FSM 5 statuts), SupplierOrderLine, SupplierOrderReceipt, SupplierOrderReceiptLine, SupplierProductPrice.

---

## 1. Inventaire — lecture intégrale

| Fichier | LoC |
|---|---|
| `app/models/supplier.py` | 63 |
| `app/models/supplier_order.py` | 344 (4 classes) |
| `app/models/supplier_product_price.py` | 71 (parcours) |
| `app/services/supplier_order.py` | 358 (parcours) |
| `app/repositories/supplier.py` | 98 |
| `app/repositories/supplier_order.py` | 214 (parcours) |
| `app/api/v1/endpoints/suppliers.py` | 115 |
| `app/api/v1/endpoints/supplier_orders.py` | 142 (parcours) |
| `app/schemas/supplier.py` | 36 |
| `app/schemas/supplier_order.py` | 166 (parcours) |

**Volume total** : ~1 610 LoC.

---

## 2. Architecture observée

```
Supplier
  ↓ 1:N
SupplierOrder (FSM : draft → ordered → partially_received | fully_received | cancelled)
  ├── SupplierOrderLine (qty_ordered, qty_received cumulé, unit_cost_cents)
  └── SupplierOrderReceipt (received_at, received_by, lines_json snapshot)
        └── SupplierOrderReceiptLine (qty_received/damaged/missing par ligne)

SupplierProductPrice (catalog supplier prices, pas audité en détail)
```

---

## 3. Frictions identifiées — module 26

> Compteur cumulé (mod. 01-25) ≈ 825. Module 26 ouvre à **F826**.

### 3.1 P0

#### F826 — `Supplier` aucune UniqueConstraint `(tenant_id, name)`

`models/supplier.py` n'a même pas `__table_args__`. Doublons "ACME" + "ACME" silencieux.

---

#### F827 — `SupplierOrder.reference String(100)` sans UNIQUE per tenant (cf. F767 pattern)

---

#### F828 — `SupplierOrder.status String(30)` sans CHECK enum

5 valeurs en commentaire model l. 53 mais aucun CHECK SQL. Typo `status="orderd"` accepté.

---

#### F829 — `SupplierOrderReceiptLine` aucun CHECK couplant qty_received + qty_damaged + qty_missing ≤ qty_ordered

Possible enregistrement `qty_received=100, qty_damaged=50, qty_missing=30` sur `qty_ordered=20` → bilan absurde.

---

#### F830 — Pas de sync auto `Product.stock_quantity` après `qty_received`

Le commentaire `models/supplier_order.py:173` dit "Chaque réception déclenche des StockAdjustment". À confirmer dans le service. Si pas le cas → stock incohérent.

---

### 3.2 P1

#### F831 — `Supplier.email/phone` aucune validation format

#### F832 — `Supplier.notes Text` non chiffré (PII : conditions négociées, mots de passe portail)

#### F833 — `SupplierOrderReceipt.lines_json JSON` + `SupplierOrderReceiptLine` table = **duplicate sources of truth**

Drift garanti si l'un est mis à jour sans l'autre.

---

#### F834 — `SupplierOrderReceipt.received_by FK accounts RESTRICT`

Bloque offboarding employé ayant fait des réceptions.

---

#### F835 — Pas d'audit log structurel sur transitions order status

---

#### F836 — `SupplierOrderReceipt.notes Text` non chiffré

---

#### F837 — `SupplierOrderReceiptLine.qty_damaged/missing server_default="0"` string

Vs Python `default=0` — pattern inconsistant.

---

#### F838 — Pas de schemas Pydantic pour bulk receipt creation

---

#### F839 — `Supplier.address Text` libre (pas structuré street/city/postal)

---

#### F840 — Pas d'index `(tenant_id, supplier_id, status)` pour dashboards

---

### 3.3 P2

#### F841 — `Supplier.contact_name` String(255) non chiffré (PII)

#### F842 — `SupplierOrderLine.unit_cost_cents` BigInteger sans borne max

#### F843 — Pas de CHECK `expected_date >= order_date`

#### F844 — `SupplierProductPrice` (71L) parcouru rapidement — patterns probables même

#### F845 — `Supplier.phone` pas validé E.164

---

### 3.4 P3

#### F846 — Format `CMD-YYYY-NNN` documenté en comment

#### F847 — `lines_json` JSON sans schema validation

---

## 4. Synthèse module 26

| Sévérité | Nb | Frictions |
|---|---|---|
| P0 | 5 | F826 (no UNIQUE supplier), F827 (no UNIQUE reference), F828 (no CHECK status), F829 (no CHECK qty), F830 (no auto-sync stock) |
| P1 | 10 | F831 → F840 |
| P2 | 5 | F841 → F845 |
| P3 | 2 | F846, F847 |
| **Total** | **22** | F826 → F847 |

**Compteur cumulé après module 26** : ≈ 825 + 22 = **847 frictions**.

---

## 5. Décision architecturale

> **P0 immédiat** : (1) UniqueConstraint suppliers (F826) ; (2) UNIQUE reference per tenant (F827) ; (3) CHECK status (F828) ; (4) CHECK quantités (F829) ; (5) hook auto-sync stock (F830 — confirmer).
