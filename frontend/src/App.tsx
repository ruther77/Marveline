import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'

// Layouts
import AuthLayout from '@/components/layout/AuthLayout'
import DashboardLayout from '@/components/layout/DashboardLayout'

// Auth pages
import LoginPage from '@/pages/auth/LoginPage'
import ForgotPasswordPage from '@/pages/auth/ForgotPasswordPage'
import ResetPasswordPage from '@/pages/auth/ResetPasswordPage'
import MFAVerifyPage from '@/pages/auth/MFAVerifyPage'
import OAuthCallbackPage from '@/pages/auth/OAuthCallbackPage'

// Admin pages
import UsersPage from '@/pages/admin/UsersPage'
import SessionsPage from '@/pages/admin/SessionsPage'
import AuditLogsPage from '@/pages/admin/AuditLogsPage'

// Product pages
import ProductsPage from '@/pages/products/ProductsPage'
import CategoriesPage from '@/pages/products/CategoriesPage'
import BundlesPage from '@/pages/products/BundlesPage'

// Reservation pages
import ReservationsPage from '@/pages/events/EventsPage'

// Inventory pages
import InventoryPage from '@/pages/inventory/InventoryPage'
import MovementsPage from '@/pages/inventory/MovementsPage'

// Profile pages
import ProfilePage from '@/pages/profile/ProfilePage'
import SecurityPage from '@/pages/profile/SecurityPage'
import MFASetupPage from '@/pages/profile/MFASetupPage'

// Dashboard (page d'accueil simple)
import DashboardPage from '@/pages/dashboard/DashboardPage'

// Error pages
import NotFoundPage from '@/pages/errors/NotFoundPage'

// Agenda pages
import AgendaPage from '@/pages/agenda/AgendaPage'
import AgendaMobilePage from '@/pages/agenda/AgendaMobilePage'

// Protected Route wrapper
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuthStore()

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-dark-900">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500"></div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}

// Public Route wrapper (redirect if authenticated)
function PublicRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuthStore()

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-dark-900">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500"></div>
      </div>
    )
  }

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />
  }

  return <>{children}</>
}

export default function App() {
  return (
    <Routes>
      {/* Public routes - Auth */}
      <Route element={<AuthLayout />}>
        <Route path="/login" element={<PublicRoute><LoginPage /></PublicRoute>} />
        <Route path="/register" element={<Navigate to="/login" replace />} />
        <Route path="/forgot-password" element={<PublicRoute><ForgotPasswordPage /></PublicRoute>} />
        <Route path="/reset-password" element={<PublicRoute><ResetPasswordPage /></PublicRoute>} />
        <Route path="/mfa/verify" element={<MFAVerifyPage />} />
        <Route path="/auth/callback/:provider" element={<OAuthCallbackPage />} />
      </Route>

      {/* Protected routes */}
      <Route element={<ProtectedRoute><DashboardLayout /></ProtectedRoute>}>
        {/* Dashboard */}
        <Route path="/dashboard" element={<DashboardPage />} />

        {/* Agenda / Événements */}
        <Route path="/agenda" element={<AgendaPage />} />
        <Route path="/agenda/mobile" element={<AgendaMobilePage />} />

        {/* Catalogue */}
        <Route path="/products" element={<ProductsPage />} />
        <Route path="/products/categories" element={<CategoriesPage />} />
        <Route path="/products/bundles" element={<BundlesPage />} />

        {/* Ventes / Réservations */}
        <Route path="/events" element={<ReservationsPage />} />

        {/* Inventaire */}
        <Route path="/inventory/stock" element={<InventoryPage />} />
        <Route path="/inventory/movements" element={<MovementsPage />} />

        {/* Admin */}
        <Route path="/admin/users" element={<UsersPage />} />
        <Route path="/admin/sessions" element={<SessionsPage />} />
        <Route path="/admin/audit-logs" element={<AuditLogsPage />} />

        {/* Profile & Settings */}
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/profile/security" element={<SecurityPage />} />
        <Route path="/profile/mfa" element={<MFASetupPage />} />
        <Route path="/settings" element={<ProfilePage />} />
      </Route>

      {/* Redirects */}
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}
