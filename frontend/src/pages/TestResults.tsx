import { FlaskConical } from 'lucide-react'
import { EmptyState } from '@components/ui/EmptyState'

export default function TestResults() {
  return (
    <div className="p-8 max-w-6xl mx-auto h-full flex flex-col">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight">Test Results</h1>
        <p className="text-muted-foreground mt-1">Review the outcomes of Cartographer's isolated sandbox test executions.</p>
      </div>

      <div className="flex-1 flex items-center justify-center">
        <EmptyState
          icon={<FlaskConical className="h-10 w-10 text-cyan-500" />}
          title="No tests executed yet"
          description="When Cartographer proposes a code edit, it runs tests in an isolated sandbox. Results will appear here."
        />
      </div>
    </div>
  )
}
