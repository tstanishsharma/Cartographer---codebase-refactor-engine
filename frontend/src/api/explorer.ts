import { useQuery } from '@tanstack/react-query'
import { apiClient } from './client'

export interface RepositoryFile {
  path: string
  language: string
  chunk_count: number
  total_lines: number
}

export interface Chunk {
  id: string
  file_path: string
  language: string
  chunk_type: string
  chunk_index: number
  symbol_name: string | null
  symbol_type: string | null
  start_line: number
  end_line: number
  content: string
}

export function useRepositoryFiles(repoId: string | null) {
  return useQuery({
    queryKey: ['repo-files', repoId],
    queryFn: async () => {
      const response = await apiClient.get<RepositoryFile[]>(
        `/api/v1/repositories/${repoId}/files`
      )
      return response.data
    },
    enabled: !!repoId,
    staleTime: 30_000,
  })
}

export function useFileChunks(repoId: string | null, filePath: string | null) {
  return useQuery({
    queryKey: ['file-chunks', repoId, filePath],
    queryFn: async () => {
      const response = await apiClient.get<Chunk[]>(
        `/api/v1/repositories/${repoId}/chunks`,
        { params: { file_path: filePath } }
      )
      return response.data
    },
    enabled: !!repoId && !!filePath,
    staleTime: 30_000,
  })
}
