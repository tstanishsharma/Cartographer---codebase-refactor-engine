import { useQuery } from '@tanstack/react-query'
import { apiClient } from './client'

export interface GraphNode {
  id: string
  node_type: string
  name: string
  qualified_name: string | null
  file_path: string
  start_line: number
  end_line: number
  metadata: Record<string, unknown>
}

export interface GraphEdge {
  id: string
  source_id: string
  target_id: string
  edge_type: string
  weight: number
}

export interface RepositoryGraph {
  nodes: GraphNode[]
  edges: GraphEdge[]
  total_nodes: number
  total_edges: number
}

export function useRepositoryGraph(repoId: string | null) {
  return useQuery({
    queryKey: ['graph', repoId],
    queryFn: async () => {
      const response = await apiClient.get<RepositoryGraph>(
        `/api/v1/graph/repositories/${repoId}`
      )
      return response.data
    },
    enabled: !!repoId,
    staleTime: 30_000,
  })
}

export function useNodeNeighbors(repoId: string | null, nodeId: string | null) {
  return useQuery({
    queryKey: ['graph-neighbors', repoId, nodeId],
    queryFn: async () => {
      const response = await apiClient.get<GraphNode[]>(
        `/api/v1/graph/repositories/${repoId}/nodes/${nodeId}/neighbors`
      )
      return response.data
    },
    enabled: !!repoId && !!nodeId,
    staleTime: 30_000,
  })
}
