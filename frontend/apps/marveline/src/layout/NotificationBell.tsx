import { Bell } from 'lucide-react'
import { Link } from '@tanstack/react-router'
import { useNotifications } from '@/api/queries/useNotifications'

export default function NotificationBell() {
  const { data } = useNotifications()
  const count = data?.unread_count ?? 0

  return (
    <Link
      to="/notifications"
      className="relative flex items-center justify-center w-9 h-9 rounded-xl text-dark-400 hover:text-dark-50 hover:bg-dark-600/50 transition-colors"
      title="Notifications"
    >
      <Bell className="w-5 h-5" />
      {count > 0 && (
        <span className="absolute top-1 right-1 w-4 h-4 rounded-full bg-red-500 text-white text-[10px] font-bold flex items-center justify-center leading-none">
          {count > 9 ? '9+' : count}
        </span>
      )}
    </Link>
  )
}
