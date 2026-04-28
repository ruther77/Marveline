import { api } from './fetchClient'
import type { User } from '@/types'

export interface UserProfileUpdatePayload {
  email?: string
  first_name?: string
  last_name?: string
  password?: string
  address?: string
  postal_code?: string
}

export const usersApi = {
  getMyProfile: async (): Promise<User> => {
    return api.get<User>('/users/me')
  },

  updateMyProfile: async (payload: UserProfileUpdatePayload): Promise<User> => {
    return api.patch<User>('/users/me', payload)
  },
}
