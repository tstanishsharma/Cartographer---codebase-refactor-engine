import { useMutation } from '@tanstack/react-query'
import { apiClient } from './client'

export interface BlastRadiusRequest {
  repository_id: string
  symbol_name: string
  file_path: string
  proposed_change: string
}

export interface AffectedNode {
  id: string
  node_type: string
  name: string
  qualified_name: string | null
  file_path: string
  start_line: number
  end_line: number
}

export interface BlastRadiusResult {
  affected_files: string[]
  affected_nodes: AffectedNode[]
  risk_level: string
  risk_score: number
  reasoning: string
  dependency_chain: string[]
}

export function useEstimateBlastRadius() {
  return useMutation({
    mutationFn: async (body: BlastRadiusRequest) => {
      const response = await apiClient.post<BlastRadiusResult>(
        '/api/v1/blast-radius/estimate',
        body
      )
      return response.data
    },
  })
}
