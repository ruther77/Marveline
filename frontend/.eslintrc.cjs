module.exports = {
  root: true,
  env: {
    browser: true,
    es2020: true,
  },
  parser: '@typescript-eslint/parser',
  parserOptions: {
    ecmaVersion: 'latest',
    sourceType: 'module',
    ecmaFeatures: {
      jsx: true,
    },
  },
  plugins: ['@typescript-eslint', 'react-hooks', 'react-refresh'],
  extends: [
    'eslint:recommended',
    'plugin:@typescript-eslint/recommended',
    'plugin:react-hooks/recommended',
  ],
  rules: {
    'no-unused-vars': 'off',
    '@typescript-eslint/no-unused-vars': 'off',
    '@typescript-eslint/no-explicit-any': 'off',
    'react-refresh/only-export-components': 'off',

    // ─── Layout system enforcement ────────────────────────────────────────────
    // Interdit les espacements non-multiples de 8px (p-3=12px, gap-3=12px, etc.)
    // Règle : tout espacement doit être multiple de 4 ou 8px.
    // Valeurs interdites : 3, 5, 7 (12px, 20px, 28px hors système).
    // Pour contourner légitimement : ajouter eslint-disable avec justification.
    'no-restricted-syntax': [
      'warn',
      // Espacements arbitraires dans className (JSX)
      {
        selector: 'JSXAttribute[name.name="className"] Literal[value=/\\b(p|px|py|pt|pr|pb|pl|m|mx|my|mt|mr|mb|ml|gap|gap-x|gap-y|space-x|space-y)-[357]\\b/]',
        message: 'Espacement non-multiple de 8px détecté (p-3, gap-3, p-5…). Utiliser p-2 (8px), p-4 (16px) ou p-6 (24px). Voir docs/plans/AUDIT-LAYOUT-III-2026-02-24.md',
      },
      // Espacements arbitraires dans cn() / clsx() (template literals et appels)
      {
        selector: 'CallExpression[callee.name=/^(cn|clsx|cx)$/] Literal[value=/\\b(p|px|py|pt|pr|pb|pl|m|mx|my|mt|mr|mb|ml|gap|gap-x|gap-y|space-x|space-y)-[357]\\b/]',
        message: 'Espacement non-multiple de 8px détecté (p-3, gap-3, p-5…). Utiliser p-2 (8px), p-4 (16px) ou p-6 (24px). Voir docs/plans/AUDIT-LAYOUT-III-2026-02-24.md',
      },
      // Z-index arbitraires hors système (z-[N] avec N > 100)
      {
        selector: 'JSXAttribute[name.name="className"] Literal[value=/\\bz-\\[([2-9]\\d{2,}|1[1-9]\\d|10[1-9])\\]/]',
        message: 'Z-index arbitraire hors système détecté. Utiliser les classes z-10/z-20/z-30/z-40/z-50 ou style={{ zIndex: Z.TOAST }} pour les toasts. Voir src/config/zindex.ts',
      },
    ],
  },
  overrides: [
    {
      files: ['src/**/*.{ts,tsx}'],
      excludedFiles: [
        'src/api/**/*.{ts,tsx}',
        'src/api/queries/**/*.{ts,tsx}',
        'src/**/__tests__/**/*.{ts,tsx}',
        'src/**/*.test.{ts,tsx}',
        'src/**/*.spec.{ts,tsx}',
      ],
      rules: {
        'no-restricted-imports': [
          'error',
          {
            patterns: [
              {
                group: ['@/api/*', '!@/api/queries', '!@/api/queries/*'],
                message: 'Import API direct interdit hors couches autorisées. Utiliser les hooks depuis @/api/queries.',
              },
            ],
          },
        ],
      },
    },
  ],
  ignorePatterns: ['dist', 'node_modules'],
};
