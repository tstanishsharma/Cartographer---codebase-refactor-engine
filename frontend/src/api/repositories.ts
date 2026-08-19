import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from './client'

export interface RepositoryResponse {
  id: string
  name: string
  url: string
  description: string | null
  status: string
  total_files: number
  total_chunks: number
  total_nodes: number
  total_edges: number
  languages: Record<string, number>
  created_at: string
  ingested_at: string | null
}

export interface CreateRepositoryRequest {
  url: string
  name: string
  description?: string
  default_branch?: string
}

export const useRepositories = () => {
  return useQuery({
    queryKey: ['repositories'],
    queryFn: async () => {
      const response = await apiClient.get<RepositoryResponse[]>('/api/v1/repositories/')
      return response.data
    },
    refetchInterval: (query) => {
      // Poll if any repo is pending/cloning
      const data = query.state.data
      if (data?.some((r) => ['pending', 'cloning'].includes(r.status))) {
        return 2000 // poll every 2s
      }
      return false
    }
  })
}

export const useAddRepository = () => {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async (data: CreateRepositoryRequest) => {
      const response = await apiClient.post<RepositoryResponse>('/api/v1/repositories/', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['repositories'] })
    }
  })
}

export const useDeleteRepository = () => {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async (id: string) => {
      await apiClient.delete(`/api/v1/repositories/${id}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['repositories'] })
    }
  })
}
