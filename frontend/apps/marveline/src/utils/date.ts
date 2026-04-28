/**
 * Parse une chaîne de date ISO "date seule" (YYYY-MM-DD) en heure locale.
 * `new Date("2026-03-15")` est parsé en UTC → décale d'un jour sur les fuseaux < 0.
 * Ajouter T00:00:00 force l'interprétation en heure locale.
 */
export function parseDateLocal(dateStr: string): Date {
  return new Date(dateStr + 'T00:00:00')
}
