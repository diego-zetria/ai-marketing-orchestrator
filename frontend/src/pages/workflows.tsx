import { useState, useMemo, useCallback, useEffect } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import {
  Plus,
  Save,
  Trash2,
  Star,
  ArrowRight,
  Info,
} from "lucide-react"
import { toast } from "sonner"
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  addEdge,
  Handle,
  Position,
  type Node,
  type Edge,
  type Connection,
  type NodeProps,
  BackgroundVariant,
} from "@xyflow/react"
import dagre from "dagre"
import "@xyflow/react/dist/style.css"

import { api } from "@/lib/api"
import { usePermission } from "@/lib/auth"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { Separator } from "@/components/ui/separator"
import { Card, CardContent } from "@/components/ui/card"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Textarea } from "@/components/ui/textarea"

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Workflow {
  id: string
  name: string
  display_name: string
  description: string | null
  statuses: string[]
  transitions: Record<string, string[]>
  transition_actions: Record<string, unknown>
  is_default: boolean
  is_active: boolean
}

interface CreateWorkflowPayload {
  name: string
  display_name: string
  description?: string
  statuses: string[]
  transitions: Record<string, string[]>
  is_default?: boolean
}

interface UpdateWorkflowPayload {
  name?: string
  display_name?: string
  description?: string
  statuses?: string[]
  transitions?: Record<string, string[]>
}

type StatusNodeData = {
  label: string
  isFirst: boolean
  isLast: boolean
}

// ---------------------------------------------------------------------------
// Dagre auto-layout
// ---------------------------------------------------------------------------

const NODE_WIDTH = 180
const NODE_HEIGHT = 48

function getLayoutedElements(
  nodes: Node<StatusNodeData>[],
  edges: Edge[]
): { nodes: Node<StatusNodeData>[]; edges: Edge[] } {
  const g = new dagre.graphlib.Graph()
  g.setDefaultEdgeLabel(() => ({}))
  g.setGraph({ rankdir: "TB", nodesep: 60, ranksep: 80 })

  for (const node of nodes) {
    g.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT })
  }

  for (const edge of edges) {
    g.setEdge(edge.source, edge.target)
  }

  dagre.layout(g)

  const layoutedNodes = nodes.map((node) => {
    const nodeWithPosition = g.node(node.id)
    return {
      ...node,
      position: {
        x: nodeWithPosition.x - NODE_WIDTH / 2,
        y: nodeWithPosition.y - NODE_HEIGHT / 2,
      },
    }
  })

  return { nodes: layoutedNodes, edges }
}

// ---------------------------------------------------------------------------
// Custom Node
// ---------------------------------------------------------------------------

function StatusNode({ data, selected }: NodeProps<Node<StatusNodeData>>) {
  return (
    <div
      className={`
        flex items-center justify-center rounded-lg border-2 bg-background px-4 py-2
        text-sm font-medium shadow-sm transition-colors
        ${selected ? "border-primary ring-2 ring-primary/20" : "border-border"}
        ${data.isFirst ? "border-green-500 bg-green-50 dark:bg-green-950/20" : ""}
        ${data.isLast ? "border-orange-500 bg-orange-50 dark:bg-orange-950/20" : ""}
      `}
      style={{ width: NODE_WIDTH, height: NODE_HEIGHT }}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="!h-2 !w-2 !border-2 !border-muted-foreground !bg-background"
      />
      <span className="truncate">{data.label}</span>
      <Handle
        type="source"
        position={Position.Bottom}
        className="!h-2 !w-2 !border-2 !border-muted-foreground !bg-background"
      />
    </div>
  )
}

const nodeTypes = { statusNode: StatusNode }

// ---------------------------------------------------------------------------
// Build nodes and edges from workflow
// ---------------------------------------------------------------------------

function buildNodesAndEdges(workflow: Workflow) {
  const rawNodes: Node<StatusNodeData>[] = workflow.statuses.map(
    (status, index) => ({
      id: status,
      type: "statusNode",
      position: { x: 0, y: 0 },
      data: {
        label: status,
        isFirst: index === 0,
        isLast: index === workflow.statuses.length - 1,
      },
    })
  )

  const rawEdges: Edge[] = []
  for (const [source, targets] of Object.entries(workflow.transitions)) {
    for (const target of targets) {
      rawEdges.push({
        id: `${source}->${target}`,
        source,
        target,
        type: "smoothstep",
        animated: false,
        style: { strokeWidth: 2 },
        markerEnd: { type: "arrowclosed" as const, width: 16, height: 16 },
      })
    }
  }

  return getLayoutedElements(rawNodes, rawEdges)
}

// ---------------------------------------------------------------------------
// Loading Skeleton
// ---------------------------------------------------------------------------

function WorkflowsLoadingSkeleton() {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Skeleton className="h-9 w-64" />
        <Skeleton className="h-9 w-32" />
        <Skeleton className="h-9 w-40" />
      </div>
      <Skeleton className="h-[500px] w-full rounded-lg" />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Add Status Dialog
// ---------------------------------------------------------------------------

interface AddStatusDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onAdd: (name: string) => void
  existingStatuses: string[]
}

function AddStatusDialog({
  open,
  onOpenChange,
  onAdd,
  existingStatuses,
}: AddStatusDialogProps) {
  const [name, setName] = useState("")
  const normalized = name.trim().toLowerCase().replace(/\s+/g, "_")
  const isDuplicate = existingStatuses.includes(normalized)

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!normalized || isDuplicate) return
    onAdd(normalized)
    setName("")
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Adicionar Status</DialogTitle>
          <DialogDescription>
            Informe o nome do novo status. Espaços serão convertidos em
            underscores.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit}>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label htmlFor="status-name">Nome do Status</Label>
              <Input
                id="status-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="ex: em_revisao"
                autoFocus
              />
              {normalized && (
                <p className="text-xs text-muted-foreground">
                  Slug: <code className="rounded bg-muted px-1">{normalized}</code>
                </p>
              )}
              {isDuplicate && (
                <p className="text-xs text-destructive">
                  Esse status já existe neste fluxo.
                </p>
              )}
            </div>
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Cancelar
            </Button>
            <Button type="submit" disabled={!normalized || isDuplicate}>
              Adicionar
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// ---------------------------------------------------------------------------
// Create Workflow Dialog
// ---------------------------------------------------------------------------

interface CreateWorkflowDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreate: (payload: CreateWorkflowPayload) => void
  isCreating: boolean
}

function CreateWorkflowDialog({
  open,
  onOpenChange,
  onCreate,
  isCreating,
}: CreateWorkflowDialogProps) {
  const [name, setName] = useState("")
  const [displayName, setDisplayName] = useState("")
  const [description, setDescription] = useState("")
  const [statusesText, setStatusesText] = useState("")

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const slug = name.trim().toLowerCase().replace(/\s+/g, "_")
    if (!slug || !displayName.trim()) return

    const statuses = statusesText
      .split(",")
      .map((s) => s.trim().toLowerCase().replace(/\s+/g, "_"))
      .filter(Boolean)

    // Build sequential transitions from the status order
    const transitions: Record<string, string[]> = {}
    for (let i = 0; i < statuses.length - 1; i++) {
      transitions[statuses[i]] = [statuses[i + 1]]
    }

    onCreate({
      name: slug,
      display_name: displayName.trim(),
      description: description.trim() || undefined,
      statuses,
      transitions,
    })
  }

  function handleClose() {
    setName("")
    setDisplayName("")
    setDescription("")
    setStatusesText("")
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Novo Fluxo de Trabalho</DialogTitle>
          <DialogDescription>
            Crie um novo fluxo definindo nome, descrição e os status iniciais.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit}>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label htmlFor="wf-name">Nome (slug)</Label>
              <Input
                id="wf-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="ex: fluxo_padrão"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="wf-display-name">Nome de Exibição</Label>
              <Input
                id="wf-display-name"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="ex: Fluxo Padrão"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="wf-description">Descrição</Label>
              <Textarea
                id="wf-description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Descrição opcional do fluxo..."
                rows={2}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="wf-statuses">Status (separados por vírgula)</Label>
              <Input
                id="wf-statuses"
                value={statusesText}
                onChange={(e) => setStatusesText(e.target.value)}
                placeholder="ex: ativar, planejamento, desenvolvimento, aprovado"
              />
              <p className="text-xs text-muted-foreground">
                As transições iniciais serão criadas na ordem informada.
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={handleClose}>
              Cancelar
            </Button>
            <Button
              type="submit"
              disabled={!name.trim() || !displayName.trim() || isCreating}
            >
              {isCreating ? "Criando..." : "Criar Fluxo"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// ---------------------------------------------------------------------------
// Workflows Page
// ---------------------------------------------------------------------------

export function WorkflowsPage() {
  const queryClient = useQueryClient()

  // ---- RBAC ----
  const canCreate = usePermission("workflows", "create")
  const canUpdate = usePermission("workflows", "update")
  const canDelete = usePermission("workflows", "delete")

  // ---- Local state ----
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string | null>(null)
  const [addStatusOpen, setAddStatusOpen] = useState(false)
  const [createDialogOpen, setCreateDialogOpen] = useState(false)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)

  // Local editable copies
  const [localStatuses, setLocalStatuses] = useState<string[]>([])
  const [localTransitions, setLocalTransitions] = useState<Record<string, string[]>>({})

  // React Flow state
  const [nodes, setNodes, onNodesChange] = useNodesState<Node<StatusNodeData>>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null)

  // ---- Queries ----
  const {
    data: workflows,
    isLoading: workflowsLoading,
    error: workflowsError,
  } = useQuery({
    queryKey: ["workflows"],
    queryFn: () => api.get<Workflow[]>("/workflows"),
  })

  const selectedWorkflow = useMemo(
    () => workflows?.find((w) => w.id === selectedWorkflowId) ?? null,
    [workflows, selectedWorkflowId]
  )

  // Auto-select first workflow when data loads
  useEffect(() => {
    if (workflows && workflows.length > 0 && !selectedWorkflowId) {
      setSelectedWorkflowId(workflows[0].id)
    }
  }, [workflows, selectedWorkflowId])

  // Sync local state when selected workflow changes
  useEffect(() => {
    if (selectedWorkflow) {
      setLocalStatuses([...selectedWorkflow.statuses])
      setLocalTransitions(
        JSON.parse(JSON.stringify(selectedWorkflow.transitions))
      )
      const { nodes: layoutedNodes, edges: layoutedEdges } =
        buildNodesAndEdges(selectedWorkflow)
      setNodes(layoutedNodes)
      setEdges(layoutedEdges)
      setSelectedNodeId(null)
      setSelectedEdgeId(null)
    } else {
      setLocalStatuses([])
      setLocalTransitions({})
      setNodes([])
      setEdges([])
    }
  }, [selectedWorkflow, setNodes, setEdges])

  // ---- isDirty ----
  const isDirty = useMemo(() => {
    if (!selectedWorkflow) return false
    const statusesChanged =
      JSON.stringify(localStatuses) !==
      JSON.stringify(selectedWorkflow.statuses)
    const transitionsChanged =
      JSON.stringify(localTransitions) !==
      JSON.stringify(selectedWorkflow.transitions)
    return statusesChanged || transitionsChanged
  }, [localStatuses, localTransitions, selectedWorkflow])

  // ---- Rebuild graph from local state ----
  const rebuildGraph = useCallback(
    (statuses: string[], transitions: Record<string, string[]>) => {
      const tempWorkflow: Workflow = {
        id: "",
        name: "",
        display_name: "",
        description: null,
        statuses,
        transitions,
        transition_actions: {},
        is_default: false,
        is_active: true,
      }
      const { nodes: layoutedNodes, edges: layoutedEdges } =
        buildNodesAndEdges(tempWorkflow)
      setNodes(layoutedNodes)
      setEdges(layoutedEdges)
    },
    [setNodes, setEdges]
  )

  // ---- Mutations ----
  const updateMutation = useMutation({
    mutationFn: (payload: UpdateWorkflowPayload) =>
      api.put<Workflow>(`/workflows/${selectedWorkflowId}`, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["workflows"] })
      toast.success("Fluxo salvo com sucesso.")
    },
    onError: (err: Error) => {
      toast.error(`Erro ao salvar fluxo: ${err.message}`)
    },
  })

  const createMutation = useMutation({
    mutationFn: (payload: CreateWorkflowPayload) =>
      api.post<Workflow>("/workflows", payload),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["workflows"] })
      setSelectedWorkflowId(data.id)
      setCreateDialogOpen(false)
      toast.success("Fluxo criado com sucesso.")
    },
    onError: (err: Error) => {
      toast.error(`Erro ao criar fluxo: ${err.message}`)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => api.delete<void>(`/workflows/${selectedWorkflowId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["workflows"] })
      setSelectedWorkflowId(null)
      setDeleteDialogOpen(false)
      toast.success("Fluxo excluído com sucesso.")
    },
    onError: (err: Error) => {
      toast.error(`Erro ao excluir fluxo: ${err.message}`)
    },
  })

  const setDefaultMutation = useMutation({
    mutationFn: () =>
      api.put<Workflow>(`/workflows/${selectedWorkflowId}/set-default`, {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["workflows"] })
      toast.success("Fluxo definido como padrão.")
    },
    onError: (err: Error) => {
      toast.error(`Erro ao definir fluxo padrão: ${err.message}`)
    },
  })

  // ---- Handlers ----
  function handleSave() {
    if (!selectedWorkflowId) return
    updateMutation.mutate({
      statuses: localStatuses,
      transitions: localTransitions,
    })
  }

  function handleAddStatus(name: string) {
    const newStatuses = [...localStatuses, name]
    const newTransitions = { ...localTransitions }
    setLocalStatuses(newStatuses)
    setLocalTransitions(newTransitions)
    rebuildGraph(newStatuses, newTransitions)
  }

  function handleRemoveStatus(statusId: string) {
    const newStatuses = localStatuses.filter((s) => s !== statusId)
    const newTransitions: Record<string, string[]> = {}
    for (const [source, targets] of Object.entries(localTransitions)) {
      if (source === statusId) continue
      const filteredTargets = targets.filter((t) => t !== statusId)
      if (filteredTargets.length > 0) {
        newTransitions[source] = filteredTargets
      }
    }
    setLocalStatuses(newStatuses)
    setLocalTransitions(newTransitions)
    setSelectedNodeId(null)
    rebuildGraph(newStatuses, newTransitions)
  }

  function handleRemoveEdge(edgeId: string) {
    const parts = edgeId.split("->")
    if (parts.length !== 2) return
    const [source, target] = parts
    const newTransitions = { ...localTransitions }
    if (newTransitions[source]) {
      newTransitions[source] = newTransitions[source].filter(
        (t) => t !== target
      )
      if (newTransitions[source].length === 0) {
        delete newTransitions[source]
      }
    }
    setLocalTransitions(newTransitions)
    setSelectedEdgeId(null)
    rebuildGraph(localStatuses, newTransitions)
  }

  const onConnect = useCallback(
    (connection: Connection) => {
      if (!canUpdate) return
      if (!connection.source || !connection.target) return
      if (connection.source === connection.target) return

      const existing = localTransitions[connection.source] ?? []
      if (existing.includes(connection.target)) return

      const newTransitions = {
        ...localTransitions,
        [connection.source]: [...existing, connection.target],
      }
      setLocalTransitions(newTransitions)

      const newEdge: Edge = {
        id: `${connection.source}->${connection.target}`,
        source: connection.source,
        target: connection.target,
        type: "smoothstep",
        style: { strokeWidth: 2 },
        markerEnd: { type: "arrowclosed" as const, width: 16, height: 16 },
      }
      setEdges((eds) => addEdge(newEdge, eds))
    },
    [canUpdate, localTransitions, setEdges]
  )

  function handleNodeClick(_: React.MouseEvent, node: Node) {
    setSelectedNodeId(node.id)
    setSelectedEdgeId(null)
  }

  function handleEdgeClick(_: React.MouseEvent, edge: Edge) {
    setSelectedEdgeId(edge.id)
    setSelectedNodeId(null)
  }

  function handlePaneClick() {
    setSelectedNodeId(null)
    setSelectedEdgeId(null)
  }

  // ---- Selected edge info ----
  const selectedEdgeInfo = useMemo(() => {
    if (!selectedEdgeId) return null
    const parts = selectedEdgeId.split("->")
    if (parts.length !== 2) return null
    return { source: parts[0], target: parts[1] }
  }, [selectedEdgeId])

  // ---- Render ----
  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">
          Fluxos de Trabalho
        </h1>
        <p className="mt-1 text-muted-foreground">
          Visualize e edite os fluxos de status das tarefas.
        </p>
      </div>

      {/* Error state */}
      {workflowsError && (
        <div
          role="alert"
          className="rounded-lg border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm text-destructive"
        >
          {workflowsError instanceof Error
            ? workflowsError.message
            : "Erro ao carregar fluxos de trabalho."}
        </div>
      )}

      {/* Loading */}
      {workflowsLoading && <WorkflowsLoadingSkeleton />}

      {/* Empty state */}
      {!workflowsLoading &&
        !workflowsError &&
        workflows &&
        workflows.length === 0 && (
          <div className="flex flex-col items-center justify-center gap-4 py-16">
            <p className="text-center text-muted-foreground">
              Nenhum fluxo de trabalho encontrado.
            </p>
            {canCreate && (
              <Button onClick={() => setCreateDialogOpen(true)}>
                <Plus className="size-4" aria-hidden="true" />
                Novo Fluxo
              </Button>
            )}
          </div>
        )}

      {/* Main content */}
      {!workflowsLoading && workflows && workflows.length > 0 && (
        <>
          {/* Toolbar */}
          <div className="flex flex-wrap items-center gap-3">
            <div className="w-72">
              <Select
                value={selectedWorkflowId ?? undefined}
                onValueChange={setSelectedWorkflowId}
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Selecionar fluxo..." />
                </SelectTrigger>
                <SelectContent>
                  {workflows.map((wf) => (
                    <SelectItem key={wf.id} value={wf.id}>
                      <span className="flex items-center gap-2">
                        {wf.display_name}
                        {wf.is_default && (
                          <Badge variant="secondary" className="text-xs">
                            Padrão
                          </Badge>
                        )}
                      </span>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {canCreate && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCreateDialogOpen(true)}
              >
                <Plus className="size-4" aria-hidden="true" />
                Novo Fluxo
              </Button>
            )}

            {selectedWorkflow && !selectedWorkflow.is_default && canUpdate && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setDefaultMutation.mutate()}
                disabled={setDefaultMutation.isPending}
              >
                <Star className="size-4" aria-hidden="true" />
                {setDefaultMutation.isPending
                  ? "Definindo..."
                  : "Definir como Padrão"}
              </Button>
            )}

            {selectedWorkflow && canDelete && (
              <Button
                variant="outline"
                size="sm"
                className="text-destructive hover:bg-destructive/10"
                onClick={() => setDeleteDialogOpen(true)}
              >
                <Trash2 className="size-4" aria-hidden="true" />
                Excluir
              </Button>
            )}

            <div className="flex-1" />

            {isDirty && (
              <Badge variant="outline" className="text-amber-600 border-amber-300">
                Alterações não salvas
              </Badge>
            )}

            {canUpdate && (
              <Button
                size="sm"
                onClick={handleSave}
                disabled={!isDirty || updateMutation.isPending}
              >
                <Save className="size-4" aria-hidden="true" />
                {updateMutation.isPending ? "Salvando..." : "Salvar"}
              </Button>
            )}
          </div>

          {/* Workflow info */}
          {selectedWorkflow && (
            <div className="flex items-center gap-4 text-sm text-muted-foreground">
              <span>
                <strong>Slug:</strong>{" "}
                <code className="rounded bg-muted px-1.5 py-0.5 text-xs">
                  {selectedWorkflow.name}
                </code>
              </span>
              {selectedWorkflow.description && (
                <>
                  <Separator orientation="vertical" className="h-4" />
                  <span>{selectedWorkflow.description}</span>
                </>
              )}
              <Separator orientation="vertical" className="h-4" />
              <span>
                {selectedWorkflow.statuses.length} status,{" "}
                {Object.values(selectedWorkflow.transitions).reduce(
                  (acc, t) => acc + t.length,
                  0
                )}{" "}
                transições
              </span>
            </div>
          )}

          {/* React Flow canvas */}
          {selectedWorkflow && (
            <Card className="overflow-hidden">
              <CardContent className="p-0">
                <div className="h-[500px] w-full">
                  <ReactFlow
                    nodes={nodes}
                    edges={edges}
                    onNodesChange={onNodesChange}
                    onEdgesChange={onEdgesChange}
                    onConnect={onConnect}
                    onNodeClick={handleNodeClick}
                    onEdgeClick={handleEdgeClick}
                    onPaneClick={handlePaneClick}
                    nodeTypes={nodeTypes}
                    fitView
                    fitViewOptions={{ padding: 0.3 }}
                    proOptions={{ hideAttribution: true }}
                    defaultEdgeOptions={{
                      type: "smoothstep",
                      style: { strokeWidth: 2 },
                    }}
                  >
                    <Background
                      variant={BackgroundVariant.Dots}
                      gap={16}
                      size={1}
                      className="!bg-muted/30"
                    />
                    <Controls
                      showInteractive={false}
                      className="!rounded-lg !border !shadow-sm"
                    />
                    <MiniMap
                      nodeStrokeWidth={3}
                      className="!rounded-lg !border !shadow-sm"
                      maskColor="rgba(0,0,0,0.08)"
                    />
                  </ReactFlow>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Selection panel */}
          {selectedWorkflow && (
            <div className="flex flex-wrap items-start gap-4">
              {/* Node selected */}
              {selectedNodeId && (
                <Card className="w-full max-w-sm">
                  <CardContent className="space-y-3 pt-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                          Status selecionado
                        </p>
                        <p className="text-lg font-semibold">{selectedNodeId}</p>
                      </div>
                      <Badge
                        variant={
                          localStatuses.indexOf(selectedNodeId) === 0
                            ? "default"
                            : localStatuses.indexOf(selectedNodeId) ===
                                localStatuses.length - 1
                              ? "secondary"
                              : "outline"
                        }
                      >
                        {localStatuses.indexOf(selectedNodeId) === 0
                          ? "Início"
                          : localStatuses.indexOf(selectedNodeId) ===
                              localStatuses.length - 1
                            ? "Fim"
                            : `Posição ${localStatuses.indexOf(selectedNodeId) + 1}`}
                      </Badge>
                    </div>

                    {/* Outgoing transitions */}
                    {localTransitions[selectedNodeId] &&
                      localTransitions[selectedNodeId].length > 0 && (
                        <div className="space-y-1">
                          <p className="text-xs text-muted-foreground">
                            Transições de saída:
                          </p>
                          <div className="flex flex-wrap gap-1.5">
                            {localTransitions[selectedNodeId].map((t) => (
                              <Badge key={t} variant="outline" className="gap-1">
                                <ArrowRight className="size-3" aria-hidden="true" />
                                {t}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      )}

                    <Separator />

                    {canUpdate && (
                      <Button
                        variant="destructive"
                        size="sm"
                        onClick={() => handleRemoveStatus(selectedNodeId)}
                        className="w-full"
                      >
                        <Trash2 className="size-3" aria-hidden="true" />
                        Remover Status
                      </Button>
                    )}
                  </CardContent>
                </Card>
              )}

              {/* Edge selected */}
              {selectedEdgeId && selectedEdgeInfo && (
                <Card className="w-full max-w-sm">
                  <CardContent className="space-y-3 pt-4">
                    <div>
                      <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                        Transição selecionada
                      </p>
                      <div className="mt-1 flex items-center gap-2 text-sm font-medium">
                        <Badge variant="outline">{selectedEdgeInfo.source}</Badge>
                        <ArrowRight className="size-4 text-muted-foreground" aria-hidden="true" />
                        <Badge variant="outline">{selectedEdgeInfo.target}</Badge>
                      </div>
                    </div>

                    <Separator />

                    {canUpdate && (
                      <Button
                        variant="destructive"
                        size="sm"
                        onClick={() => handleRemoveEdge(selectedEdgeId)}
                        className="w-full"
                      >
                        <Trash2 className="size-3" aria-hidden="true" />
                        Remover Transição
                      </Button>
                    )}
                  </CardContent>
                </Card>
              )}

              {/* No selection - show hint */}
              {!selectedNodeId && !selectedEdgeId && (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Info className="size-4" aria-hidden="true" />
                  <span>
                    Clique em um status ou transição para editar. Conecte dois
                    status arrastando de um ponto de conexão para outro.
                  </span>
                </div>
              )}

              <div className="flex-1" />

              {canUpdate && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setAddStatusOpen(true)}
                >
                  <Plus className="size-4" aria-hidden="true" />
                  Adicionar Status
                </Button>
              )}
            </div>
          )}
        </>
      )}

      {/* Dialogs */}
      <AddStatusDialog
        open={addStatusOpen}
        onOpenChange={setAddStatusOpen}
        onAdd={handleAddStatus}
        existingStatuses={localStatuses}
      />

      <CreateWorkflowDialog
        open={createDialogOpen}
        onOpenChange={setCreateDialogOpen}
        onCreate={(payload) => createMutation.mutate(payload)}
        isCreating={createMutation.isPending}
      />

      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Excluir Fluxo</AlertDialogTitle>
            <AlertDialogDescription>
              Tem certeza que deseja excluir o fluxo{" "}
              <strong>{selectedWorkflow?.display_name}</strong>? Esta ação não pode
              ser desfeita.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => deleteMutation.mutate()}
            >
              {deleteMutation.isPending ? "Excluindo..." : "Excluir"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
