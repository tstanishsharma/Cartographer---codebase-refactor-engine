import { useState, useMemo } from 'react'
import Editor from '@monaco-editor/react'
import { FolderGit2, FileCode2, Search, ChevronDown, ChevronRight, Loader2 } from 'lucide-react'
import { Input } from '@components/ui/Input'
import { EmptyState } from '@components/ui/EmptyState'
import { useRepositories } from '@api/repositories'
import { useRepositoryFiles, useFileChunks, RepositoryFile } from '@api/explorer'

interface TreeNode {
  name: string
  path: string
  type: 'file' | 'folder'
  language?: string
  children: TreeNode[]
}

function buildTree(files: RepositoryFile[]): TreeNode[] {
  const roots: TreeNode[] = []
  const byPath = new Map<string, TreeNode>()
  files.forEach((f) => {
    const parts = f.path.split('/')
    let current: TreeNode[] = roots
    let acc = ''
    parts.forEach((part, i) => {
      acc = acc ? `${acc}/${part}` : part
      let node = byPath.get(acc)
      if (!node) {
        node = {
          name: part,
          path: acc,
          type: i === parts.length - 1 ? 'file' : 'folder',
          language: i === parts.length - 1 ? f.language : undefined,
          children: [],
        }
        byPath.set(acc, node)
        current.push(node)
      }
      current = node.children
    })
  })
  return roots
}

function toMonacoLanguage(language: string | undefined): string {
  switch (language) {
    case 'python': return 'python'
    case 'typescript': return 'typescript'
    case 'javascript': return 'javascript'
    case 'json': return 'json'
    case 'markdown': return 'markdown'
    case 'go': return 'go'
    case 'java': return 'java'
    case 'rust': return 'rust'
    case 'html': return 'html'
    case 'css': return 'css'
    case 'sql': return 'sql'
    case 'yaml': return 'yaml'
    default: return 'plaintext'
  }
}

export default function RepositoryExplorer() {
  const { data: repositories } = useRepositories()
  const [selectedRepo, setSelectedRepo] = useState<string | null>(null)
  const { data: files, isLoading } = useRepositoryFiles(selectedRepo)
  const [selectedFile, setSelectedFile] = useState<RepositoryFile | null>(null)
  const { data: chunks, isLoading: chunksLoading } = useFileChunks(
    selectedRepo,
    selectedFile?.path ?? null
  )
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set())
  const [search, setSearch] = useState('')

  const tree = useMemo(() => (files ? buildTree(files) : []), [files])

  const fileContent = useMemo(() => {
    if (!chunks) return ''
    return chunks.map((c) => c.content).join('\n')
  }, [chunks])

  const toggle = (path: string) =>
    setCollapsed((prev) => {
      const next = new Set(prev)
      if (next.has(path)) next.delete(path)
      else next.add(path)
      return next
    })

  const renderTree = (nodes: TreeNode[], depth: number): React.ReactNode => {
    return nodes.map((node) => {
      const isCollapsed = collapsed.has(node.path)
      const matches = node.name.toLowerCase().includes(search.toLowerCase())
      if (node.type === 'folder') {
        return (
          <div key={node.path}>
            <button
              onClick={() => toggle(node.path)}
              className="flex w-full items-center gap-1.5 rounded px-2 py-1 text-left text-xs text-muted-foreground hover:bg-secondary/60"
              style={{ paddingLeft: 8 + depth * 14 }}
            >
              {isCollapsed ? <ChevronRight className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
              <FolderGit2 className="h-3.5 w-3.5 text-amber-500" />
              <span className="truncate">{node.name}</span>
            </button>
            {!isCollapsed && renderTree(node.children, depth + 1)}
          </div>
        )
      }
      if (search && !matches) return null
      return (
        <button
          key={node.path}
          onClick={() => {
            const f = files?.find((x) => x.path === node.path)
            if (f) setSelectedFile(f)
          }}
          className={`flex w-full items-center gap-1.5 rounded px-2 py-1 text-left text-xs hover:bg-secondary/60 ${
            selectedFile?.path === node.path ? 'bg-primary/10 text-primary' : 'text-foreground/80'
          }`}
          style={{ paddingLeft: 24 + depth * 14 }}
        >
          <FileCode2 className="h-3.5 w-3.5 shrink-0 text-sky-500" />
          <span className="truncate">{node.name}</span>
        </button>
      )
    })
  }

  return (
    <div className="flex h-full bg-background overflow-hidden">
      {/* Sidebar */}
      <div className="w-80 border-r border-border bg-card/50 flex flex-col">
        <div className="p-3 border-b border-border space-y-2">
          <h2 className="font-semibold text-sm">Explorer</h2>
          <select
            value={selectedRepo ?? ''}
            onChange={(e) => {
              setSelectedRepo(e.target.value || null)
              setSelectedFile(null)
            }}
            className="w-full h-8 rounded-md border border-border bg-secondary/50 px-2 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
          >
            <option value="">Select a repository…</option>
            {repositories?.map((r) => (
              <option key={r.id} value={r.id}>
                {r.name}
              </option>
            ))}
          </select>
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search files..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-8 h-8 text-xs bg-secondary/50 border-border"
            />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-2 text-sm">
          {isLoading ? (
            <div className="flex justify-center py-10">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : !selectedRepo ? (
            <p className="px-2 py-4 text-xs text-muted-foreground">
              Select a repository to browse its ingested files.
            </p>
          ) : tree.length === 0 ? (
            <p className="px-2 py-4 text-xs text-muted-foreground">
              No files ingested yet. Re-ingest the repository.
            </p>
          ) : (
            renderTree(tree, 0)
          )}
        </div>
      </div>

      {/* Code view */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {!selectedFile ? (
          <div className="flex flex-1 items-center justify-center">
            <EmptyState
              icon={<FileCode2 className="h-10 w-10 text-sky-500" />}
              title="Select a file"
              description="Choose a file from the explorer to view its ingested chunks."
            />
          </div>
        ) : chunksLoading ? (
          <div className="flex flex-1 items-center justify-center">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <>
            <div className="flex items-center gap-2 border-b border-border bg-card/50 px-4 py-2">
              <FileCode2 className="h-4 w-4 text-sky-500" />
              <span className="text-xs font-medium text-foreground">{selectedFile.path}</span>
              <span className="ml-auto text-[10px] uppercase tracking-wide text-muted-foreground">
                {selectedFile.language} · {chunks?.length ?? 0} chunks · {selectedFile.total_lines} lines
              </span>
            </div>
            <Editor
              height="100%"
              language={toMonacoLanguage(selectedFile.language)}
              theme="vs-dark"
              value={fileContent}
              options={{ readOnly: true, fontSize: 13, minimap: { enabled: false }, lineNumbers: 'on' }}
            />
          </>
        )}
      </div>
    </div>
  )
}
