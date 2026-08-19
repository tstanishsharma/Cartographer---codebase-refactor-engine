import { Activity } from 'lucide-react'
import { EmptyState } from '@components/ui/EmptyState'

export default function AgentTrace() {
  return (
    <div className="p-8 max-w-6xl mx-auto h-full flex flex-col">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight">Agent Trace</h1>
        <p className="text-muted-foreground mt-1">View the step-by-step reasoning and tool usage of the multi-agent system.</p>
      </div>

      <div className="flex-1 flex items-center justify-center">
        <EmptyState
          icon={<Activity className="h-10 w-10 text-primary" />}
          title="No active agent runs"
          description="Agent traces will appear here when Cartographer is executing complex tasks or proposing refactors."
        />
      </div>
    </div>
  )
}
