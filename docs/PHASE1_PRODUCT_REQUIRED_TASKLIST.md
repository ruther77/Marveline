# Phase 1 — Product-Required Task List (Executable)

Date: 2026-03-05  
Scope: `product-required` only (taxonomy V1 locked)  
Method: usage-first, senior engineering backlog (state machine + API contract + UI wiring)

## 1) Baseline after latest wiring
- Taxonomy decision is locked: `product-required` vs `admin/internal` vs `platform/system`.
- Hooks layer is complete for critical domains (`reservations`, `invoices`, `ventes`, `devis`).
- UI wiring completed on key pages: reservation full flow, invoice audit/full/remind, devis modules/phases/coverage, ventes overdue list.
- Remaining work is now concentrated on residual product capabilities and backend state invariants.

## 2) Residual product-required gaps (closed set)
Statut: **tous les gaps PR-GAP-01..09 sont fermés** (API + Hook + UI branchés).

| Gap ID | Usage | Endpoint(s) | API | Hook | UI | Priority | Status | Notes |
|---|---|---|---|---|---|---|---|---|
| PR-GAP-01 | U5 | `PATCH /reservations/{id}/assign` | Yes | Yes | Yes | P0 | Closed | Delivered in reservation details; user list depends on `users:read` scope. |
| PR-GAP-02 | U7/U6 | `POST /invoices/damage` | Yes | Yes | Yes | P0 | Closed | Delivered in return flow via `useCreateDamageInvoice` (damage charges -> invoice). |
| PR-GAP-03 | U10 | `PATCH /ventes/{id}` | Yes | Yes | Yes | P0 | Closed | Delivered in `VenteEditPage` (deposit %, due date, notes). |
| PR-GAP-04 | U10 | `GET /ventes/{id}/payments` | Yes | Yes | Yes | P0 | Closed | Delivered in vente detail/edit pages via `useVentePayments`. |
| PR-GAP-05 | U4 | `POST /devis/{id}/renew` | Yes | Yes | Yes | P1 | Closed | Delivered in `DevisActions` with cache priming + navigation to renewed draft. |
| PR-GAP-06 | U1 | `GET/PATCH /users/me` vs `GET /auth/me` | Yes | Yes | Yes | P1 | Closed | Convergence closed: `auth/me` = RBAC/scopes source, `users/me` = editable profile source, merge canonique validé en tests store. |
| PR-GAP-07 | U1 | `POST /auth/logout/device/{device_id}` | Yes | Yes | Yes | P1 | Closed | Delivered in sessions UX via `useLogoutDevice` and device-level action button. |
| PR-GAP-08 | U1 | `POST /mfa/stepup/verify` | Yes | Yes | Yes | P1 | Closed | Delivered via `StepUpVerifyModal` gate on sensitive admin action flow. |
| PR-GAP-09 | U12 | `POST /users/{id}/unlock` | Yes | Yes | Yes | P1 | Closed | Delivered in `AdminUserDetailPage` with step-up challenge + retry. |

## 3) Backend correctness blockers (product integrity)
| Blocker ID | Usage | Area | Priority | Error Ref | Status |
|---|---|---|---|---|---|
| BE-BLK-01 | U5/U6 | Reservation state machine inconsistency (`confirm/pre_check/deliver`) | P0 | ERR-013 | Closed |
| BE-BLK-02 | U5/U6 | `pre-check/complete` can force illegal transition | P0 | ERR-014 | Closed |
| BE-BLK-03 | U5/U6 | `extend` transition conflicts with return operation eligibility | P0 | ERR-015 | Closed |
| BE-BLK-04 | U7 | Payment invariants diverge across invoice endpoints | P1 | ERR-017 | Closed |
| BE-BLK-05 | U4 | Devis transitions `negotiation/version_pending` not explicit enough | P1 | ERR-018 | Closed |
| BE-BLK-06 | U10 | Overdue vente transition not reliably fed | P1 | ERR-019 | Closed |

## 3bis) Remaining open backlog (source de vérité: `PHASE1_ERROR_REGISTER`)
| ID | Usage | Scope | Severity | Status | Next closure action |
|---|---|---|---|---|---|
| Aucun | - | - | - | - | Backlog critique phase 1 soldé sur ce périmètre |

## 4) Sprintable task list by module
| Sprint | Ticket | Module | Deliverable | Depends On | DoD (short) |
|---|---|---|---|---|---|
| S1 | TK-RES-ASSIGN-01 | Reservations | Add assignee UI in reservation details + wire `useAssignReservationUser` | - | Assignment persisted, audit visible, tests pass |
| S1 | TK-INV-DAMAGE-01 | Invoices/Operations | Wire damage declaration to `useCreateDamageInvoice` in return flow | BE-BLK-04 | Damage invoice created from return incidents |
| S1 | TK-VTE-UPDATE-01 | Ventes | Wire `useUpdateVente` in edit page (deposit %, due date, notes) | BE-BLK-06 | PATCH path used, data persists and refetches |
| S1 | TK-VTE-PAY-01 | Ventes | Wire `useVentePayments` for payment history and refresh strategy | TK-VTE-UPDATE-01 | Dedicated payments endpoint consumed |
| S1 | TK-BE-RZ-STATE-01 | Backend Reservations | Fix reservation transition guards (`confirm`, `pre-check`, `deliver`, `extend`) | - | Canonical state machine respected |
| S2 | TK-DV-RENEW-01 | Devis | Add renew action in `DevisActions` + optimistic refresh path | - | Renew action available with error handling |
| S2 | TK-ID-PROFILE-01 | Auth/Profile | Create canonical hooks for profile read/write, remove direct `api.patch('/users/me')` | - | Query-first profile flow in place |
| S2 | TK-ID-SESSION-01 | Auth/Sessions | Expose logout device action in sessions UI | - | Revoke current/other devices supported |
| S2 | TK-BE-INV-RULES-01 | Backend Invoices | Align payment business rules across `/payments` and `/add-payment` | - | Single invariant set, integration tests green |
| S3 | TK-ID-STEPUP-01 | Auth/Security | Implement step-up hook + UX gate for sensitive mutations | - | Step-up challenge enforced where required |
| S3 | TK-ADM-UNLOCK-01 | Admin Users | Add unlock account action with confirmation and audit feedback | - | Locked user can be unlocked via UI |
| S3 | TK-BE-DV-TRANS-01 | Backend Devis | Harden explicit transitions for `negotiation/version_pending` | - | Transition matrix covered by tests |
| S4 | TK-CROSS-API-01 | Cross-cutting | Reduce direct API allowlist from 9 to <=10 (priority modules first) | S1/S2 | Query hooks become default in pages/components |
| S4 | TK-CROSS-CI-01 | Platform | Add CI gate on product-required coverage and allowlist delta | TK-CROSS-API-01 | Failing gate on new regressions |

## 5) Priority order (decision)
1. S1 is mandatory before new feature expansion.
2. S2 starts only when S1 backend blockers are closed.
3. S3 can run in parallel with S2 backend tasks if ownership is split.
4. S4 is merge-gate hardening and debt cap, not optional.

## 6) Tracking fields per ticket
- `usage_id` (`U1..U12`)
- `endpoints`
- `frontend_files`
- `backend_files`
- `state_transition`
- `tenant_isolation_impact`
- `rbac_impact`
- `tests_added` (unit/integration/e2e)
- `rollback_plan`

## 7) Immediate execution recommendation
1. Keep `TK-CROSS-API-01` under CI guard with zero-debt budget locked (`allowlist` active = 0).
2. Open hardening task for asyncpg warning cleanup in test runtime (`Connection._cancel` unawaited warnings).
3. Maintenir un run périodique de revalidation intégration ciblée sur transitions critiques.

## 8) Execution log (2026-03-05)
- `TK-RES-ASSIGN-01`: Delivered in reservation details UI (assign/unassign + self-assign action).
- `TK-VTE-UPDATE-01`: Delivered in vente edit UI (persist sale parameters via PATCH).
- `TK-VTE-PAY-01`: Delivered in vente detail/edit UI (payments via dedicated `GET /ventes/{id}/payments` endpoint).
- `TK-INV-DAMAGE-01`: Delivered in return flow UI (damage invoice creation via `POST /invoices/damage`).
- `TK-BE-RZ-STATE-01`: Delivered — transition guards aligned and validated in integration (`tests/integration/test_operations.py` + `tests/integration/test_reservation_advanced.py`: 57 passed).
- `TK-DV-RENEW-01`: Delivered — renew action wired in Devis UI (`DevisActions`) with error handling and cache-primed refresh/navigation path.
- `TK-ID-PROFILE-01`: Delivered — canonical profile hooks (`useMyProfile`, `useUpdateMyProfile`) added and `ProfilePage` migrated off direct `api.patch('/users/me')`.
- `TK-ID-SESSION-01`: Delivered — device-level logout wired in sessions UX (`useLogoutDevice` + action button), backend session responses enriched with `device_id`, and endpoint bugfix (`await redis_client.logout_device(...)`).
- `TK-ID-SESSION-01` validation note: frontend tests/build green; integration suite `tests/integration/test_sessions.py` not runnable in this environment due local PostgreSQL connectivity (OperationalError during fixture setup).
- `TK-BE-INV-RULES-01`: Delivered — payment invariants unified via shared backend rule (`/add-payment` + `/payments`), with integration validation green (`tests/integration/test_payments.py`: 13 passed; `tests/integration/test_invoices_endpoints.py`: 17 passed).
- `TK-ID-STEPUP-01`: Delivered (initial slice) — step-up verify hook + modal flow implemented; sensitive admin unlock action now triggers MFA step-up gate and retries on success.
- `ERR-006` closure slice: Delivered — canonical convergence validated (`auth/me` remains authority for role/scopes, `users/me` for editable profile), with dedicated store tests passing (`src/stores/__tests__/authStore.test.ts`: 22 passed).
- `TK-CROSS-API-01` lot 2: Delivered — auth surfaces migrated to query hooks (`useLogin/useMfaVerify/useLogout/useForgotPassword/useResetPassword/useChangePassword/useOAuthProviders/useOAuthAuthorize/useOAuthCallback`), reducing direct API files from 40 to 29; frontend build + targeted tests green.
- `TK-CROSS-API-01` lot 3: Delivered — invoices/inventory/events surfaces migrated to query hooks (`useReservationDeposits`, `useFinancesStats`, `useInvoicesList`, `useAddPaymentRecord`, `useAllInvoicePayments`, `useInvoiceTvaReport`, `useInvoicePdf`, `useMarkInvoiceSent`, `useProductStock`, `useUpdateStockItemStatus`, `useUploadReservationSignature`, `useCloseReservationDispute`), reducing direct API files from 29 to 16; frontend build + targeted tests green.
- `TK-CROSS-API-01` lot 4: Delivered — catalogue/customers/dashboard/events wrappers migrated to query hooks (`useDashboardExportCsv`, `useProductImages` family, `useProductAvailability`, `useSendRfmCampaign`, `useUsers`, `useDamageTypesList`, `useLogin/useMfaVerify/useLogout/useLogoutAllSessions` in `useAuth`), reducing direct API files from 16 to 9 (target `<=10` achieved); frontend build + targeted tests green.
- `TK-CROSS-API-01` lot 5: Delivered — residual 9-file allowlist migrated (`CataloguePickerModal`, `CatalogueBuilderPage`, `AdminUserDetailPage`, `VpnPage`, `InventoryPage`, `DamageDeclarationModal`, `ProductImportPage`, `stores/authStore.ts`, `stores/uiStore.ts`) via query hooks/query-layer helpers (`useProductsList/useCategoriesList/useBundlesList`, `useUserDetail`, `useVpn*`, `fetchProductStockDetail`, `useUploadDamagePhoto`, `useImportProductsCsv`, `fetchAuthMe/fetchMyProfile/fetchAuthCsrfToken`); targeted tests + build + `check:api-access` green.
- `TK-CROSS-CI-01`: Delivered — CI guard hardened with allowlist delta budget (`max_allowlist_entries`, `max_active_allowlisted_files`) in `frontend/scripts/check-api-access.mjs` + `frontend/config/api-access-allowlist.json`; runtime scope excludes tests, stale allowlist cleanup enforced by budget; `check:api-access` and build green.
- `TK-CROSS-API-01` lot 6: Delivered — last residual `src/stores/authStore.ts` decoupled from direct `@/api/fetchClient` import via query-layer bridge (`api/queries/clientBridge.ts`); allowlist reduced to 0 with budget locked at 0; `check:api-access` (`active=0, entries=0`) + auth store tests + build green.
- `G0-05`: Delivered — ESLint blocking rule added (`no-restricted-imports`) to forbid direct `@/api/*` imports outside runtime allowed layers (`src/api/**`, `src/api/queries/**`; tests excluded).
- `G0-05` hardening slice: Delivered — removed 6 `react-hooks/exhaustive-deps` warnings on product pages, introduced lint warning budget gate (`frontend/config/lint-warning-budget.json` + `npm run lint:warnings:budget`) and CI step `npm run lint:strict` (errors + no warning budget regression).
- `G0-05` burn-down slice 2: Delivered — spacing-token normalization batches across high-warning pages/components reduced `no-restricted-syntax` warnings from `1603` to `0`; budget updated to `0` and validated with `npm run lint:strict`.
- `H2-01` hook/backend coverage slice: Delivered — missing surfaces added for audit targeted queries (`/audit/user/{id}`, `/audit/entity/{type}/{id}`), inventory today (`/inventory-movements/today`), unified order detail (`/orders/{type}/{id}`), products low-stock (`/products/low-stock`) with corresponding query hooks (`useUserAuditLogs`, `useEntityAuditLogs`, `useTodayMovementsAgenda`, `useOrderDetail`, `useLowStockProducts`); details tracked in `docs/PHASE2_HOOK_BACKEND_GAP_REGISTER.md`.
- `H2-02` taxonomy+coverage hardening: Delivered — taxonomy synced with devis advanced transitions (`POST /devis/{id}/negotiation/start`, `POST /devis/{id}/version-pending`) and new AST coverage reporter added (`npm run report:endpoint-coverage`); current report: `product_missing_in_frontend_count=0`, `api_functions_without_hook_count=0`.
- `H2-03` wiring produit hooks/backend: Delivered — hooks activés dans pages produit (`CommandesListPage` aperçu via `useOrderDetail`, `InventoryPage` low-stock + agenda today, `StockAlertPage` contexte low-stock) et transitions devis explicites branchées (`startNegotiation`, `markVersionPending`) dans `DevisDetailPage`, `DevisIdLayout`, `DevisChangeRequestPage`; lint/build/check-api-access/report coverage green.
- `H2-04` CI observabilité coverage: Delivered — workflow frontend CI enrichi avec reporting non bloquant `report-endpoint-coverage` et upload d'artefact JSON `endpoint-coverage-report` (`.github/workflows/ci.yml`).
- `H2-05` gouvernance scanner coverage: Delivered — exception système `GET /.well-known/jwks.json` traitée explicitement dans le reporter (`system_exceptions`), `taxonomy_orphans_count` ramené à `0` sans régression des compteurs produit.
- `H2-06` clôture `ERR-020`: Delivered — contrat ventes/statuts FE/BE harmonisé (`sale_date` -> `created_at`, suppression champ création non supporté, filtres `date_from/date_to/search` supportés backend) + garde CI `check-critical-contracts` étendue à ERR-020.
- `H2-07` clôture `ERR-016`: Delivered — annulation réservations terminales verrouillée et validée en intégration DB locale (`test_cancel_reservation_completed_forbidden`, `test_cancel_reservation_returned_dispute_forbidden`).
- `H2-08` clôture `ERR-018`: Delivered — transitions devis `negotiation/version_pending` revalidées en DB locale (3 tests d’intégration dédiés green).
- `H2-09` clôture `ERR-019`: Delivered — transitions overdue revalidées en DB locale (`TestVenteOverdue` x3 green).
- `H2-10` clôture `ERR-025`: Delivered — hardening `tests/conftest.py` (`_truncate_all_sync`) + run consolidé `ERR-016/018/019` vert sans deadlock ni warning async.
