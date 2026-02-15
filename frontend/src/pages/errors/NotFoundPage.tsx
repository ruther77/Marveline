import { useNavigate } from 'react-router-dom'
import { Home, ArrowLeft } from 'lucide-react'

export default function NotFoundPage() {
  const navigate = useNavigate()

  return (
    <div className="min-h-screen flex items-center justify-center bg-dark-900 p-6">
      <div className="max-w-md w-full text-center">
        <div className="mb-6">
          <span className="text-7xl font-bold bg-gradient-to-br from-primary-400 to-primary-600 bg-clip-text text-transparent">
            404
          </span>
        </div>
        <h1 className="text-xl font-bold text-white mb-2">Page introuvable</h1>
        <p className="text-dark-400 mb-8">
          La page que vous recherchez n'existe pas ou a ete deplacee.
        </p>
        <div className="flex items-center justify-center gap-3">
          <button
            onClick={() => navigate(-1)}
            className="flex items-center gap-2 px-4 py-2.5 bg-dark-700 hover:bg-dark-600 text-dark-200 text-sm font-medium rounded-xl transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Retour
          </button>
          <button
            onClick={() => navigate('/dashboard')}
            className="flex items-center gap-2 px-5 py-2.5 bg-primary-600 hover:bg-primary-500 text-white text-sm font-medium rounded-xl transition-colors"
          >
            <Home className="w-4 h-4" />
            Accueil
          </button>
        </div>
      </div>
    </div>
  )
}
