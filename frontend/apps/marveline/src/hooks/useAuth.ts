import { useCallback } from 'react';
import { useNavigate } from '@tanstack/react-router';
import { useAuthStore } from '../stores/authStore';
import { useLogin, useLogout, useLogoutAllSessions, useMfaVerify } from '@/api/queries/useAuth';
import type { LoginRequest } from '../types';

/**
 * Hook pour gérer l'authentification
 * Encapsule le store et fournit des méthodes pratiques
 */
export function useAuth() {
  const navigate = useNavigate();
  const {
    user,
    isAuthenticated,
    isLoading,
    mfaSessionToken,
    setTokens,
    setMfaSessionToken,
    logout: storeLogout,
    initialize,
    fetchUser,
  } = useAuthStore();
  const loginMutation = useLogin();
  const mfaVerifyMutation = useMfaVerify();
  const logoutMutation = useLogout();
  const logoutAllMutation = useLogoutAllSessions();

  // Login avec email/password
  const login = useCallback(
    async (credentials: LoginRequest) => {
      const response = await loginMutation.mutateAsync({ credentials });

      // Si MFA requis
      if (response.mfa_required && response.mfa_session_token) {
        setMfaSessionToken(response.mfa_session_token);
        return { mfaRequired: true };
      }

      // Login réussi — backend renvoie uniquement access_token (refresh via httpOnly cookie)
      if (response.access_token) {
        setTokens(response.access_token);
        await fetchUser();
        // INC-07 : mot de passe compromis ou expiré — redirection forcée (spec §04 §4.7)
        if (response.password_change_required) {
          navigate({ to: '/profile/security' });
          return { mfaRequired: false, passwordChangeRequired: true };
        }
        return { mfaRequired: false };
      }

      throw new Error('Réponse de login invalide');
    },
    [setMfaSessionToken, setTokens, fetchUser, loginMutation, navigate]
  );

  // Vérification MFA
  const verifyMfa = useCallback(
    async (code: string) => {
      if (!mfaSessionToken) {
        throw new Error('Pas de session MFA active');
      }

      const response = await mfaVerifyMutation.mutateAsync({
        mfa_session_token: mfaSessionToken,
        code,
      });

      if (response.access_token) {
        setTokens(response.access_token);
        await fetchUser();
        setMfaSessionToken('');
        return useAuthStore.getState().user;
      }

      throw new Error('Vérification MFA échouée');
    },
    [fetchUser, mfaSessionToken, mfaVerifyMutation, setMfaSessionToken, setTokens]
  );

  // Logout
  const logout = useCallback(
    async (redirectTo = '/login') => {
      try {
        await logoutMutation.mutateAsync();
      } catch (error) {
        console.error('Erreur lors du logout:', error);
      } finally {
        storeLogout();
        navigate({ to: redirectTo });
      }
    },
    [logoutMutation, navigate, storeLogout]
  );

  // Logout de toutes les sessions
  const logoutAllSessions = useCallback(async () => {
    await logoutAllMutation.mutateAsync();
    storeLogout();
    navigate({ to: '/login' });
  }, [logoutAllMutation, navigate, storeLogout]);

  // isAdmin : affichage uniquement (profil, badges) — pour le RBAC utiliser useHasScope()
  const isAdmin = user?.role === 'admin' || user?.role === 'tenant_admin';

  return {
    // State
    user,
    isAuthenticated,
    isLoading,
    isAdmin,
    mfaSessionToken,

    // Actions
    login,
    verifyMfa,
    logout,
    logoutAllSessions,
    initialize,
  };
}
