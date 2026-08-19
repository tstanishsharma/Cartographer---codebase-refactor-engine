import { useState, useCallback, useEffect, useMemo } from 'react'
import ReactFlow, {
  MiniMap,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  Connection,
  Edge,
  Node,
  MarkerType,
} from 'reactflow'
import 'reactflow/dist/style.css'
import { Search, Share2, Loader2 } from 'lucide-react'

import { Input } from '@components/ui/Input'
import { apiClient } from '@api/client'
import { useRepositories } from '@api/repositories'
import { useRepositoryGraph, GraphNode } from '@api/graph'

// Node fill colors by AST node type.
const NODE_COLORS: Record<string, string> = {
  module: '#3b82f6',
  class: '#22c55e',
  function: '#f59e0b',
  method: '#a855f7',
  import: '#64748b',
  variable: '#06b6d4',
  decorator: '#ef4444',
}

interface FlowNodeData {
  label: string
}

function toReactFlowNode(node: GraphNode, layer: number, layerIndex: number): Node<FlowNodeData> {
  return {
    id: node.id,
    position: { x: 60 + layer * 260, y: 60 + layerIndex * 84 },
    data: { label: node.name },
    className: 'rounded-lg border-2 border-border text-xs',
    style: { borderColor: NODE_COLORS[node.node_type] ?? '#94a3b8' },
  }
}

export default function RepositoryGraph() {
  const { data: repositories } = useRepositories()
  const [selectedRepo, setSelectedRepo] = useState<string | null>(null)
  const { data: graphData, isLoading } = useRepositoryGraph(selectedRepo)

  const [nodes, setNodes, onNodesChange] = useNodesState<FlowNodeData>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])
  const [search, setSearch] = useState('')

  // Lay out the fetched graph into nodes/edges.
  useEffect(() => {
    if (!graphData) return

    const { nodes: gNodes, edges: gEdges } = graphData

    // BFS layering from roots (nodes with no incoming edges).
    const incoming = new Map<string, number>()
    const adjacency = new Map<string, string[]>()
    gNodes.forEach((n) => incoming.set(n.id, 0))
    gEdges.forEach((e) => {
      incoming.set(e.target_id, (incoming.get(e.target_id) ?? 0) + 1)
      adjacency.set(e.source_id, [...(adjacency.get(e.source_id) ?? []), e.target_id])
    })

    const layers = new Map<string, number>()
    const queue: string[] = gNodes.filter((n) => (incoming.get(n.id) ?? 0) === 0).map((n) => n.id)
    let visited = 0
    for (const id of queue) {
      layers.set(id, 0)
      visited++
    }
    while (queue.length) {
      const current = queue.shift()!
      const next = adjacency.get(current) ?? []
      for (const target of next) {
        const nextLayer = (layers.get(current) ?? 0) + 1
        if (!layers.has(target) || (layers.get(target) ?? 0) < nextLayer) {
          layers.set(target, nextLayer)
        }
        queue.push(target)
      }
    }
    // Nodes unreachable from roots (cycles) get the last layer.
    gNodes.forEach((n) => {
      if (!layers.has(n.id)) layers.set(n.id, (layers.get(n.id) ?? 0) + 1)
    })

    const byLayer = new Map<number, GraphNode[]>()
    gNodes.forEach((n) => {
      const layer = layers.get(n.id) ?? 0
      byLayer.set(layer, [...(byLayer.get(layer) ?? []), n])
    })
    const layerIndex = new Map<string, number>()
    for (const [layer, layerNodes] of byLayer) {
      layerNodes.forEach((n, i) => layerIndex.set(n.id, i))
    }

    setNodes(gNodes.map((n) => toReactFlowNode(n, layers.get(n.id) ?? 0, layerIndex.get(n.id) ?? 0)))
    setEdges(
      gEdges.map((e) => ({
        id: e.id,
        source: e.source_id,
        target: e.target_id,
        animated: true,
        markerEnd: { type: MarkerType.ArrowClosed },
      }))
    )
  }, [graphData, setNodes, setEdges])

  // Expand neighbors when a node is clicked.
  const onNodeClick = useCallback(
    async (_: React.MouseEvent, node: Node) => {
      if (!selectedRepo) return
      const response = await apiClient.get<GraphNode[]>(
        `/api/v1/graph/repositories/${selectedRepo}/nodes/${node.id}/neighbors`
      )
      const neighborsData = response.data
      setNodes((nds) => {
        const existing = new Set(nds.map((n) => n.id))
        const next = [...nds]
        neighborsData.forEach((n) => {
          if (!existing.has(n.id)) {
            next.push({
              id: n.id,
              position: { x: node.position.x + 240, y: node.position.y + next.length * 8 },
              data: { label: n.name },
              className: 'rounded-lg border-2 border-border text-xs',
              style: { borderColor: NODE_COLORS[n.node_type] ?? '#94a3b8' },
            })
          }
        })
        return next
      })
      setEdges((eds) => {
        const next = [...eds]
        const seen = new Set(eds.map((e) => `${e.source}-${e.target}`))
        neighborsData.forEach((n) => {
          const key = `${node.id}-${n.id}`
          if (!seen.has(key)) {
            seen.add(key)
            next.push({
              id: `exp-${key}`,
              source: node.id,
              target: n.id,
              animated: true,
              markerEnd: { type: MarkerType.ArrowClosed },
            })
          }
        })
        return next
      })
    },
    [selectedRepo, setNodes, setEdges]
  )

  const onConnect = useCallback(
    (params: Connection) =>
      setEdges((eds) => {
        if (!params.source || !params.target) return eds
        const newEdge: Edge = {
          id: `c-${params.source}-${params.target}`,
          source: params.source,
          target: params.target,
          sourceHandle: params.sourceHandle,
          targetHandle: params.targetHandle,
        }
        return [...eds, newEdge]
      }),
    [setEdges]
  )

  const filteredNodes = useMemo(() => {
    if (!search.trim()) return nodes
    const q = search.toLowerCase()
    return nodes.filter((n) => String(n.data.label).toLowerCase().includes(q))
  }, [nodes, search])

  return (
    <div className="flex h-full flex-col bg-background">
      {/* Toolbar */}
      <div className="flex items-center gap-3 border-b border-border bg-card/50 px-4 py-3">
        <h1 className="font-semibold text-sm">Repository Graph</h1>
        <select
          value={selectedRepo ?? ''}
          onChange={(e) => setSelectedRepo(e.target.value || null)}
          className="h-8 rounded-md border border-border bg-secondary/50 px-2 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
        >
          <option value="">Select a repository…</option>
          {repositories?.map((r) => (
            <option key={r.id} value={r.id}>
              {r.name}
            </option>
          ))}
        </select>
        <div className="relative ml-auto w-56">
          <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Filter nodes..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-8 h-8 text-xs bg-secondary/50 border-border"
          />
        </div>
        <Share2 className="h-4 w-4 text-muted-foreground" />
      </div>

      {/* Graph canvas */}
      <div className="flex-1">
        {isLoading && selectedRepo ? (
          <div className="flex h-full items-center justify-center">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        ) : !selectedRepo ? (
          <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
            Select a repository to visualize its knowledge graph.
          </div>
        ) : (
          <ReactFlow
            nodes={filteredNodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={onNodeClick}
            fitView
            fitViewOptions={{ padding: 0.3, maxZoom: 1 }}
            proOptions={{ hideAttribution: true }}
          >
            <MiniMap
              nodeColor={(n) => (n.style?.borderColor as string) ?? '#94a3b8'}
              maskColor="rgba(0,0,0,0.6)"
            />
            <Controls />
            <Background gap={18} size={1} />
          </ReactFlow>
        )}
      </div>
    </div>
  )
}

