/**
 * Cartographer — Auth Page (Login + Register)
 *
 * Beautiful dark-themed auth page with JWT login.
 * GitHub OAuth tab shown when GITHUB_OAUTH_ENABLED=true.
 */

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { Map, Eye, EyeOff, Loader2 } from 'lucide-react'
import { apiClient } from '@api/client'
import axios from 'axios'
import { useAuthStore } from '@store/authStore'
import type { TokenResponse, User } from '../types'
import { cn } from '@utils/cn'

type Tab = 'login' | 'register'

export default function Auth() {
  const [tab, setTab] = useState<Tab>('login')
  const [showPassword, setShowPassword] = useState(false)
  const [form, setForm] = useState({ email: '', username: '', password: '', full_name: '' })
  const [error, setError] = useState('')

  const { setTokens, setUser } = useAuthStore()
  const navigate = useNavigate()

  const loginMutation = useMutation({
    mutationFn: async () => {
      const res = await apiClient.post<TokenResponse>('/api/v1/auth/login', {
        email: form.email,
        password: form.password,
      })
      return res.data
    },
    onSuccess: async (tokens) => {
      setTokens(tokens.access_token, tokens.refresh_token)
      const meRes = await apiClient.get<User>('/api/v1/auth/me', {
        headers: { Authorization: `Bearer ${tokens.access_token}` },
      })
      setUser(meRes.data)
      navigate('/dashboard')
    },
    onError: (err: unknown) => {
      if (axios.isAxiosError(err)) {
        setError(err.response?.data?.detail ?? 'Login failed')
      } else {
        setError('Login failed')
      }
    },
  })

  const registerMutation = useMutation({
    mutationFn: async () => {
      const res = await apiClient.post<User>('/api/v1/auth/register', {
        email: form.email,
        username: form.username,
        password: form.password,
        full_name: form.full_name || undefined,
      })
      return res.data
    },
    onSuccess: () => {
      setTab('login')
      setError('')
    },
    onError: (err: unknown) => {
      if (axios.isAxiosError(err)) {
        setError(err.response?.data?.detail ?? 'Registration failed')
      } else {
        setError('Registration failed')
      }
    },
  })

  const isLoading = loginMutation.isPending || registerMutation.isPending

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    if (tab === 'login') loginMutation.mutate()
    else registerMutation.mutate()
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      {/* Background gradient */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -top-40 left-1/2 -translate-x-1/2 h-[600px] w-[600px] rounded-full bg-primary/5 blur-3xl" />
        <div className="absolute -bottom-40 right-1/4 h-[400px] w-[400px] rounded-full bg-accent/5 blur-3xl" />
      </div>

      <div className="relative w-full max-w-md">
        {/* Logo */}
        <div className="mb-8 flex flex-col items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary shadow-lg shadow-primary/25">
            <Map className="h-6 w-6 text-white" />
          </div>
          <div className="text-center">
            <h1 className="text-2xl font-bold tracking-tight">Cartographer</h1>
            <p className="text-sm text-muted-foreground">Autonomous code understanding</p>
          </div>
        </div>

        {/* Card */}
        <div className="glass-card rounded-2xl p-8">
          {/* Tabs */}
          <div className="mb-6 flex rounded-lg bg-secondary p-1">
            {(['login', 'register'] as Tab[]).map((t) => (
              <button
                key={t}
                onClick={() => { setTab(t); setError('') }}
                className={cn(
                  'flex-1 rounded-md py-2 text-sm font-medium transition-all duration-200',
                  tab === t
                    ? 'bg-card text-foreground shadow-sm'
                    : 'text-muted-foreground hover:text-foreground'
                )}
              >
                {t === 'login' ? 'Sign In' : 'Create Account'}
              </button>
            ))}
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {tab === 'register' && (
              <div>
                <label className="text-sm font-medium text-foreground">Username</label>
                <input
                  type="text"
                  value={form.username}
                  onChange={(e) => setForm({ ...form, username: e.target.value })}
                  required
                  className="mt-1 w-full rounded-lg border border-border bg-secondary px-3 py-2 text-sm outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-colors"
                  placeholder="your_username"
                />
              </div>
            )}

            <div>
              <label className="text-sm font-medium text-foreground">Email</label>
              <input
                type="email"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                required
                className="mt-1 w-full rounded-lg border border-border bg-secondary px-3 py-2 text-sm outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-colors"
                placeholder="you@example.com"
              />
            </div>

            <div>
              <label className="text-sm font-medium text-foreground">Password</label>
              <div className="relative mt-1">
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={form.password}
                  onChange={(e) => setForm({ ...form, password: e.target.value })}
                  required
                  className="w-full rounded-lg border border-border bg-secondary px-3 py-2 pr-10 text-sm outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-colors"
                  placeholder="••••••••"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            {error && (
              <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={isLoading}
              className="w-full rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-primary/25 transition-all hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoading ? (
                <span className="flex items-center justify-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  {tab === 'login' ? 'Signing in...' : 'Creating account...'}
                </span>
              ) : (
                tab === 'login' ? 'Sign In' : 'Create Account'
              )}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
