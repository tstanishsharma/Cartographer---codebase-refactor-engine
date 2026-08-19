import { Activity } from 'lucide-react'
import { EmptyState } from '@components/ui/EmptyState'

export default function RefactorRuns() {
  return (
    <div className="p-8 max-w-6xl mx-auto h-full flex flex-col">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight">Refactor Runs</h1>
        <p className="text-muted-foreground mt-1">Monitor autonomous refactoring sessions and apply generated pull requests.</p>
      </div>

      <div className="flex-1 flex items-center justify-center">
        <EmptyState
          icon={<Activity className="h-10 w-10 text-primary" />}
          title="No refactoring runs"
          description="Ask Cartographer to perform a large-scale refactor to see its progress and results here."
        />
      </div>
    </div>
  )
}
