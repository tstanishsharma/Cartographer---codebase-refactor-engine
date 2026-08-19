import { motion } from 'framer-motion'
import { Card, CardContent, CardHeader, CardTitle } from '@components/ui/Card'
import { FolderGit2, MessageSquare, Zap, Cpu, ArrowRight, Activity, Server, Plus } from 'lucide-react'
import { Button } from '@components/ui/Button'
import { useNavigate } from 'react-router-dom'
import { useRepositories } from '@api/repositories'
import { formatDistanceToNow } from 'date-fns'

function compactCount(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}

const quickActions = [
  { icon: Plus, label: 'Add Repository', path: '/repositories' },
  { icon: MessageSquare, label: 'New Chat Session', path: '/chat' },
  { icon: FolderGit2, label: 'Explore Code', path: '/explorer' },
  { icon: Zap, label: 'Estimate Blast Radius', path: '/blast-radius' },
]

export default function Dashboard() {
  const navigate = useNavigate()
  const { data: repositories } = useRepositories()

  const pendingCount =
    repositories?.filter((r) => ['pending', 'cloning', 'parsing', 'embedding'].includes(r.status))
      .length ?? 0
  const totalNodes = repositories?.reduce((sum, r) => sum + (r.total_nodes ?? 0), 0) ?? 0

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-muted-foreground mt-1">Overview of your repositories and AI agent activity.</p>
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {quickActions.map((action, i) => (
          <motion.div
            key={action.label}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.05 }}
          >
            <button
              onClick={() => navigate(action.path)}
              className="flex w-full items-center gap-3 rounded-xl border border-border bg-card p-4 text-left transition-colors hover:bg-secondary/80 focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-background"
            >
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <action.icon className="h-5 w-5" />
              </div>
              <span className="font-medium text-sm">{action.label}</span>
            </button>
          </motion.div>
        ))}
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        
        {/* Left Column (Stats & Repos) */}
        <div className="md:col-span-2 space-y-6">
          <div className="grid grid-cols-2 gap-4">
            <Card className="glass-card">
              <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
                <CardTitle className="text-sm font-medium text-muted-foreground">Repositories</CardTitle>
                <FolderGit2 className="h-4 w-4 text-primary" />
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold">{repositories?.length ?? 0}</div>
                <p className="text-xs text-muted-foreground mt-1">{pendingCount} pending ingestion</p>
              </CardContent>
            </Card>
            <Card className="glass-card">
              <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
                <CardTitle className="text-sm font-medium text-muted-foreground">Knowledge Graph</CardTitle>
                <Cpu className="h-4 w-4 text-accent" />
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold">{compactCount(totalNodes)}</div>
                <p className="text-xs text-muted-foreground mt-1">AST nodes parsed</p>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>Recent Repositories</CardTitle>
              <Button variant="ghost" size="sm" onClick={() => navigate('/repositories')} className="text-xs">
                View All <ArrowRight className="ml-1 h-3 w-3" />
              </Button>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {repositories?.slice(0, 4).map((repo) => (
                  <div key={repo.id} className="flex items-center justify-between border-b pb-4 last:border-0 last:pb-0">
                    <div className="flex items-center gap-3">
                      <div className="flex h-9 w-9 items-center justify-center rounded-md border bg-secondary/50">
                        <FolderGit2 className="h-4 w-4 text-muted-foreground" />
                      </div>
                      <div>
                        <p className="text-sm font-medium">{repo.name}</p>
                        <p className="text-xs text-muted-foreground">
                          {repo.ingested_at
                            ? `Ingested ${formatDistanceToNow(new Date(repo.ingested_at), { addSuffix: true })}`
                            : repo.status}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <span
                        className={`inline-flex h-2 w-2 rounded-full ${
                          repo.status === 'ready' ? 'bg-green-500' : 'bg-amber-500'
                        }`}
                      />
                      <span className="text-xs text-muted-foreground">{repo.status}</span>
                    </div>
                  </div>
                ))}
                {!repositories?.length && (
                  <p className="py-6 text-center text-sm text-muted-foreground">
                    No repositories yet. Add your first one to get started.
                  </p>
                )}
              </div>
            </CardContent>
          </Card>
          
          {/* Refactor Runs Placeholder */}
          <Card>
            <CardHeader>
              <CardTitle>Recent Refactor Runs</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-col items-center justify-center py-6 text-center">
                <Zap className="h-8 w-8 text-muted-foreground/30 mb-3" />
                <p className="text-sm text-muted-foreground">No recent refactors.</p>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Right Column (Agents & System) */}
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Activity className="h-4 w-4 text-primary animate-pulse" />
                Live Processing Jobs
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-medium text-foreground">Cloning 'django/django'</span>
                    <span className="text-muted-foreground">45%</span>
                  </div>
                  <div className="h-1.5 w-full overflow-hidden rounded-full bg-secondary">
                    <div className="h-full bg-primary" style={{ width: '45%' }} />
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Server className="h-4 w-4" />
                System Health
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex justify-between items-center text-sm">
                <span className="text-muted-foreground">Database</span>
                <span className="text-green-400 font-medium">Connected</span>
              </div>
              <div className="flex justify-between items-center text-sm">
                <span className="text-muted-foreground">Vector Store</span>
                <span className="text-green-400 font-medium">Healthy</span>
              </div>
              <div className="flex justify-between items-center text-sm">
                <span className="text-muted-foreground">LLM Provider</span>
                <span className="text-green-400 font-medium">Operational</span>
              </div>
              <div className="flex justify-between items-center text-sm">
                <span className="text-muted-foreground">Docker Sandbox</span>
                <span className="text-yellow-400 font-medium">Idle</span>
              </div>
            </CardContent>
          </Card>
          
          <Card>
            <CardHeader>
              <CardTitle>Recent Chats</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {[1, 2].map((i) => (
                  <div key={i} className="rounded-lg border bg-secondary/20 p-3 hover:bg-secondary/40 cursor-pointer transition-colors">
                    <p className="text-sm font-medium text-foreground line-clamp-1">Explain the hybrid retrieval logic</p>
                    <p className="text-xs text-muted-foreground mt-1">Today at 2:30 PM</p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
