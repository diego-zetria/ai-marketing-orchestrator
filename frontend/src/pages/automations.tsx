import { useState, useMemo, useCallback } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import {
  Plus,
  X,
  Pencil,
  Trash2,
  FlaskConical,
  CheckCircle2,
  XCircle,
  ChevronDown,
  ChevronUp,
} from "lucide-react"
import { toast } from "sonner"
import { api } from "@/lib/api"
import { usePermission } from "@/lib/auth"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface AutomationRule {
  id: string
  name: string
  display_name: string
  intent_type: string
  patterns: string[]
  allowed_roles: string[]
  valid_from_statuses: string[]
  target_status: string
  mode: string
  special_action: string | null
  priority: number
  is_active: boolean
}

interface AutomationCreate {
  name: string
  display_name: string
  intent_type: string
  patterns: string[]
  allowed_roles: string[]
  valid_from_statuses: string[]
  target_status: string
  mode: string
  special_action?: string | null
  priority: number
}

interface AutomationUpdate {
  display_name?: string
  intent_type?: string
  patterns?: string[]
  allowed_roles?: string[]
  valid_from_statuses?: string[]
  target_status?: string
  mode?: string
  special_action?: string | null
  priority?: number
  is_active?: boolean
}

interface PatternTestRequest {
  text: string
  user_role?: string
  current_status?: string
}

interface PatternTestResponse {
  matched: boolean
  intent_type?: string
  matched_pattern?: string
  target_status?: string
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const AVAILABLE_ROLES = [
  { value: "account", label: "Atendimento" },
  { value: "admin", label: "Admin" },
  { value: "designer", label: "Designer" },
  { value: "strategy_reviewer", label: "Revisor de Estratégia" },
  { value: "content_reviewer", label: "Revisor de Conteúdo" },
]

const ROLE_LABELS: Record<string, string> = Object.fromEntries(
  AVAILABLE_ROLES.map((r) => [r.value, r.label])
)

const AVAILABLE_STATUSES = [
  "ativar",
  "planejamento",
  "desenvolvimento",
  "em criacao",
  "revisao",
  "alteracao",
  "aprovado",
  "pronto",
]

const MODE_OPTIONS = [
  { value: "confirm", label: "Confirmação" },
  { value: "auto", label: "Automático" },
]

// ---------------------------------------------------------------------------
// Multi-Value Editor (type + Enter, badges with remove)
// ---------------------------------------------------------------------------

interface MultiValueEditorProps {
  values: string[]
  onChange: (values: string[]) => void
  placeholder: string
  validate?: (value: string) => string | null
  showRoleLabels?: boolean
}

function MultiValueEditor({
  values,
  onChange,
  placeholder,
  validate,
  showRoleLabels,
}: MultiValueEditorProps) {
  const [inputValue, setInputValue] = useState("")
  const [validationError, setValidationError] = useState<string | null>(null)

  function handleAdd(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      e.preventDefault()
      const trimmed = inputValue.trim()
      if (!trimmed) return
      if (values.includes(trimmed)) {
        setValidationError("Valor já adicionado")
        return
      }
      if (validate) {
        const error = validate(trimmed)
        if (error) {
          setValidationError(error)
          return
        }
      }
      onChange([...values, trimmed])
      setInputValue("")
      setValidationError(null)
    }
  }

  function handleRemove(value: string) {
    onChange(values.filter((v) => v !== value))
  }

  function handleInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    setInputValue(e.target.value)
    if (validationError) setValidationError(null)
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-1.5">
        {values.map((value) => (
          <Badge key={value} variant="outline" className="gap-1">
            <span className="max-w-48 truncate font-mono text-xs">
              {showRoleLabels ? (ROLE_LABELS[value] ?? value) : value}
            </span>
            <button
              type="button"
              onClick={() => handleRemove(value)}
              className="ml-0.5 rounded-full outline-none hover:bg-accent focus-visible:ring-1 focus-visible:ring-ring"
              aria-label={`Remover ${value}`}
            >
              <X className="size-3" aria-hidden="true" />
            </button>
          </Badge>
        ))}
      </div>
      <Input
        value={inputValue}
        onChange={handleInputChange}
        onKeyDown={handleAdd}
        placeholder={placeholder}
        className="h-8 text-sm"
        aria-invalid={!!validationError}
      />
      {validationError && (
        <p className="text-xs text-destructive" role="alert">
          {validationError}
        </p>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Regex Validator
// ---------------------------------------------------------------------------

function validateRegex(pattern: string): string | null {
  try {
    new RegExp(pattern)
    return null
  } catch {
    return "Regex inválido"
  }
}

// ---------------------------------------------------------------------------
// Automation Form Dialog
// ---------------------------------------------------------------------------

interface AutomationFormDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  rule: AutomationRule | null
  onSubmit: (data: AutomationCreate | AutomationUpdate) => void
  isPending: boolean
}

function AutomationFormDialog({
  open,
  onOpenChange,
  rule,
  onSubmit,
  isPending,
}: AutomationFormDialogProps) {
  const isEditing = rule !== null

  const [name, setName] = useState("")
  const [displayName, setDisplayName] = useState("")
  const [intentType, setIntentType] = useState("")
  const [patterns, setPatterns] = useState<string[]>([])
  const [allowedRoles, setAllowedRoles] = useState<string[]>([])
  const [validFromStatuses, setValidFromStatuses] = useState<string[]>([])
  const [targetStatus, setTargetStatus] = useState("")
  const [mode, setMode] = useState("confirm")
  const [specialAction, setSpecialAction] = useState("")
  const [priority, setPriority] = useState(10)

  function handleOpenChange(next: boolean) {
    if (next && rule) {
      setName(rule.name)
      setDisplayName(rule.display_name)
      setIntentType(rule.intent_type)
      setPatterns([...rule.patterns])
      setAllowedRoles([...rule.allowed_roles])
      setValidFromStatuses([...rule.valid_from_statuses])
      setTargetStatus(rule.target_status)
      setMode(rule.mode)
      setSpecialAction(rule.special_action ?? "")
      setPriority(rule.priority)
    } else if (next) {
      setName("")
      setDisplayName("")
      setIntentType("")
      setPatterns([])
      setAllowedRoles([])
      setValidFromStatuses([])
      setTargetStatus("")
      setMode("confirm")
      setSpecialAction("")
      setPriority(10)
    }
    onOpenChange(next)
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()

    if (isEditing) {
      const update: AutomationUpdate = {
        display_name: displayName,
        intent_type: intentType,
        patterns,
        allowed_roles: allowedRoles,
        valid_from_statuses: validFromStatuses,
        target_status: targetStatus,
        mode,
        special_action: specialAction || null,
        priority,
      }
      onSubmit(update)
    } else {
      const create: AutomationCreate = {
        name,
        display_name: displayName,
        intent_type: intentType,
        patterns,
        allowed_roles: allowedRoles,
        valid_from_statuses: validFromStatuses,
        target_status: targetStatus,
        mode,
        special_action: specialAction || null,
        priority,
      }
      onSubmit(create)
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>
            {isEditing ? "Editar Regra" : "Nova Regra de Automação"}
          </DialogTitle>
          <DialogDescription>
            {isEditing
              ? "Atualize os campos da regra de automação."
              : "Preencha os campos para criar uma nova regra."}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="rule-name">Nome (slug) *</Label>
              <Input
                id="rule-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="aprovacao_cliente"
                required
                disabled={isEditing}
                aria-describedby={isEditing ? "name-hint" : undefined}
              />
              {isEditing && (
                <p id="name-hint" className="text-xs text-muted-foreground">
                  O nome não pode ser alterado.
                </p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="rule-display-name">Nome de Exibição *</Label>
              <Input
                id="rule-display-name"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="Aprovação do Cliente"
                required
              />
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="rule-intent-type">Tipo de Intenção *</Label>
              <Input
                id="rule-intent-type"
                value={intentType}
                onChange={(e) => setIntentType(e.target.value)}
                placeholder="approval"
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="rule-priority">Prioridade *</Label>
              <Input
                id="rule-priority"
                type="number"
                min={1}
                value={priority}
                onChange={(e) => setPriority(Number(e.target.value))}
                required
              />
              <p className="text-xs text-muted-foreground">
                Menor número = maior prioridade.
              </p>
            </div>
          </div>

          <Separator />

          <div className="space-y-2">
            <Label>Patterns (regex) *</Label>
            <MultiValueEditor
              values={patterns}
              onChange={setPatterns}
              placeholder="Digite um regex e pressione Enter"
              validate={validateRegex}
            />
          </div>

          <Separator />

          <div className="space-y-2">
            <Label>Roles Permitidas</Label>
            <MultiValueEditor
              values={allowedRoles}
              onChange={setAllowedRoles}
              placeholder="Digite uma role e pressione Enter"
              showRoleLabels
            />
            <div className="flex flex-wrap gap-1">
              {AVAILABLE_ROLES.filter((r) => !allowedRoles.includes(r.value)).map((r) => (
                <Button
                  key={r.value}
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => setAllowedRoles([...allowedRoles, r.value])}
                  className="h-6 px-2 text-xs text-muted-foreground"
                >
                  + {r.label}
                </Button>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            <Label>Status de Origem</Label>
            <MultiValueEditor
              values={validFromStatuses}
              onChange={setValidFromStatuses}
              placeholder="Digite um status e pressione Enter"
            />
            <div className="flex flex-wrap gap-1">
              {AVAILABLE_STATUSES.filter((s) => !validFromStatuses.includes(s)).map((s) => (
                <Button
                  key={s}
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => setValidFromStatuses([...validFromStatuses, s])}
                  className="h-6 px-2 text-xs text-muted-foreground"
                >
                  + {s}
                </Button>
              ))}
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="rule-target-status">Status Destino *</Label>
              <Input
                id="rule-target-status"
                value={targetStatus}
                onChange={(e) => setTargetStatus(e.target.value)}
                placeholder="aprovado"
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="rule-mode">Modo *</Label>
              <Select value={mode} onValueChange={setMode}>
                <SelectTrigger id="rule-mode" className="w-full">
                  <SelectValue placeholder="Selecione o modo" />
                </SelectTrigger>
                <SelectContent>
                  {MODE_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="rule-special-action">Ação Especial</Label>
            <Input
              id="rule-special-action"
              value={specialAction}
              onChange={(e) => setSpecialAction(e.target.value)}
              placeholder="Opcional"
            />
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={isPending}
            >
              Cancelar
            </Button>
            <Button type="submit" disabled={isPending}>
              {isPending ? "Salvando..." : isEditing ? "Salvar" : "Criar"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// ---------------------------------------------------------------------------
// Delete Confirmation Dialog
// ---------------------------------------------------------------------------

function DeleteRuleDialog({
  open,
  onOpenChange,
  ruleName,
  onConfirm,
  isPending,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  ruleName: string
  onConfirm: () => void
  isPending: boolean
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Excluir Regra</DialogTitle>
          <DialogDescription>
            Tem certeza que deseja excluir <strong>{ruleName}</strong>? A regra
            será desativada (soft delete).
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={isPending}
          >
            Cancelar
          </Button>
          <Button
            variant="destructive"
            onClick={onConfirm}
            disabled={isPending}
          >
            {isPending ? "Excluindo..." : "Excluir"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ---------------------------------------------------------------------------
// Expandable Badges Cell
// ---------------------------------------------------------------------------

function BadgesCell({
  items,
  max,
  variant = "secondary",
}: {
  items: string[]
  max: number
  variant?: "secondary" | "outline" | "default"
}) {
  const visible = items.slice(0, max)
  const overflow = items.length - max

  if (items.length === 0) {
    return <span className="text-muted-foreground">-</span>
  }

  return (
    <div className="flex flex-wrap gap-1">
      {visible.map((item) => (
        <Badge key={item} variant={variant} className="text-xs">
          {ROLE_LABELS[item] ?? item}
        </Badge>
      ))}
      {overflow > 0 && (
        <Badge variant="outline" className="text-xs">
          +{overflow}
        </Badge>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Expandable Patterns Cell
// ---------------------------------------------------------------------------

function PatternsCell({ patterns }: { patterns: string[] }) {
  const [expanded, setExpanded] = useState(false)

  if (patterns.length === 0) {
    return <span className="text-muted-foreground">-</span>
  }

  return (
    <div className="space-y-1">
      <button
        type="button"
        className="inline-flex items-center gap-1 rounded text-xs outline-none focus-visible:ring-1 focus-visible:ring-ring"
        onClick={(e) => {
          e.stopPropagation()
          setExpanded(!expanded)
        }}
        aria-expanded={expanded}
        aria-label={`${patterns.length} patterns, clique para ${expanded ? "recolher" : "expandir"}`}
      >
        <Badge variant="secondary" className="text-xs">
          {patterns.length} pattern{patterns.length > 1 ? "s" : ""}
        </Badge>
        {expanded ? (
          <ChevronUp className="size-3" aria-hidden="true" />
        ) : (
          <ChevronDown className="size-3" aria-hidden="true" />
        )}
      </button>
      {expanded && (
        <ul className="space-y-0.5">
          {patterns.map((p, i) => (
            <li
              key={i}
              className="max-w-48 truncate font-mono text-xs text-muted-foreground"
              title={p}
            >
              {p}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Pattern Tester Card
// ---------------------------------------------------------------------------

function PatternTester({ rules }: { rules: AutomationRule[] }) {
  const [selectedRuleId, setSelectedRuleId] = useState("")
  const [testText, setTestText] = useState("")
  const [userRole, setUserRole] = useState("")
  const [currentStatus, setCurrentStatus] = useState("")
  const [result, setResult] = useState<PatternTestResponse | null>(null)

  const testMutation = useMutation({
    mutationFn: ({ ruleId, body }: { ruleId: string; body: PatternTestRequest }) =>
      api.post<PatternTestResponse>(`/automations/${ruleId}/test`, body),
    onSuccess: (data) => {
      setResult(data)
    },
    onError: (err: Error) => {
      toast.error(`Erro ao testar pattern: ${err.message}`)
    },
  })

  function handleTest() {
    if (!selectedRuleId || !testText.trim()) return
    const body: PatternTestRequest = {
      text: testText.trim(),
    }
    if (userRole) body.user_role = userRole
    if (currentStatus) body.current_status = currentStatus
    setResult(null)
    testMutation.mutate({ ruleId: selectedRuleId, body })
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <FlaskConical className="size-5" aria-hidden="true" />
          Testar Patterns
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="tester-rule">Regra de Automação</Label>
            <Select value={selectedRuleId} onValueChange={(v) => { setSelectedRuleId(v); setResult(null) }}>
              <SelectTrigger id="tester-rule" className="w-full">
                <SelectValue placeholder="Selecione uma regra" />
              </SelectTrigger>
              <SelectContent>
                {rules.map((rule) => (
                  <SelectItem key={rule.id} value={rule.id}>
                    {rule.display_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="tester-text">Texto de Teste *</Label>
            <Input
              id="tester-text"
              value={testText}
              onChange={(e) => { setTestText(e.target.value); setResult(null) }}
              placeholder="Ex: aprovado, pode publicar"
            />
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-3">
          <div className="space-y-2">
            <Label htmlFor="tester-role">Role (opcional)</Label>
            <Select value={userRole || "__empty__"} onValueChange={(v) => { setUserRole(v === "__empty__" ? "" : v); setResult(null) }}>
              <SelectTrigger id="tester-role" className="w-full">
                <SelectValue placeholder="Qualquer" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__empty__">Qualquer</SelectItem>
                {AVAILABLE_ROLES.map((r) => (
                  <SelectItem key={r.value} value={r.value}>
                    {r.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="tester-status">Status Atual (opcional)</Label>
            <Input
              id="tester-status"
              value={currentStatus}
              onChange={(e) => { setCurrentStatus(e.target.value); setResult(null) }}
              placeholder="Ex: revisao"
            />
          </div>

          <div className="space-y-2">
            <Label className="invisible">Ação</Label>
            <Button
              onClick={handleTest}
              disabled={!selectedRuleId || !testText.trim() || testMutation.isPending}
              className="w-full"
            >
              {testMutation.isPending ? "Testando..." : "Testar"}
            </Button>
          </div>
        </div>

        {/* Result */}
        {result && (
          <div
            role="status"
            className={`rounded-lg border px-4 py-3 text-sm ${
              result.matched
                ? "border-emerald-500/50 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400"
                : "border-destructive/50 bg-destructive/10 text-destructive"
            }`}
          >
            {result.matched ? (
              <div className="space-y-1">
                <div className="flex items-center gap-2 font-medium">
                  <CheckCircle2 className="size-4" aria-hidden="true" />
                  Match encontrado
                </div>
                <p>
                  <span className="text-muted-foreground">Pattern:</span>{" "}
                  <code className="rounded bg-muted px-1 py-0.5 font-mono text-xs">
                    {result.matched_pattern}
                  </code>
                </p>
                {result.intent_type && (
                  <p>
                    <span className="text-muted-foreground">Intenção:</span>{" "}
                    {result.intent_type}
                  </p>
                )}
                {result.target_status && (
                  <p>
                    <span className="text-muted-foreground">Status destino:</span>{" "}
                    {result.target_status}
                  </p>
                )}
              </div>
            ) : (
              <div className="flex items-center gap-2 font-medium">
                <XCircle className="size-4" aria-hidden="true" />
                Nenhum match
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

// ---------------------------------------------------------------------------
// Loading Skeleton
// ---------------------------------------------------------------------------

function AutomationsTableSkeleton() {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Prioridade</TableHead>
          <TableHead>Nome</TableHead>
          <TableHead>Tipo</TableHead>
          <TableHead>Patterns</TableHead>
          <TableHead>Roles</TableHead>
          <TableHead>Status Origem</TableHead>
          <TableHead>Status Destino</TableHead>
          <TableHead>Modo</TableHead>
          <TableHead>Ativo</TableHead>
          <TableHead className="w-24">
            <span className="sr-only">Ações</span>
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {Array.from({ length: 5 }).map((_, i) => (
          <TableRow key={i}>
            <TableCell><Skeleton className="h-5 w-8 rounded-full" /></TableCell>
            <TableCell><Skeleton className="h-4 w-32" /></TableCell>
            <TableCell><Skeleton className="h-5 w-16 rounded-full" /></TableCell>
            <TableCell><Skeleton className="h-5 w-20 rounded-full" /></TableCell>
            <TableCell><Skeleton className="h-5 w-24" /></TableCell>
            <TableCell><Skeleton className="h-5 w-24" /></TableCell>
            <TableCell><Skeleton className="h-4 w-16" /></TableCell>
            <TableCell><Skeleton className="h-5 w-20 rounded-full" /></TableCell>
            <TableCell><Skeleton className="h-4 w-10" /></TableCell>
            <TableCell><Skeleton className="h-8 w-16" /></TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

// ---------------------------------------------------------------------------
// Automations Page
// ---------------------------------------------------------------------------

export function AutomationsPage() {
  const queryClient = useQueryClient()
  const canCreate = usePermission("automations", "create")
  const canUpdate = usePermission("automations", "update")
  const canDelete = usePermission("automations", "delete")
  const [formOpen, setFormOpen] = useState(false)
  const [editingRule, setEditingRule] = useState<AutomationRule | null>(null)
  const [deletingRule, setDeletingRule] = useState<AutomationRule | null>(null)

  // ---- Queries ----
  const {
    data: rules,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["automations"],
    queryFn: () => api.get<AutomationRule[]>("/automations"),
  })

  // ---- Sorted rules ----
  const sortedRules = useMemo(
    () => (rules ?? []).slice().sort((a, b) => a.priority - b.priority),
    [rules]
  )

  // ---- Mutations ----
  const createMutation = useMutation({
    mutationFn: (data: AutomationCreate) =>
      api.post<AutomationRule>("/automations", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["automations"] })
      toast.success("Regra criada com sucesso.")
      setFormOpen(false)
    },
    onError: (err: Error) => {
      toast.error(`Erro ao criar regra: ${err.message}`)
    },
  })

  const updateMutation = useMutation({
    mutationFn: (data: AutomationUpdate & { id: string }) => {
      const { id, ...body } = data
      return api.put<AutomationRule>(`/automations/${id}`, body)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["automations"] })
      toast.success("Regra atualizada com sucesso.")
      setFormOpen(false)
      setEditingRule(null)
    },
    onError: (err: Error) => {
      toast.error(`Erro ao atualizar regra: ${err.message}`)
    },
  })

  const toggleActiveMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      api.put<AutomationRule>(`/automations/${id}`, { is_active }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["automations"] })
      toast.success(
        data.is_active ? "Regra ativada." : "Regra desativada."
      )
    },
    onError: (err: Error) => {
      toast.error(`Erro ao atualizar status: ${err.message}`)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) =>
      api.delete<AutomationRule>(`/automations/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["automations"] })
      toast.success("Regra excluída com sucesso.")
      setDeletingRule(null)
    },
    onError: (err: Error) => {
      toast.error(`Erro ao excluir regra: ${err.message}`)
    },
  })

  // ---- Handlers ----
  function handleAdd() {
    setEditingRule(null)
    setFormOpen(true)
  }

  function handleEdit(rule: AutomationRule) {
    setEditingRule(rule)
    setFormOpen(true)
  }

  const handleToggleActive = useCallback(
    (rule: AutomationRule) => {
      toggleActiveMutation.mutate({ id: rule.id, is_active: !rule.is_active })
    },
    [toggleActiveMutation]
  )

  function handleFormSubmit(data: AutomationCreate | AutomationUpdate) {
    if (editingRule) {
      updateMutation.mutate({ ...data, id: editingRule.id })
    } else {
      createMutation.mutate(data as AutomationCreate)
    }
  }

  function handleDeleteConfirm() {
    if (deletingRule) {
      deleteMutation.mutate(deletingRule.id)
    }
  }

  const isMutating = createMutation.isPending || updateMutation.isPending

  // ---- Render ----
  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">
            Regras de Automação
          </h1>
          <p className="mt-1 text-muted-foreground">
            Tabela de decisão para processamento automático de comentários no
            ClickUp.
          </p>
        </div>
        {canCreate && (
          <Button onClick={handleAdd}>
            <Plus aria-hidden="true" />
            Nova Regra
          </Button>
        )}
      </div>

      {/* Error state */}
      {error && (
        <div
          role="alert"
          className="rounded-lg border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm text-destructive"
        >
          {error instanceof Error
            ? error.message
            : "Erro ao carregar regras de automação."}
        </div>
      )}

      {/* Loading */}
      {isLoading && <AutomationsTableSkeleton />}

      {/* Empty state */}
      {!isLoading && !error && sortedRules.length === 0 && (
        <p className="py-12 text-center text-muted-foreground">
          Nenhuma regra de automação encontrada.
        </p>
      )}

      {/* Data table */}
      {!isLoading && sortedRules.length > 0 && (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-20">Prioridade</TableHead>
                <TableHead>Nome</TableHead>
                <TableHead>Tipo</TableHead>
                <TableHead>Patterns</TableHead>
                <TableHead>Roles</TableHead>
                <TableHead>Status Origem</TableHead>
                <TableHead>Status Destino</TableHead>
                <TableHead>Modo</TableHead>
                <TableHead className="w-16">Ativo</TableHead>
                <TableHead className="w-24">
                  <span className="sr-only">Ações</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sortedRules.map((rule) => (
                <TableRow
                  key={rule.id}
                  className={canUpdate ? "cursor-pointer" : undefined}
                  onClick={canUpdate ? () => handleEdit(rule) : undefined}
                >
                  <TableCell>
                    <Badge variant="outline" className="font-mono text-xs">
                      {rule.priority}
                    </Badge>
                  </TableCell>

                  <TableCell>
                    <div>
                      <span className="font-medium">{rule.display_name}</span>
                      <br />
                      <span className="text-xs text-muted-foreground">
                        {rule.name}
                      </span>
                    </div>
                  </TableCell>

                  <TableCell>
                    <Badge variant="secondary" className="text-xs">
                      {rule.intent_type}
                    </Badge>
                  </TableCell>

                  <TableCell onClick={(e) => e.stopPropagation()}>
                    <PatternsCell patterns={rule.patterns} />
                  </TableCell>

                  <TableCell>
                    <BadgesCell items={rule.allowed_roles} max={2} />
                  </TableCell>

                  <TableCell>
                    <BadgesCell
                      items={rule.valid_from_statuses}
                      max={2}
                      variant="outline"
                    />
                  </TableCell>

                  <TableCell className="text-sm">
                    {rule.target_status || (
                      <span className="text-muted-foreground">-</span>
                    )}
                  </TableCell>

                  <TableCell>
                    <Badge
                      className={
                        rule.mode === "auto"
                          ? "bg-amber-500/15 text-amber-700 hover:bg-amber-500/15 dark:text-amber-400"
                          : "bg-blue-500/15 text-blue-700 hover:bg-blue-500/15 dark:text-blue-400"
                      }
                    >
                      {rule.mode === "auto" ? "Automático" : "Confirmação"}
                    </Badge>
                  </TableCell>

                  <TableCell onClick={(e) => e.stopPropagation()}>
                    <Switch
                      checked={rule.is_active}
                      onCheckedChange={() => handleToggleActive(rule)}
                      disabled={!canUpdate}
                      aria-label={`${rule.display_name} ${rule.is_active ? "ativo" : "inativo"}`}
                    />
                  </TableCell>

                  <TableCell onClick={(e) => e.stopPropagation()}>
                    <div className="flex items-center gap-1">
                      {canUpdate && (
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          onClick={() => handleEdit(rule)}
                          aria-label={`Editar ${rule.display_name}`}
                        >
                          <Pencil className="size-4" aria-hidden="true" />
                        </Button>
                      )}
                      {canDelete && (
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          onClick={() => setDeletingRule(rule)}
                          aria-label={`Excluir ${rule.display_name}`}
                        >
                          <Trash2 className="size-4 text-destructive" aria-hidden="true" />
                        </Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Pattern Tester */}
      {!isLoading && sortedRules.length > 0 && (
        <PatternTester rules={sortedRules} />
      )}

      {/* Form dialog (add / edit) */}
      <AutomationFormDialog
        open={formOpen}
        onOpenChange={(open) => {
          setFormOpen(open)
          if (!open) setEditingRule(null)
        }}
        rule={editingRule}
        onSubmit={handleFormSubmit}
        isPending={isMutating}
      />

      {/* Delete confirmation */}
      <DeleteRuleDialog
        open={deletingRule !== null}
        onOpenChange={(open) => {
          if (!open) setDeletingRule(null)
        }}
        ruleName={deletingRule?.display_name ?? ""}
        onConfirm={handleDeleteConfirm}
        isPending={deleteMutation.isPending}
      />
    </div>
  )
}
