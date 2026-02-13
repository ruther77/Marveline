import { useAuthStore } from '@/stores/authStore'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { PageHeader } from '@/components/ui/Breadcrumb'
import { User, Shield, Settings } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

export default function DashboardPage() {
  const { user } = useAuthStore()
  const navigate = useNavigate()

  return (
    <div className="space-y-6">
      <PageHeader
        title={`Bienvenue, ${user?.full_name || user?.email || 'Utilisateur'}`}
        subtitle="Tableau de bord Marveline"
      />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card hover className="cursor-pointer" onClick={() => navigate('/profile')}>
          <CardHeader>
            <CardTitle>
              <User className="w-5 h-5 inline mr-2 text-primary-500" />
              Mon Profil
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-dark-400">
              Modifier vos informations personnelles
            </p>
          </CardContent>
        </Card>

        <Card hover className="cursor-pointer" onClick={() => navigate('/profile/security')}>
          <CardHeader>
            <CardTitle>
              <Shield className="w-5 h-5 inline mr-2 text-green-500" />
              Securite
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-dark-400">
              Gerer vos sessions et MFA
            </p>
          </CardContent>
        </Card>

        <Card hover className="cursor-pointer" onClick={() => navigate('/settings')}>
          <CardHeader>
            <CardTitle>
              <Settings className="w-5 h-5 inline mr-2 text-blue-500" />
              Parametres
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-dark-400">
              Configurer votre compte
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
