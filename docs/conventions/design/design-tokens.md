# Design — Design Tokens

## Principe

Les design tokens centralisent toutes les valeurs visuelles (couleurs, typographie, espacement, ombres) pour assurer la cohérence et faciliter le theming (dark mode, white-label).

## CSS Custom Properties

```css
/* src/styles/tokens.css */
:root {
    /* Couleurs brand */
    --color-primary-50:  #eff6ff;
    --color-primary-100: #dbeafe;
    --color-primary-500: #3b82f6;
    --color-primary-600: #2563eb;
    --color-primary-700: #1d4ed8;
    --color-primary-900: #1e3a8a;

    /* Couleurs sémantiques */
    --color-success: #10b981;
    --color-warning: #f59e0b;
    --color-error:   #ef4444;
    --color-info:    #06b6d4;

    /* Couleurs neutrales */
    --color-gray-50:  #f9fafb;
    --color-gray-100: #f3f4f6;
    --color-gray-200: #e5e7eb;
    --color-gray-500: #6b7280;
    --color-gray-700: #374151;
    --color-gray-900: #111827;

    /* Typographie */
    --font-sans:  'Sora', 'Inter', system-ui, sans-serif;
    --font-body:  'Manrope', 'Inter', system-ui, sans-serif;
    --font-mono:  'JetBrains Mono', 'Fira Code', monospace;

    /* Tailles de police */
    --text-xs:   0.75rem;   /* 12px */
    --text-sm:   0.875rem;  /* 14px */
    --text-base: 1rem;      /* 16px */
    --text-lg:   1.125rem;  /* 18px */
    --text-xl:   1.25rem;   /* 20px */
    --text-2xl:  1.5rem;    /* 24px */

    /* Line heights */
    --leading-tight:  1.25;
    --leading-normal: 1.5;
    --leading-relaxed: 1.75;

    /* Espacement (8pt grid) */
    --space-1: 0.25rem;   /* 4px */
    --space-2: 0.5rem;    /* 8px */
    --space-3: 0.75rem;   /* 12px */
    --space-4: 1rem;      /* 16px */
    --space-6: 1.5rem;    /* 24px */
    --space-8: 2rem;      /* 32px */
    --space-12: 3rem;     /* 48px */
    --space-16: 4rem;     /* 64px */

    /* Bordures */
    --radius-sm:   0.25rem;
    --radius-md:   0.375rem;
    --radius-lg:   0.5rem;
    --radius-xl:   0.75rem;
    --radius-full: 9999px;

    /* Ombres */
    --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
    --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1);
    --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1);

    /* Z-index */
    --z-dropdown: 100;
    --z-modal:    200;
    --z-toast:    300;
    --z-tooltip:  400;
}

/* Dark mode */
@media (prefers-color-scheme: dark) {
    :root {
        --color-gray-50: #111827;
        --color-gray-100: #1f2937;
        /* ... */
    }
}
```

## Tailwind Config

```javascript
// tailwind.config.js
module.exports = {
    content: ['./src/**/*.{tsx,ts,jsx,js}'],
    theme: {
        extend: {
            colors: {
                primary: {
                    50:  'var(--color-primary-50)',
                    100: 'var(--color-primary-100)',
                    500: 'var(--color-primary-500)',
                    600: 'var(--color-primary-600)',
                    700: 'var(--color-primary-700)',
                    900: 'var(--color-primary-900)',
                },
                success: 'var(--color-success)',
                warning: 'var(--color-warning)',
                error:   'var(--color-error)',
            },
            fontFamily: {
                sans: ['var(--font-sans)'],
                body: ['var(--font-body)'],
                mono: ['var(--font-mono)'],
            },
            spacing: {
                // Mapping tokens → utilitaires Tailwind
            },
        },
    },
};
```

## Tokens TypeScript (pour styled-components / CSS-in-JS)

```typescript
// src/styles/tokens.ts
export const tokens = {
    colors: {
        primary: {
            50:  'var(--color-primary-50)',
            500: 'var(--color-primary-500)',
            600: 'var(--color-primary-600)',
        },
        semantic: {
            success: 'var(--color-success)',
            warning: 'var(--color-warning)',
            error:   'var(--color-error)',
        },
    },
    fontSizes: {
        xs:   'var(--text-xs)',
        sm:   'var(--text-sm)',
        base: 'var(--text-base)',
        lg:   'var(--text-lg)',
    },
    space: {
        1: 'var(--space-1)',
        2: 'var(--space-2)',
        4: 'var(--space-4)',
        8: 'var(--space-8)',
    },
} as const;
```

## Zustand Immer (State avec Immutabilité)

```typescript
// Utiliser Immer pour les updates complexes de state
import { immer } from 'zustand/middleware/immer';

const useStore = create<State>()(
    immer((set) => ({
        items: [],
        addItem: (item) => set((state) => {
            state.items.push(item);  // Mutation directe — Immer gère l'immutabilité
        }),
        updateItem: (id, updates) => set((state) => {
            const item = state.items.find(i => i.id === id);
            if (item) Object.assign(item, updates);
        }),
    }))
);
```

## Règles Design Tokens

- Toutes les valeurs visuelles passent par des tokens CSS custom
- Jamais de valeurs hardcodées (`#3b82f6`) dans les composants — utiliser `var(--color-primary-500)`
- Grille d'espacement : multiples de 4px (8pt grid)
- Dark mode via `@media (prefers-color-scheme: dark)` sur `:root`
- Tokens TS pour usage programmatique (animations, calculs)
