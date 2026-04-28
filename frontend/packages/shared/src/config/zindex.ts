/**
 * Échelle z-index globale — NE PAS utiliser de valeurs hors de cet objet.
 *
 * Règle : aucun z-index arbitraire (z-[...]) dans le projet.
 * Si un nouveau layer est nécessaire, l'ajouter ici avec justification.
 *
 * Tailwind : pour utiliser ces valeurs dans className, préférer les classes
 * correspondantes (z-10, z-20, …) documentées ci-dessous.
 * Pour les cas dynamiques (style={{ zIndex: Z.MODAL }}), utiliser cet objet.
 */
export const Z = {
  /** Nul — flux normal */
  BASE: 0,

  /** z-10 — Headers sticky (table, sections) */
  ELEVATED: 10,

  /** z-20 — Context menus, popovers ancrés */
  DROPDOWN: 20,

  /** z-30 — Navigation layout, panels de filtres */
  NAVIGATION: 30,

  /** z-40 — Backdrops de modals, menus latéraux */
  OVERLAY: 40,

  /** z-50 — Modals, bottom sheets, tooltips, dropdowns */
  MODAL: 50,

  /**
   * z-[100] — Toasts uniquement.
   * Exception justifiée : doit passer au-dessus de tout composant,
   * y compris les modals empilés.
   */
  TOAST: 100,
} as const;

export type ZLevel = (typeof Z)[keyof typeof Z];
