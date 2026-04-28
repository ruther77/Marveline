import { useQuery } from '@tanstack/react-query'
import { adminApi } from '../../admin'

/**
 * Hook global pour charger la liste complète des utilisateurs actifs du tenant.
 * Une seule entrée de cache partagée par toute l'app → évite les requêtes
 * dupliquées entre composants (AssignSection, modals d'affectation, planning).
 *
 * staleTime 10 min : la liste utilisateurs évolue rarement à l'échelle d'une session.
 * Pour la pagination réelle (UsersPage admin), utiliser useUsers avec skip/limit.
 */
export function useGlobalUsers() {
  return useQuery({
    queryKey: ['global-users'],
    queryFn: () => adminApi.listUsers({ skip: 0, limit: 500 }),
    staleTime: 10 * 60 * 1000,
    gcTime: 30 * 60 * 1000,
  })
}
