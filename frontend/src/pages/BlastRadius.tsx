import { useState } from 'react'
import { Zap, Loader2, FileCode2, AlertTriangle } from 'lucide-react'
import { EmptyState } from '@components/ui/EmptyState'
import { Button } from '@components/ui/Button'
import { Input } from '@components/ui/Input'
import { Badge } from '@components/ui/Badge'
import { useRepositories } from '@api/repositories'
import { useEstimateBlastRadius } from '@api/blastRadius'

const RISK_COLORS: Record<string, string> = {
  LOW: 'bg-green-500/15 text-green-500 border-green-500/30',
  MEDIUM: 'bg-amber-500/15 text-amber-500 border-amber-500/30',
  HIGH: 'bg-red-500/15 text-red-500 border-red-500/30',
}

export default function BlastRadius() {
  const { data: repositories } = useRepositories()
  const estimate = useEstimateBlastRadius()
  const [repositoryId, setRepositoryId] = useState('')
  const [symbolName, setSymbolName] = useState('')
  const [filePath, setFilePath] = useState('')
  const [proposedChange, setProposedChange] = useState('')

  const canSubmit = repositoryId && symbolName && !estimate.isPending

  const submit = () => {
    if (!canSubmit) return
    estimate.mutate({
      repository_id: repositoryId,
      symbol_name: symbolName,
      file_path: filePath || 'src/main.py',
      proposed_change: proposedChange || 'Refactor this symbol',
    })
  }

  const result = estimate.data

  return (
    <div className="p-8 max-w-6xl mx-auto h-full flex flex-col">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight">Blast Radius</h1>
        <p className="text-muted-foreground mt-1">Estimate the impact of a proposed code change across the dependency graph.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Estimator form */}
        <div className="rounded-xl border border-border bg-card p-5 space-y-4">
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground">Repository</label>
            <select
              value={repositoryId}
              onChange={(e) => setRepositoryId(e.target.value)}
              className="w-full h-9 rounded-md border border-border bg-secondary/50 px-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
            >
              <option value="">Select a repository…</option>
              {repositories?.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.name}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground">Symbol name</label>
            <Input
              placeholder="e.g. Command"
              value={symbolName}
              onChange={(e) => setSymbolName(e.target.value)}
              className="h-9"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground">File path</label>
            <Input
              placeholder="e.g. src/click/core.py"
              value={filePath}
              onChange={(e) => setFilePath(e.target.value)}
              className="h-9"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground">Proposed change</label>
            <textarea
              value={proposedChange}
              onChange={(e) => setProposedChange(e.target.value)}
              rows={3}
              placeholder="Describe the refactor or signature change…"
              className="w-full rounded-md border border-border bg-secondary/50 px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </div>

          <Button onClick={submit} disabled={!canSubmit} className="w-full">
            {estimate.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Zap className="mr-2 h-4 w-4" />
            )}
            Estimate Blast Radius
          </Button>

          {estimate.isError && (
            <p className="text-xs text-red-500">
              {(estimate.error as Error)?.message ?? 'Estimation failed.'}
            </p>
          )}
        </div>

        {/* Results */}
        <div className="rounded-xl border border-border bg-card p-5 overflow-y-auto max-h-[70vh]">
          {!result ? (
            <EmptyState
              icon={<Zap className="h-10 w-10 text-orange-500" />}
              title="No changes analyzed"
              description="Enter a symbol and file to estimate how far its impact ripples through the codebase."
            />
          ) : (
            <div className="space-y-5">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="font-semibold">{result.risk_level} Risk</h2>
                  <p className="text-xs text-muted-foreground">Score {result.risk_score.toFixed(3)} / 1.0</p>
                </div>
                <Badge className={RISK_COLORS[result.risk_level] ?? ''}>{result.risk_level}</Badge>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-lg bg-secondary/40 p-3">
                  <p className="text-lg font-bold">{result.affected_files.length}</p>
                  <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Files affected</p>
                </div>
                <div className="rounded-lg bg-secondary/40 p-3">
                  <p className="text-lg font-bold">{result.affected_nodes.length}</p>
                  <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Nodes affected</p>
                </div>
              </div>

              <p className="text-xs text-muted-foreground leading-relaxed">{result.reasoning}</p>

              <div>
                <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Affected files
                </h3>
                {result.affected_files.length === 0 ? (
                  <p className="text-xs text-muted-foreground">None — the change is isolated.</p>
                ) : (
                  <ul className="space-y-1 max-h-40 overflow-y-auto">
                    {result.affected_files.map((f) => (
                      <li key={f} className="flex items-center gap-2 text-xs text-foreground/80">
                        <FileCode2 className="h-3.5 w-3.5 text-sky-500" />
                        <span className="truncate">{f}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <div>
                <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Dependency chain
                </h3>
                <ol className="space-y-1">
                  {result.dependency_chain.map((c, i) => (
                    <li key={`${c}-${i}`} className="flex items-center gap-1.5 text-xs text-foreground/70">
                      <AlertTriangle className="h-3 w-3 text-amber-500" />
                      <span className="truncate">{c}</span>
                    </li>
                  ))}
                </ol>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
