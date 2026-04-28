import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { queryKeys } from './keys'
import { usersApi, type UserProfileUpdatePayload } from '../users'

export async function fetchMyProfile() {
  return usersApi.getMyProfile()
}

export function useMyProfile(enabled = true) {
  return useQuery({
    queryKey: queryKeys.users.me(),
    queryFn: () => usersApi.getMyProfile(),
    enabled,
    staleTime: 60 * 1000,
  })
}

export function useUpdateMyProfile() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: UserProfileUpdatePayload) => usersApi.updateMyProfile(payload),
    onSuccess: (updatedUser) => {
      qc.setQueryData(queryKeys.users.me(), updatedUser)
      // /auth/me reste la source de vérité permissions/scopes; on force un refresh.
      qc.invalidateQueries({ queryKey: queryKeys.auth.me() })
    },
  })
}
