import type { ErrorCategory } from './types'

// --- User-facing error messages (French) ---

export const ERROR_TITLES: Record<ErrorCategory, string> = {
  network: 'Probleme de connexion',
  auth: 'Erreur d\'authentification',
  validation: 'Donnees invalides',
  not_found: 'Ressource introuvable',
  forbidden: 'Acces refuse',
  server: 'Erreur serveur',
  chunk_load: 'Erreur de chargement',
  unknown: 'Erreur inattendue',
}

export const ERROR_MESSAGES: Record<ErrorCategory, string> = {
  network: 'Impossible de joindre le serveur. Verifiez votre connexion internet.',
  auth: 'Votre session a expire. Veuillez vous reconnecter.',
  validation: 'Les donnees envoyees sont invalides. Verifiez le formulaire.',
  not_found: 'La ressource demandee n\'existe pas ou a ete supprimee.',
  forbidden: 'Vous n\'avez pas les droits pour effectuer cette action.',
  server: 'Une erreur est survenue sur le serveur. Reessayez dans quelques instants.',
  chunk_load: 'Un module de l\'application n\'a pas pu etre charge. Rechargez la page.',
  unknown: 'Une erreur inattendue est survenue.',
}

export const ERROR_ACTIONS: Record<ErrorCategory, string> = {
  network: 'Reessayer',
  auth: 'Se reconnecter',
  validation: 'Corriger',
  not_found: 'Retour a l\'accueil',
  forbidden: 'Retour a l\'accueil',
  server: 'Reessayer',
  chunk_load: 'Recharger la page',
  unknown: 'Reessayer',
}

// --- HTTP status → category mapping ---

export const STATUS_CATEGORY_MAP: Record<number, ErrorCategory> = {
  400: 'validation',
  401: 'auth',
  403: 'forbidden',
  404: 'not_found',
  409: 'validation',
  422: 'validation',
  429: 'network', // rate limit treated as transient
  500: 'server',
  502: 'server',
  503: 'server',
  504: 'network', // gateway timeout = network-like
}
