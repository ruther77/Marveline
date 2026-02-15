import { Construction } from 'lucide-react'

interface ComingSoonProps {
  title: string
  description?: string
}

export default function ComingSoon({ title, description }: ComingSoonProps) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-4">
      <div className="w-16 h-16 rounded-2xl bg-primary-500/10 flex items-center justify-center mb-6">
        <Construction className="w-8 h-8 text-primary-500" />
      </div>
      <h1 className="text-2xl font-bold text-white mb-2">{title}</h1>
      {description && (
        <p className="text-dark-400 mb-4 max-w-md">{description}</p>
      )}
      <p className="text-dark-500 text-sm">
        Cette fonctionnalite sera disponible prochainement.
      </p>
    </div>
  )
}
