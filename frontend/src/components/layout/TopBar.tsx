import { Map, Bell, Search, Sun, Moon } from 'lucide-react'
import { useState, useEffect } from 'react'

export function TopBar() {
  const [isDark, setIsDark] = useState(true)

  // A simple theme toggle for the UI
  const toggleTheme = () => {
    setIsDark(!isDark)
    if (isDark) {
      document.documentElement.classList.remove('dark')
    } else {
      document.documentElement.classList.add('dark')
    }
  }

  // Ensure initial theme is dark
  useEffect(() => {
    document.documentElement.classList.add('dark')
  }, [])

  return (
    <header className="flex h-16 items-center justify-between border-b border-border bg-card/50 px-6 backdrop-blur-xl">
      <div className="flex items-center gap-4">
        {/* Repo selector placeholder */}
        <div className="flex items-center gap-2 rounded-lg border border-border bg-secondary/50 px-3 py-1.5 text-sm">
          <Map className="h-4 w-4 text-muted-foreground" />
          <span className="font-medium text-foreground">Cartographer / cartographer</span>
          <span className="text-xs text-muted-foreground">v1.0</span>
        </div>
      </div>

      <div className="flex items-center gap-4">
        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search files, symbols, chats..."
            className="w-64 rounded-full border border-border bg-secondary/30 py-1.5 pl-9 pr-4 text-sm text-foreground outline-none transition-all focus:w-80 focus:border-primary focus:ring-1 focus:ring-primary"
          />
        </div>

        {/* Notifications */}
        <button className="relative flex h-8 w-8 items-center justify-center rounded-full hover:bg-secondary transition-colors">
          <Bell className="h-4 w-4 text-muted-foreground" />
          <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-primary" />
        </button>

        {/* Theme Toggle */}
        <button
          onClick={toggleTheme}
          className="flex h-8 w-8 items-center justify-center rounded-full hover:bg-secondary transition-colors"
        >
          {isDark ? <Sun className="h-4 w-4 text-muted-foreground" /> : <Moon className="h-4 w-4 text-muted-foreground" />}
        </button>

        {/* User Profile */}
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-primary to-accent text-xs font-semibold text-white shadow-sm ring-2 ring-background">
          R
        </div>
      </div>
    </header>
  )
}
