import { useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';
import { authApi } from '../api/auth';
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
    setUser,
    setTokens,
    setMfaSessionToken,
    logout: storeLogout,
    initialize,
  } = useAuthStore();

  // Login avec email/password
  const login = useCallback(
    async (credentials: LoginRequest) => {
      const response = await authApi.login(credentials);

      // Si MFA requis
      if (response.mfa_required && response.mfa_session_token) {
        setMfaSessionToken(response.mfa_session_token);
        return { mfaRequired: true };
      }

      // Login réussi
      if (response.access_token && response.refresh_token && response.user) {
        setTokens(response.access_token, response.refresh_token);
        setUser(response.user);
        return { mfaRequired: false, user: response.user };
      }

      throw new Error('Réponse de login invalide');
    },
    [setMfaSessionToken, setTokens, setUser]
  );

  // Vérification MFA
  const verifyMfa = useCallback(
    async (code: string) => {
      if (!mfaSessionToken) {
        throw new Error('Pas de session MFA active');
      }

      const response = await authApi.mfaVerify({
        mfa_session_token: mfaSessionToken,
        code,
      });

      if (response.access_token && response.refresh_token && response.user) {
        setTokens(response.access_token, response.refresh_token);
        setUser(response.user);
        setMfaSessionToken('');
        return response.user;
      }

      throw new Error('Vérification MFA échouée');
    },
    [mfaSessionToken, setTokens, setUser, setMfaSessionToken]
  );

  // Logout
  const logout = useCallback(
    async (redirectTo = '/login') => {
      try {
        await authApi.logout();
      } catch (error) {
        console.error('Erreur lors du logout:', error);
      } finally {
        storeLogout();
        navigate(redirectTo);
      }
    },
    [storeLogout, navigate]
  );

  // Logout de toutes les sessions
  const logoutAllSessions = useCallback(async () => {
    await authApi.logoutAll();
    storeLogout();
    navigate('/login');
  }, [storeLogout, navigate]);

  // Vérifier si l'utilisateur a un rôle
  const hasRole = useCallback(
    (role: string) => {
      if (!user) return false;
      // Adapter selon votre structure de rôles
      if (role === 'admin' || role === 'superuser') {
        return user.is_superuser;
      }
      return true;
    },
    [user]
  );

  // Vérifier si l'utilisateur est admin
  const isAdmin = user?.is_superuser ?? false;

  // Vérifier si MFA est activé
  const isMfaEnabled = user?.mfa_enabled ?? false;

  return {
    // State
    user,
    isAuthenticated,
    isLoading,
    isAdmin,
    isMfaEnabled,
    mfaSessionToken,

    // Actions
    login,
    verifyMfa,
    logout,
    logoutAllSessions,
    initialize,
    hasRole,
  };
}
