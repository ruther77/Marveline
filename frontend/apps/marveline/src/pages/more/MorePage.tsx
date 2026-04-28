import { useEffect } from 'react'
import { useNavigate } from '@tanstack/react-router'

/**
 * MorePage — page de transition legacy (non montée par la route /_app/more).
 * La route more.tsx gère la redirection 301 → /plus via beforeLoad.
 * Ce composant est conservé pour cohérence mais redirige aussi vers /plus.
 */
export default function MorePage() {
  const navigate = useNavigate()

  useEffect(() => {
    navigate({ to: '/plus', replace: true })
  }, [navigate])

  return null
}
