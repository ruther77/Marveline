# Design — Accessibilité

## Standard : WCAG 2.1 AA

Objectif minimum : conformité WCAG 2.1 niveau AA pour tous les écrans.

## axe-playwright (Tests Automatisés)

```typescript
// tests/e2e/accessibility.spec.ts
import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test.describe('Accessibility', () => {
    test('dashboard has no WCAG 2.1 AA violations', async ({ page }) => {
        await page.goto('/dashboard');
        await page.waitForLoadState('networkidle');

        const results = await new AxeBuilder({ page })
            .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
            .analyze();

        expect(results.violations).toEqual([]);
    });

    test('invoice modal is accessible', async ({ page }) => {
        await page.goto('/invoices');
        await page.click('button:has-text("Nouvelle facture")');

        const results = await new AxeBuilder({ page })
            .include('.modal')
            .withTags(['wcag2a', 'wcag2aa'])
            .analyze();

        expect(results.violations).toEqual([]);
    });
});
```

## Lighthouse CI

```json
// .lighthouserc.json
{
    "ci": {
        "collect": {
            "url": ["http://localhost:3000/dashboard"],
            "numberOfRuns": 3
        },
        "assert": {
            "assertions": {
                "categories:performance":   ["warn", {"minScore": 0.8}],
                "categories:accessibility": ["error", {"minScore": 0.9}],
                "categories:best-practices": ["warn", {"minScore": 0.9}],
                "categories:seo":           ["warn", {"minScore": 0.8}],
                "first-contentful-paint":   ["warn", {"maxNumericValue": 2000}],
                "largest-contentful-paint": ["warn", {"maxNumericValue": 3000}],
                "cumulative-layout-shift":  ["warn", {"maxNumericValue": 0.1}],
                "total-blocking-time":      ["warn", {"maxNumericValue": 500}]
            }
        },
        "upload": {
            "target": "temporary-public-storage"
        }
    }
}
```

```yaml
# .github/workflows/lighthouse.yml
- name: Run Lighthouse CI
  run: |
    npm install -g @lhci/cli
    lhci autorun
  env:
    LHCI_GITHUB_APP_TOKEN: ${{ secrets.LHCI_GITHUB_APP_TOKEN }}
```

## Règles HTML/JSX

```tsx
// Boutons : toujours un texte accessible
<button aria-label="Fermer la modal">
    <XIcon className="w-5 h-5" aria-hidden="true" />
</button>

// Images : alt descriptif ou vide si décorative
<img src="/logo.png" alt="Marveline logo" />
<img src="/decoration.svg" alt="" aria-hidden="true" />

// Formulaires : labels associés
<label htmlFor="invoice-amount">Montant</label>
<input id="invoice-amount" type="number" aria-required="true" />

// Erreurs : aria-describedby
<input
    id="email"
    aria-invalid={!!errors.email}
    aria-describedby={errors.email ? "email-error" : undefined}
/>
{errors.email && (
    <p id="email-error" role="alert">{errors.email.message}</p>
)}

// Navigation : landmarks
<main>
    <h1>Tableau de bord</h1>
    <nav aria-label="Navigation principale">...</nav>
    <section aria-labelledby="stats-heading">
        <h2 id="stats-heading">Statistiques</h2>
    </section>
</main>

// Focus management (modals)
const modalRef = useRef<HTMLDivElement>(null);
useEffect(() => {
    if (isOpen) modalRef.current?.focus();
}, [isOpen]);

<div
    ref={modalRef}
    role="dialog"
    aria-modal="true"
    aria-labelledby="modal-title"
    tabIndex={-1}
>
    <h2 id="modal-title">Titre du modal</h2>
</div>
```

## Contraste des Couleurs

```
# WCAG AA minimums
Texte normal : ratio ≥ 4.5:1
Texte large (≥ 18px bold ou ≥ 24px) : ratio ≥ 3:1
Éléments UI (boutons, inputs) : ratio ≥ 3:1

# Vérifier avec : https://webaim.org/resources/contrastchecker/
# primary-600 (#2563eb) sur blanc : 4.54:1 ✓
# gray-500 (#6b7280) sur blanc : 4.63:1 ✓
```

## Navigation Clavier

```tsx
// Trap focus dans les modals
function useFocusTrap(isActive: boolean, containerRef: RefObject<HTMLElement>) {
    useEffect(() => {
        if (!isActive || !containerRef.current) return;

        const focusable = containerRef.current.querySelectorAll<HTMLElement>(
            'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        const first = focusable[0];
        const last = focusable[focusable.length - 1];

        const handleTab = (e: KeyboardEvent) => {
            if (e.key !== 'Tab') return;
            if (e.shiftKey && document.activeElement === first) {
                last.focus(); e.preventDefault();
            } else if (!e.shiftKey && document.activeElement === last) {
                first.focus(); e.preventDefault();
            }
        };

        document.addEventListener('keydown', handleTab);
        first?.focus();
        return () => document.removeEventListener('keydown', handleTab);
    }, [isActive, containerRef]);
}
```

## Checklist Accessibilité

- ☐ Tous les boutons icon ont `aria-label`
- ☐ Toutes les images ont `alt` (descriptif ou vide si décoratif)
- ☐ Labels associés aux inputs via `htmlFor` / `id`
- ☐ Erreurs annoncées via `role="alert"` ou `aria-describedby`
- ☐ Modals : `role="dialog"`, `aria-modal`, `aria-labelledby`, focus trap
- ☐ Contraste couleurs vérifié (≥ 4.5:1 texte normal)
- ☐ Navigation 100% au clavier possible
- ☐ axe-playwright passe sans violation
- ☐ Lighthouse Accessibility ≥ 90
