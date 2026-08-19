/**
 * Cartographer — Sidebar Navigation
 *
 * Dark glass sidebar with:
 * - Brand logo
 * - Primary navigation links with icons
 * - Active route highlighting
 * - Collapsible on mobile
 * - User profile at bottom
 */

import { NavLink, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard,
  GitBranch,
  Share2,
  FolderOpen,
  MessageSquare,
  Activity,
  Zap,
  FileDiff,
  FlaskConical,
  Settings,
  LogOut,
  Map,
} from 'lucide-react'
import { useAuthStore } from '@store/authStore'
import { cn } from '@utils/cn'

const navItems = [
  { to: '/dashboard',     label: 'Dashboard',           icon: LayoutDashboard },
  { to: '/repositories',  label: 'Repositories',        icon: GitBranch },
  { to: '/explorer',      label: 'Repository Explorer', icon: FolderOpen },
  { to: '/graph',         label: 'Code Graph',          icon: Share2 },
  { to: '/chat',          label: 'Chat',                icon: MessageSquare },
  { to: '/runs',          label: 'Refactor Runs',       icon: Activity },
  { to: '/blast-radius',  label: 'Blast Radius',        icon: Zap },
  { to: '/agents',        label: 'Agent Trace',         icon: Activity },
  { to: '/diff',          label: 'Diff Viewer',         icon: FileDiff },
  { to: '/tests',         label: 'Test Results',        icon: FlaskConical },
  { to: '/settings',      label: 'Settings',            icon: Settings },
]

export function Sidebar() {
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/auth')
  }

  return (
    <aside className="flex h-full w-60 flex-col border-r border-border bg-card/50 backdrop-blur-xl">
      {/* Logo */}
      <div className="flex h-16 items-center gap-3 px-5 border-b border-border">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
          <Map className="h-4 w-4 text-white" />
        </div>
        <span className="text-lg font-semibold tracking-tight">Cartographer</span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto px-3 py-4">
        <ul className="space-y-1">
          {navItems.map(({ to, label, icon: Icon }) => (
            <li key={to}>
              <NavLink
                to={to}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-all duration-200',
                    isActive
                      ? 'bg-primary/10 text-primary border border-primary/20'
                      : 'text-muted-foreground hover:bg-secondary hover:text-foreground'
                  )
                }
              >
                <Icon className="h-4 w-4 shrink-0" />
                {label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      {/* User profile */}
      <div className="border-t border-border p-3">
        <div className="flex items-center gap-3 rounded-lg px-3 py-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/20 text-xs font-semibold text-primary">
            {user?.username?.charAt(0).toUpperCase() ?? 'U'}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium truncate">{user?.username}</p>
            <p className="text-xs text-muted-foreground truncate">{user?.email}</p>
          </div>
          <button
            onClick={handleLogout}
            className="text-muted-foreground hover:text-foreground transition-colors"
            title="Log out"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </aside>
  )
}
