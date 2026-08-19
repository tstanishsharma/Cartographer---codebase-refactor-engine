import { FileDiff } from 'lucide-react'
import { EmptyState } from '@components/ui/EmptyState'

export default function DiffViewer() {
  return (
    <div className="p-8 max-w-6xl mx-auto h-full flex flex-col">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight">Diff Viewer</h1>
        <p className="text-muted-foreground mt-1">Review AI-proposed code edits before they are applied to your repository.</p>
      </div>

      <div className="flex-1 flex items-center justify-center">
        <EmptyState
          icon={<FileDiff className="h-10 w-10 text-emerald-500" />}
          title="No diffs available"
          description="Ask Cartographer to perform a refactor in the Chat, and review the resulting Git diff here."
        />
      </div>
    </div>
  )
}
