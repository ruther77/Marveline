import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { authApi } from '@/api/auth';

// ============================================
// Types
// ============================================

export type Theme = 'light' | 'dark' | 'system';
export type SidebarState = 'expanded' | 'collapsed' | 'hidden';

export interface Notification {
  id: string;
  type: 'info' | 'success' | 'warning' | 'error';
  title: string;
  message?: string;
  read: boolean;
  createdAt: Date;
  action?: {
    label: string;
    href?: string;
    onClick?: () => void;
  };
}

export interface UIState {
  // Theme
  theme: Theme;
  resolvedTheme: 'light' | 'dark';

  // Sidebar
  sidebarState: SidebarState;
  sidebarPinned: boolean;

  // Modals globaux
  commandPaletteOpen: boolean;
  searchOpen: boolean;
  settingsOpen: boolean;

  // Notifications
  notifications: Notification[];
  unreadCount: number;

  // Préférences
  compactMode: boolean;
  animationsEnabled: boolean;
  soundEnabled: boolean;

  // Loading global
  globalLoading: boolean;
  globalLoadingMessage: string | null;

  // CSRF token
  csrfToken: string | null;
}

export interface UIActions {
  // Theme
  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;

  // Sidebar
  setSidebarState: (state: SidebarState) => void;
  toggleSidebar: () => void;
  collapseSidebar: () => void;
  expandSidebar: () => void;
  setSidebarPinned: (pinned: boolean) => void;

  // Modals
  openCommandPalette: () => void;
  closeCommandPalette: () => void;
  toggleCommandPalette: () => void;
  openSearch: () => void;
  closeSearch: () => void;
  openSettings: () => void;
  closeSettings: () => void;

  // Notifications
  addNotification: (notification: Omit<Notification, 'id' | 'read' | 'createdAt'>) => void;
  markAsRead: (id: string) => void;
  markAllAsRead: () => void;
  removeNotification: (id: string) => void;
  clearNotifications: () => void;

  // Préférences
  setCompactMode: (enabled: boolean) => void;
  setAnimationsEnabled: (enabled: boolean) => void;
  setSoundEnabled: (enabled: boolean) => void;

  // Loading
  setGlobalLoading: (loading: boolean, message?: string) => void;

  // CSRF
  setCsrfToken: (token: string) => void;
  fetchCsrfToken: () => Promise<void>;
  clearCsrfToken: () => void;
}

// ============================================
// Store
// ============================================

const getSystemTheme = (): 'light' | 'dark' => {
  if (typeof window !== 'undefined') {
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  return 'dark';
};

const resolveTheme = (theme: Theme): 'light' | 'dark' => {
  if (theme === 'system') {
    return getSystemTheme();
  }
  return theme;
};

export const useUIStore = create<UIState & UIActions>()(
  persist(
    (set, get) => ({
      // Initial state
      theme: 'dark',
      resolvedTheme: 'dark',
      sidebarState: 'expanded',
      sidebarPinned: true,
      commandPaletteOpen: false,
      searchOpen: false,
      settingsOpen: false,
      notifications: [],
      unreadCount: 0,
      compactMode: false,
      animationsEnabled: true,
      soundEnabled: true,
      globalLoading: false,
      globalLoadingMessage: null,
      csrfToken: null,

      // Theme actions
      setTheme: (theme) => {
        const resolved = resolveTheme(theme);
        set({ theme, resolvedTheme: resolved });

        // Appliquer au document
        if (typeof document !== 'undefined') {
          document.documentElement.classList.toggle('dark', resolved === 'dark');
          document.documentElement.classList.toggle('light', resolved === 'light');
        }
      },

      toggleTheme: () => {
        const { theme } = get();
        const newTheme = theme === 'dark' ? 'light' : 'dark';
        get().setTheme(newTheme);
      },

      // Sidebar actions
      setSidebarState: (sidebarState) => set({ sidebarState }),

      toggleSidebar: () => {
        const { sidebarState } = get();
        set({
          sidebarState: sidebarState === 'expanded' ? 'collapsed' : 'expanded',
        });
      },

      collapseSidebar: () => set({ sidebarState: 'collapsed' }),
      expandSidebar: () => set({ sidebarState: 'expanded' }),
      setSidebarPinned: (sidebarPinned) => set({ sidebarPinned }),

      // Modal actions
      openCommandPalette: () => set({ commandPaletteOpen: true }),
      closeCommandPalette: () => set({ commandPaletteOpen: false }),
      toggleCommandPalette: () => set((state) => ({ commandPaletteOpen: !state.commandPaletteOpen })),
      openSearch: () => set({ searchOpen: true }),
      closeSearch: () => set({ searchOpen: false }),
      openSettings: () => set({ settingsOpen: true }),
      closeSettings: () => set({ settingsOpen: false }),

      // Notification actions
      addNotification: (notification) => {
        const newNotification: Notification = {
          ...notification,
          id: crypto.randomUUID(),
          read: false,
          createdAt: new Date(),
        };

        set((state) => ({
          notifications: [newNotification, ...state.notifications].slice(0, 50), // Max 50
          unreadCount: state.unreadCount + 1,
        }));
      },

      markAsRead: (id) => {
        set((state) => {
          const notification = state.notifications.find((n) => n.id === id);
          if (!notification || notification.read) return state;

          return {
            notifications: state.notifications.map((n) =>
              n.id === id ? { ...n, read: true } : n
            ),
            unreadCount: Math.max(0, state.unreadCount - 1),
          };
        });
      },

      markAllAsRead: () => {
        set((state) => ({
          notifications: state.notifications.map((n) => ({ ...n, read: true })),
          unreadCount: 0,
        }));
      },

      removeNotification: (id) => {
        set((state) => {
          const notification = state.notifications.find((n) => n.id === id);
          const wasUnread = notification && !notification.read;

          return {
            notifications: state.notifications.filter((n) => n.id !== id),
            unreadCount: wasUnread ? Math.max(0, state.unreadCount - 1) : state.unreadCount,
          };
        });
      },

      clearNotifications: () => set({ notifications: [], unreadCount: 0 }),

      // Préférences
      setCompactMode: (compactMode) => set({ compactMode }),
      setAnimationsEnabled: (animationsEnabled) => set({ animationsEnabled }),
      setSoundEnabled: (soundEnabled) => set({ soundEnabled }),

      // Loading
      setGlobalLoading: (globalLoading, message) =>
        set({
          globalLoading,
          globalLoadingMessage: message || null,
        }),

      // CSRF actions
      setCsrfToken: (token) => {
        set({ csrfToken: token });
      },

      fetchCsrfToken: async () => {
        try {
          const response = await authApi.getCsrfToken();
          set({ csrfToken: response.csrf_token });

          // Rafraîchir le token avant expiration (14 min, TTL backend = 15 min)
          setTimeout(() => {
            get().fetchCsrfToken();
          }, 14 * 60 * 1000);
        } catch {
          // Erreur silencieuse, le middleware renverra 403 et forcera une nouvelle tentative
        }
      },

      clearCsrfToken: () => {
        set({ csrfToken: null });
      },
    }),
    {
      name: 'marveline-ui',
      partialize: (state) => ({
        theme: state.theme,
        sidebarState: state.sidebarState,
        sidebarPinned: state.sidebarPinned,
        compactMode: state.compactMode,
        animationsEnabled: state.animationsEnabled,
        soundEnabled: state.soundEnabled,
        csrfToken: state.csrfToken,
      }),
    }
  )
);

// ============================================
// Hooks utilitaires
// ============================================

export const useTheme = () => {
  const { theme, resolvedTheme, setTheme, toggleTheme } = useUIStore();
  return { theme, resolvedTheme, setTheme, toggleTheme };
};

export const useSidebar = () => {
  const {
    sidebarState,
    sidebarPinned,
    setSidebarState,
    toggleSidebar,
    collapseSidebar,
    expandSidebar,
    setSidebarPinned,
  } = useUIStore();

  return {
    state: sidebarState,
    isExpanded: sidebarState === 'expanded',
    isCollapsed: sidebarState === 'collapsed',
    isHidden: sidebarState === 'hidden',
    isPinned: sidebarPinned,
    setState: setSidebarState,
    toggle: toggleSidebar,
    collapse: collapseSidebar,
    expand: expandSidebar,
    setPinned: setSidebarPinned,
  };
};

export const useNotifications = () => {
  const {
    notifications,
    unreadCount,
    addNotification,
    markAsRead,
    markAllAsRead,
    removeNotification,
    clearNotifications,
  } = useUIStore();

  return {
    notifications,
    unreadCount,
    hasUnread: unreadCount > 0,
    add: addNotification,
    markAsRead,
    markAllAsRead,
    remove: removeNotification,
    clear: clearNotifications,

    // Helpers
    info: (title: string, message?: string) =>
      addNotification({ type: 'info', title, message }),
    success: (title: string, message?: string) =>
      addNotification({ type: 'success', title, message }),
    warning: (title: string, message?: string) =>
      addNotification({ type: 'warning', title, message }),
    error: (title: string, message?: string) =>
      addNotification({ type: 'error', title, message }),
  };
};

export const useGlobalLoading = () => {
  const { globalLoading, globalLoadingMessage, setGlobalLoading } = useUIStore();

  return {
    isLoading: globalLoading,
    message: globalLoadingMessage,
    show: (message?: string) => setGlobalLoading(true, message),
    hide: () => setGlobalLoading(false),
  };
};
