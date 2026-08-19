import { useState } from 'react'
import { motion } from 'framer-motion'
import { Plus, FolderGit2, Loader2, Trash2 } from 'lucide-react'
import { useRepositories, useAddRepository, useDeleteRepository } from '@api/repositories'
import { Button } from '@components/ui/Button'
import { Input } from '@components/ui/Input'
import { Badge } from '@components/ui/Badge'
import { EmptyState } from '@components/ui/EmptyState'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@components/ui/Table'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '@components/ui/Dialog'
import { formatDistanceToNow } from 'date-fns'

export default function Repositories() {
  const { data: repositories, isLoading } = useRepositories()
  const deleteRepo = useDeleteRepository()
  const [isAddOpen, setIsAddOpen] = useState(false)

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Repositories</h1>
          <p className="text-muted-foreground mt-1">Manage your ingested codebases for Cartographer.</p>
        </div>
        <Button onClick={() => setIsAddOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Add Repository
        </Button>
      </div>

      {isLoading ? (
        <div className="flex justify-center p-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : repositories?.length === 0 ? (
        <EmptyState
          icon={<FolderGit2 className="h-10 w-10" />}
          title="No repositories yet"
          description="Import your first GitHub repository to begin building the code knowledge graph and unlocking AI reasoning."
          action={
            <Button onClick={() => setIsAddOpen(true)}>
              <Plus className="mr-2 h-4 w-4" />
              Add Repository
            </Button>
          }
        />
      ) : (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-xl border bg-card"
        >
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Repository</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Files</TableHead>
                <TableHead>Graph Nodes</TableHead>
                <TableHead>Added</TableHead>
                <TableHead className="w-[80px]"></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {repositories?.map((repo) => (
                <TableRow key={repo.id}>
                  <TableCell>
                    <div className="font-medium text-foreground">{repo.name}</div>
                    <div className="text-xs text-muted-foreground">{repo.url}</div>
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={repo.status} />
                  </TableCell>
                  <TableCell className="text-muted-foreground">{repo.total_files.toLocaleString()}</TableCell>
                  <TableCell className="text-muted-foreground">{repo.total_nodes.toLocaleString()}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {formatDistanceToNow(new Date(repo.created_at), { addSuffix: true })}
                  </TableCell>
                  <TableCell>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => deleteRepo.mutate(repo.id)}
                      className="text-muted-foreground hover:text-destructive"
                      disabled={deleteRepo.isPending}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </motion.div>
      )}

      <AddRepositoryDialog open={isAddOpen} onOpenChange={setIsAddOpen} />
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  if (status === 'ready') return <Badge variant="success">Ready</Badge>
  if (status === 'failed') return <Badge variant="destructive">Failed</Badge>
  return (
    <Badge variant="secondary" className="animate-pulse">
      <Loader2 className="mr-1 h-3 w-3 animate-spin inline" />
      {status === 'cloning' ? 'Cloning...' : 'Processing...'}
    </Badge>
  )
}

function AddRepositoryDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const addRepo = useAddRepository()
  const [url, setUrl] = useState('')
  const [name, setName] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!url || !name) return
    await addRepo.mutateAsync({ url, name })
    onOpenChange(false)
    setUrl('')
    setName('')
  }

  // Auto-fill name from URL
  const handleUrlChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newUrl = e.target.value
    setUrl(newUrl)
    if (!name && newUrl.includes('github.com')) {
      const parts = newUrl.split('/')
      if (parts.length >= 2) {
        setName(parts[parts.length - 1].replace('.git', ''))
      }
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add Repository</DialogTitle>
          <DialogDescription>
            Enter a public Git repository URL. Cartographer will clone and analyze it.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4 pt-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">Git URL</label>
            <Input
              placeholder="https://github.com/user/repo"
              value={url}
              onChange={handleUrlChange}
              required
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Repository Name</label>
            <Input
              placeholder="repo"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </div>
          <DialogFooter className="pt-4">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={addRepo.isPending}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={addRepo.isPending}>
              {addRepo.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Start Ingestion
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
