import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Cpu,
  Star,
  Zap,
  Clock,
  Turtle,
  Eye,
  Image,
  AudioLines,
  Video,
  Wrench,
  Plus,
  Pencil,
  RefreshCw,
  LayoutGrid,
  TableProperties,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  X,
  AlertCircle,
  DollarSign,
  Brain,
} from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { usePermission } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { Checkbox } from "@/components/ui/checkbox";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ModelResponse {
  id: string;
  model_id: string;
  provider: string;
  display_name: string;
  description_pt: string;
  tier: string;
  quality_stars: number;
  speed_rating: string;
  cost_rating: string;
  best_for: string[];
  context_length: number;
  prompt_price_per_m: number | null;
  completion_price_per_m: number | null;
  supports_images: boolean;
  supports_tools: boolean;
  supports_audio: boolean;
  supports_video: boolean;
  input_modalities: string[];
  recommended_agents: string[];
  is_recommended: boolean;
  display_order: number;
  is_active: boolean;
  last_synced_at: string | null;
  updated_at: string;
}

interface AgentConfig {
  id: string;
  agent_name: string;
  model_id: string;
  instructions: string[];
  is_active: boolean;
  enabled_tools: string[];
}

interface ModelCreate {
  model_id: string;
  provider: string;
  display_name: string;
  description_pt: string;
  tier: string;
  quality_stars: number;
  speed_rating: string;
  cost_rating: string;
  best_for: string[];
  context_length: number;
  prompt_price_per_m: number | null;
  completion_price_per_m: number | null;
  supports_images: boolean;
  supports_tools: boolean;
  supports_audio: boolean;
  supports_video: boolean;
  input_modalities: string[];
  recommended_agents: string[];
  is_recommended: boolean;
  display_order: number;
  is_active: boolean;
}

type SortField =
  | "display_name"
  | "provider"
  | "quality_stars"
  | "speed_rating"
  | "cost_rating"
  | "context_length";

type SortDirection = "asc" | "desc";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const TIER_META: Record<
  string,
  { label: string; description: string; order: number }
> = {
  recomendado: {
    label: "RECOMENDADO",
    description: "Melhor equilíbrio entre qualidade, velocidade e custo",
    order: 0,
  },
  premium: {
    label: "PREMIUM",
    description: "Máxima qualidade",
    order: 1,
  },
  rapido: {
    label: "RÁPIDO",
    description: "Velocidade e economia",
    order: 2,
  },
  especialista: {
    label: "ESPECIALISTA",
    description: "Casos de uso específicos",
    order: 3,
  },
  router: {
    label: "SMART ROUTER",
    description: "Roteamento automático",
    order: 4,
  },
};

const SPEED_ICONS: Record<string, typeof Zap> = {
  fast: Zap,
  moderate: Clock,
  slow: Turtle,
};

const SPEED_LABELS: Record<string, string> = {
  fast: "Rápido",
  moderate: "Moderado",
  slow: "Lento",
};

const COST_LABELS: Record<string, string> = {
  $: "$",
  $$: "$$",
  $$$: "$$$",
  $$$$: "$$$$",
};

const TIER_OPTIONS = [
  { value: "recomendado", label: "Recomendado" },
  { value: "premium", label: "Premium" },
  { value: "rapido", label: "Rápido" },
  { value: "especialista", label: "Especialista" },
  { value: "router", label: "Router" },
];

const SPEED_OPTIONS = [
  { value: "fast", label: "Rápido" },
  { value: "moderate", label: "Moderado" },
  { value: "slow", label: "Lento" },
];

const COST_OPTIONS = [
  { value: "$", label: "$" },
  { value: "$$", label: "$$" },
  { value: "$$$", label: "$$$" },
  { value: "$$$$", label: "$$$$" },
];

const EMPTY_FORM: ModelCreate = {
  model_id: "",
  provider: "",
  display_name: "",
  description_pt: "",
  tier: "recomendado",
  quality_stars: 3,
  speed_rating: "moderate",
  cost_rating: "$$",
  best_for: [],
  context_length: 128000,
  prompt_price_per_m: null,
  completion_price_per_m: null,
  supports_images: false,
  supports_tools: false,
  supports_audio: false,
  supports_video: false,
  input_modalities: ["text"],
  recommended_agents: [],
  is_recommended: false,
  display_order: 100,
  is_active: true,
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatContextLength(length: number): string {
  if (length >= 1_000_000) {
    return `${(length / 1_000_000).toFixed(length % 1_000_000 === 0 ? 0 : 1)}M`;
  }
  return `${Math.round(length / 1000)}K`;
}

function formatPrice(price: number | null): string {
  if (price === null || price === undefined) return "N/A";
  if (price < 0.01) return `$${price.toFixed(4)}`;
  return `$${price.toFixed(2)}`;
}

function formatRelativeTime(dateString: string | null): string {
  if (!dateString) return "Nunca";
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSeconds = Math.floor(diffMs / 1000);
  const diffMinutes = Math.floor(diffSeconds / 60);
  const diffHours = Math.floor(diffMinutes / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffSeconds < 60) return "agora";
  if (diffMinutes < 60) return `${diffMinutes}min atrás`;
  if (diffHours < 24) return `${diffHours}h atrás`;
  if (diffDays < 7) return `${diffDays}d atrás`;

  return date.toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

function speedSortValue(speed: string): number {
  const map: Record<string, number> = { fast: 3, moderate: 2, slow: 1 };
  return map[speed] ?? 0;
}

function costSortValue(cost: string): number {
  return cost.length;
}

// ---------------------------------------------------------------------------
// KPI Card
// ---------------------------------------------------------------------------

function KpiCard({
  title,
  value,
  icon: Icon,
  loading,
}: {
  title: string;
  value: string | number | undefined;
  icon: typeof Cpu;
  loading: boolean;
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {title}
        </CardTitle>
        <Icon className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
      </CardHeader>
      <CardContent>
        {loading ? (
          <Skeleton className="h-8 w-24" />
        ) : (
          <p className="text-2xl font-bold">{value ?? "..."}</p>
        )}
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Stars Display
// ---------------------------------------------------------------------------

function QualityStars({ count, max = 5 }: { count: number; max?: number }) {
  return (
    <div className="flex items-center gap-0.5" aria-label={`${count} de ${max} estrelas`}>
      {Array.from({ length: max }).map((_, i) => (
        <Star
          key={i}
          className={`h-3.5 w-3.5 ${
            i < count
              ? "fill-amber-400 text-amber-400"
              : "fill-muted text-muted"
          }`}
          aria-hidden="true"
        />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Speed Icon
// ---------------------------------------------------------------------------

function SpeedIndicator({ rating }: { rating: string }) {
  const Icon = SPEED_ICONS[rating] ?? Clock;
  const label = SPEED_LABELS[rating] ?? rating;
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <div className="flex items-center gap-1">
          <Icon
            className={`h-3.5 w-3.5 ${
              rating === "fast"
                ? "text-green-500"
                : rating === "slow"
                  ? "text-orange-500"
                  : "text-blue-500"
            }`}
            aria-hidden="true"
          />
          <span className="text-xs text-muted-foreground">{label}</span>
        </div>
      </TooltipTrigger>
      <TooltipContent>Velocidade: {label}</TooltipContent>
    </Tooltip>
  );
}

// ---------------------------------------------------------------------------
// Modality Badges
// ---------------------------------------------------------------------------

function ModalityBadges({ model }: { model: ModelResponse }) {
  const modalities: { key: string; label: string; icon: typeof Eye; show: boolean }[] = [
    { key: "text", label: "Texto", icon: Eye, show: true },
    { key: "images", label: "Imagens", icon: Image, show: model.supports_images },
    { key: "audio", label: "Áudio", icon: AudioLines, show: model.supports_audio },
    { key: "video", label: "Vídeo", icon: Video, show: model.supports_video },
  ];

  return (
    <div className="flex flex-wrap gap-1">
      {modalities
        .filter((m) => m.show)
        .map((m) => {
          const MIcon = m.icon;
          return (
            <Badge key={m.key} variant="outline" className="gap-1 text-[10px] px-1.5 py-0">
              <MIcon className="h-2.5 w-2.5" aria-hidden="true" />
              {m.label}
            </Badge>
          );
        })}
      {model.supports_tools && (
        <Badge variant="outline" className="gap-1 text-[10px] px-1.5 py-0">
          <Wrench className="h-2.5 w-2.5" aria-hidden="true" />
          Tools
        </Badge>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Model Card
// ---------------------------------------------------------------------------

function ModelCard({
  model,
  isSelected,
  onToggleSelect,
  onViewDetail,
}: {
  model: ModelResponse;
  isSelected: boolean;
  onToggleSelect: (modelId: string) => void;
  onViewDetail: (model: ModelResponse) => void;
}) {
  const isRecommended = model.is_recommended;

  return (
    <Card
      className={`relative overflow-hidden transition-all ${
        isRecommended
          ? "border-primary ring-1 ring-primary/20"
          : "hover:shadow-md"
      }`}
    >
      {isRecommended && (
        <div className="bg-primary text-primary-foreground px-3 py-1 text-xs font-semibold text-center">
          <Star className="inline h-3 w-3 mr-1 fill-current" aria-hidden="true" />
          MODELO RECOMENDADO
        </div>
      )}

      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h3 className="font-semibold leading-none truncate">
                {model.display_name}
              </h3>
              <Badge variant="secondary" className="text-[10px] px-1.5 py-0 shrink-0">
                {model.provider}
              </Badge>
            </div>
          </div>
          <Checkbox
            checked={isSelected}
            onCheckedChange={() => onToggleSelect(model.id)}
            aria-label={`Selecionar ${model.display_name} para comparação`}
          />
        </div>
      </CardHeader>

      <CardContent className="space-y-3">
        {/* Quality, Speed, Cost row */}
        <div className="flex items-center gap-4 flex-wrap">
          <QualityStars count={model.quality_stars} />
          <SpeedIndicator rating={model.speed_rating} />
          <span className="text-xs font-medium text-muted-foreground">
            {COST_LABELS[model.cost_rating] ?? model.cost_rating}
          </span>
        </div>

        {/* Context length badge */}
        <div className="flex items-center gap-2 flex-wrap">
          <Badge variant="outline" className="text-[10px] px-1.5 py-0">
            {formatContextLength(model.context_length)} contexto
          </Badge>
          {!model.is_active && (
            <Badge variant="destructive" className="text-[10px] px-1.5 py-0">
              Inativo
            </Badge>
          )}
        </div>

        {/* Modality badges */}
        <ModalityBadges model={model} />

        {/* Best for tags */}
        {model.best_for.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {model.best_for.map((tag) => (
              <Badge
                key={tag}
                variant="secondary"
                className="text-[10px] px-1.5 py-0 font-normal"
              >
                {tag}
              </Badge>
            ))}
          </div>
        )}

        {/* Action */}
        <Button
          variant="outline"
          size="sm"
          className="w-full mt-2"
          onClick={() => onViewDetail(model)}
        >
          Ver detalhes
        </Button>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Loading Skeletons
// ---------------------------------------------------------------------------

function ModelsLoadingSkeleton() {
  return (
    <div className="space-y-8">
      {/* KPI Skeletons */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Card key={i}>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <Skeleton className="h-4 w-28" />
              <Skeleton className="h-4 w-4" />
            </CardHeader>
            <CardContent>
              <Skeleton className="h-8 w-20" />
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Cards Skeletons */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <Card key={i}>
            <CardHeader className="pb-3">
              <div className="flex items-start justify-between">
                <div className="space-y-2">
                  <Skeleton className="h-5 w-40" />
                  <Skeleton className="h-4 w-20" />
                </div>
                <Skeleton className="h-4 w-4" />
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-4 w-24" />
              <div className="flex gap-1">
                <Skeleton className="h-5 w-16 rounded-full" />
                <Skeleton className="h-5 w-20 rounded-full" />
                <Skeleton className="h-5 w-14 rounded-full" />
              </div>
              <Skeleton className="h-8 w-full" />
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Detail Dialog
// ---------------------------------------------------------------------------

function ModelDetailDialog({
  model,
  open,
  onOpenChange,
  agents,
  onAssignAgent,
  onEdit,
  canEdit,
}: {
  model: ModelResponse | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  agents: AgentConfig[];
  onAssignAgent: (agentName: string, modelId: string) => void;
  onEdit: (model: ModelResponse) => void;
  canEdit?: boolean;
}) {
  const [selectedAgent, setSelectedAgent] = useState("");

  if (!model) return null;

  const usingAgents = agents.filter((a) => a.model_id === model.model_id);

  function handleAssign() {
    if (selectedAgent && model) {
      onAssignAgent(selectedAgent, model.model_id);
      setSelectedAgent("");
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px] max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {model.display_name}
            {model.is_recommended && (
              <Badge className="text-[10px]">Recomendado</Badge>
            )}
          </DialogTitle>
          <DialogDescription>{model.description_pt}</DialogDescription>
        </DialogHeader>

        <div className="space-y-5">
          {/* Specs Section */}
          <div className="space-y-3">
            <h4 className="text-sm font-semibold">Especificações</h4>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <span className="text-muted-foreground">Provider</span>
                <p className="font-medium">{model.provider}</p>
              </div>
              <div>
                <span className="text-muted-foreground">Model ID</span>
                <p className="font-mono text-xs">{model.model_id}</p>
              </div>
              <div>
                <span className="text-muted-foreground">Tier</span>
                <p className="font-medium capitalize">{model.tier}</p>
              </div>
              <div>
                <span className="text-muted-foreground">Contexto</span>
                <p className="font-medium">
                  {formatContextLength(model.context_length)} tokens
                </p>
              </div>
              <div>
                <span className="text-muted-foreground">Qualidade</span>
                <QualityStars count={model.quality_stars} />
              </div>
              <div>
                <span className="text-muted-foreground">Velocidade</span>
                <SpeedIndicator rating={model.speed_rating} />
              </div>
              <div>
                <span className="text-muted-foreground">Custo</span>
                <p className="font-medium">
                  {COST_LABELS[model.cost_rating] ?? model.cost_rating}
                </p>
              </div>
              <div>
                <span className="text-muted-foreground">Status</span>
                <Badge
                  variant={model.is_active ? "default" : "secondary"}
                  className="text-[10px] px-1.5 py-0"
                >
                  {model.is_active ? "Ativo" : "Inativo"}
                </Badge>
              </div>
            </div>
          </div>

          <Separator />

          {/* Modalities */}
          <div className="space-y-2">
            <h4 className="text-sm font-semibold">Modalidades</h4>
            <ModalityBadges model={model} />
          </div>

          <Separator />

          {/* Best for */}
          {model.best_for.length > 0 && (
            <>
              <div className="space-y-2">
                <h4 className="text-sm font-semibold">Ideal para</h4>
                <div className="flex flex-wrap gap-1.5">
                  {model.best_for.map((tag) => (
                    <Badge key={tag} variant="secondary">
                      {tag}
                    </Badge>
                  ))}
                </div>
              </div>
              <Separator />
            </>
          )}

          {/* Cost Estimation */}
          <div className="space-y-2">
            <h4 className="text-sm font-semibold">Custo estimado</h4>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <span className="text-muted-foreground">
                  Prompt (por 1M tokens)
                </span>
                <p className="font-medium">
                  {formatPrice(model.prompt_price_per_m)}
                </p>
              </div>
              <div>
                <span className="text-muted-foreground">
                  Completion (por 1M tokens)
                </span>
                <p className="font-medium">
                  {formatPrice(model.completion_price_per_m)}
                </p>
              </div>
            </div>
          </div>

          <Separator />

          {/* Agents using this model */}
          <div className="space-y-2">
            <h4 className="text-sm font-semibold">Usado por estes agentes</h4>
            {usingAgents.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                Nenhum agente está usando este modelo.
              </p>
            ) : (
              <div className="flex flex-wrap gap-1.5">
                {usingAgents.map((agent) => (
                  <Badge key={agent.id} variant="outline">
                    {agent.agent_name}
                  </Badge>
                ))}
              </div>
            )}
          </div>

          <Separator />

          {/* Assign to agent */}
          <div className="space-y-2">
            <h4 className="text-sm font-semibold">Usar neste agente</h4>
            <div className="flex gap-2">
              <Select value={selectedAgent} onValueChange={setSelectedAgent}>
                <SelectTrigger className="flex-1">
                  <SelectValue placeholder="Selecione um agente" />
                </SelectTrigger>
                <SelectContent>
                  {agents.map((agent) => (
                    <SelectItem key={agent.id} value={agent.agent_name}>
                      {agent.agent_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button
                size="sm"
                onClick={handleAssign}
                disabled={!selectedAgent}
              >
                Aplicar
              </Button>
            </div>
          </div>

          {/* Last synced */}
          <div className="text-xs text-muted-foreground">
            Última sincronização: {formatRelativeTime(model.last_synced_at)}
          </div>
        </div>

        <DialogFooter>
          {canEdit && (
            <Button
              variant="outline"
              onClick={() => {
                onOpenChange(false);
                onEdit(model);
              }}
            >
              <Pencil className="h-4 w-4 mr-1" aria-hidden="true" />
              Editar
            </Button>
          )}
          <Button onClick={() => onOpenChange(false)}>Fechar</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Model Form Dialog
// ---------------------------------------------------------------------------

function ModelFormDialog({
  open,
  onOpenChange,
  editingModel,
  onSubmit,
  isSubmitting,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  editingModel: ModelResponse | null;
  onSubmit: (data: ModelCreate, isEdit: boolean) => void;
  isSubmitting: boolean;
}) {
  const isEdit = !!editingModel;

  const [form, setForm] = useState<ModelCreate>(() =>
    editingModel
      ? {
          model_id: editingModel.model_id,
          provider: editingModel.provider,
          display_name: editingModel.display_name,
          description_pt: editingModel.description_pt,
          tier: editingModel.tier,
          quality_stars: editingModel.quality_stars,
          speed_rating: editingModel.speed_rating,
          cost_rating: editingModel.cost_rating,
          best_for: editingModel.best_for,
          context_length: editingModel.context_length,
          prompt_price_per_m: editingModel.prompt_price_per_m,
          completion_price_per_m: editingModel.completion_price_per_m,
          supports_images: editingModel.supports_images,
          supports_tools: editingModel.supports_tools,
          supports_audio: editingModel.supports_audio,
          supports_video: editingModel.supports_video,
          input_modalities: editingModel.input_modalities,
          recommended_agents: editingModel.recommended_agents,
          is_recommended: editingModel.is_recommended,
          display_order: editingModel.display_order,
          is_active: editingModel.is_active,
        }
      : { ...EMPTY_FORM }
  );

  const [bestForInput, setBestForInput] = useState(
    editingModel ? editingModel.best_for.join(", ") : ""
  );
  const [recommendedAgentsInput, setRecommendedAgentsInput] = useState(
    editingModel ? editingModel.recommended_agents.join(", ") : ""
  );

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    if (!form.model_id || !form.provider || !form.display_name) {
      toast.error("Preencha todos os campos obrigatórios.");
      return;
    }

    const bestFor = bestForInput
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    const recommendedAgents = recommendedAgentsInput
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);

    onSubmit(
      {
        ...form,
        best_for: bestFor,
        recommended_agents: recommendedAgents,
      },
      isEdit
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px] max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {isEdit ? "Editar Modelo" : "Adicionar Modelo"}
          </DialogTitle>
          <DialogDescription>
            {isEdit
              ? "Atualize as informações do modelo."
              : "Preencha os dados para cadastrar um novo modelo."}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Row 1: model_id + provider */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="form-model_id">Model ID</Label>
              <Input
                id="form-model_id"
                value={form.model_id}
                onChange={(e) =>
                  setForm((f) => ({ ...f, model_id: e.target.value }))
                }
                placeholder="anthropic/claude-sonnet-4"
                className="font-mono text-xs"
                disabled={isEdit}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="form-provider">Provider</Label>
              <Input
                id="form-provider"
                value={form.provider}
                onChange={(e) =>
                  setForm((f) => ({ ...f, provider: e.target.value }))
                }
                placeholder="Anthropic"
                required
              />
            </div>
          </div>

          {/* display_name */}
          <div className="space-y-2">
            <Label htmlFor="form-display_name">Nome de Exibição</Label>
            <Input
              id="form-display_name"
              value={form.display_name}
              onChange={(e) =>
                setForm((f) => ({ ...f, display_name: e.target.value }))
              }
              placeholder="Claude Sonnet 4"
              required
            />
          </div>

          {/* description_pt */}
          <div className="space-y-2">
            <Label htmlFor="form-description_pt">Descrição (PT-BR)</Label>
            <Textarea
              id="form-description_pt"
              value={form.description_pt}
              onChange={(e) =>
                setForm((f) => ({ ...f, description_pt: e.target.value }))
              }
              placeholder="Modelo equilibrado entre qualidade e custo..."
              rows={2}
            />
          </div>

          {/* Row: tier, quality_stars, speed_rating, cost_rating */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="form-tier">Tier</Label>
              <Select
                value={form.tier}
                onValueChange={(value) =>
                  setForm((f) => ({ ...f, tier: value }))
                }
              >
                <SelectTrigger id="form-tier">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {TIER_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="form-quality">Qualidade (estrelas 1-5)</Label>
              <Input
                id="form-quality"
                type="number"
                min={1}
                max={5}
                value={form.quality_stars}
                onChange={(e) =>
                  setForm((f) => ({
                    ...f,
                    quality_stars: parseInt(e.target.value) || 1,
                  }))
                }
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="form-speed">Velocidade</Label>
              <Select
                value={form.speed_rating}
                onValueChange={(value) =>
                  setForm((f) => ({ ...f, speed_rating: value }))
                }
              >
                <SelectTrigger id="form-speed">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {SPEED_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="form-cost">Custo</Label>
              <Select
                value={form.cost_rating}
                onValueChange={(value) =>
                  setForm((f) => ({ ...f, cost_rating: value }))
                }
              >
                <SelectTrigger id="form-cost">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {COST_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* context_length + prices */}
          <div className="grid grid-cols-3 gap-4">
            <div className="space-y-2">
              <Label htmlFor="form-context">Contexto (tokens)</Label>
              <Input
                id="form-context"
                type="number"
                value={form.context_length}
                onChange={(e) =>
                  setForm((f) => ({
                    ...f,
                    context_length: parseInt(e.target.value) || 0,
                  }))
                }
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="form-prompt-price">Preço Prompt/1M</Label>
              <Input
                id="form-prompt-price"
                type="number"
                step="0.01"
                value={form.prompt_price_per_m ?? ""}
                onChange={(e) =>
                  setForm((f) => ({
                    ...f,
                    prompt_price_per_m: e.target.value
                      ? parseFloat(e.target.value)
                      : null,
                  }))
                }
                placeholder="3.00"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="form-completion-price">Preço Completion/1M</Label>
              <Input
                id="form-completion-price"
                type="number"
                step="0.01"
                value={form.completion_price_per_m ?? ""}
                onChange={(e) =>
                  setForm((f) => ({
                    ...f,
                    completion_price_per_m: e.target.value
                      ? parseFloat(e.target.value)
                      : null,
                  }))
                }
                placeholder="15.00"
              />
            </div>
          </div>

          {/* Capability toggles */}
          <div className="space-y-3">
            <Label>Capacidades</Label>
            <div className="grid grid-cols-2 gap-3">
              <div className="flex items-center justify-between rounded-lg border p-2">
                <Label htmlFor="form-supports-images" className="text-sm font-normal">
                  Suporte a Imagens
                </Label>
                <Switch
                  id="form-supports-images"
                  checked={form.supports_images}
                  onCheckedChange={(c) =>
                    setForm((f) => ({ ...f, supports_images: c }))
                  }
                />
              </div>
              <div className="flex items-center justify-between rounded-lg border p-2">
                <Label htmlFor="form-supports-tools" className="text-sm font-normal">
                  Suporte a Tools
                </Label>
                <Switch
                  id="form-supports-tools"
                  checked={form.supports_tools}
                  onCheckedChange={(c) =>
                    setForm((f) => ({ ...f, supports_tools: c }))
                  }
                />
              </div>
              <div className="flex items-center justify-between rounded-lg border p-2">
                <Label htmlFor="form-supports-audio" className="text-sm font-normal">
                  Suporte a Áudio
                </Label>
                <Switch
                  id="form-supports-audio"
                  checked={form.supports_audio}
                  onCheckedChange={(c) =>
                    setForm((f) => ({ ...f, supports_audio: c }))
                  }
                />
              </div>
              <div className="flex items-center justify-between rounded-lg border p-2">
                <Label htmlFor="form-supports-video" className="text-sm font-normal">
                  Suporte a Vídeo
                </Label>
                <Switch
                  id="form-supports-video"
                  checked={form.supports_video}
                  onCheckedChange={(c) =>
                    setForm((f) => ({ ...f, supports_video: c }))
                  }
                />
              </div>
            </div>
          </div>

          {/* best_for tags */}
          <div className="space-y-2">
            <Label htmlFor="form-best_for">Ideal para (tags separadas por vírgula)</Label>
            <Input
              id="form-best_for"
              value={bestForInput}
              onChange={(e) => setBestForInput(e.target.value)}
              placeholder="briefings, revisão de conteúdo, resumos"
            />
          </div>

          {/* recommended_agents */}
          <div className="space-y-2">
            <Label htmlFor="form-recommended_agents">
              Agentes recomendados (separados por vírgula)
            </Label>
            <Input
              id="form-recommended_agents"
              value={recommendedAgentsInput}
              onChange={(e) => setRecommendedAgentsInput(e.target.value)}
              placeholder="briefing_analyzer, content_reviewer"
            />
          </div>

          {/* Flags row */}
          <div className="grid grid-cols-3 gap-4">
            <div className="flex items-center justify-between rounded-lg border p-2">
              <Label htmlFor="form-is-recommended" className="text-sm font-normal">
                Recomendado
              </Label>
              <Switch
                id="form-is-recommended"
                checked={form.is_recommended}
                onCheckedChange={(c) =>
                  setForm((f) => ({ ...f, is_recommended: c }))
                }
              />
            </div>
            <div className="flex items-center justify-between rounded-lg border p-2">
              <Label htmlFor="form-is-active" className="text-sm font-normal">
                Ativo
              </Label>
              <Switch
                id="form-is-active"
                checked={form.is_active}
                onCheckedChange={(c) =>
                  setForm((f) => ({ ...f, is_active: c }))
                }
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="form-display-order">Ordem</Label>
              <Input
                id="form-display-order"
                type="number"
                value={form.display_order}
                onChange={(e) =>
                  setForm((f) => ({
                    ...f,
                    display_order: parseInt(e.target.value) || 0,
                  }))
                }
              />
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
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting
                ? "Salvando..."
                : isEdit
                  ? "Salvar Alterações"
                  : "Criar Modelo"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Delete Confirmation Dialog
// ---------------------------------------------------------------------------

function DeleteModelDialog({
  open,
  onOpenChange,
  model,
  onConfirm,
  isDeleting,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  model: ModelResponse | null;
  onConfirm: () => void;
  isDeleting: boolean;
}) {
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Excluir modelo?</AlertDialogTitle>
          <AlertDialogDescription>
            Tem certeza que deseja excluir o modelo{" "}
            <strong>{model?.display_name}</strong>? Esta ação não pode ser
            desfeita.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancelar</AlertDialogCancel>
          <AlertDialogAction
            onClick={onConfirm}
            disabled={isDeleting}
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
          >
            {isDeleting ? "Excluindo..." : "Excluir"}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

// ---------------------------------------------------------------------------
// Comparison Sheet
// ---------------------------------------------------------------------------

function ComparisonSheet({
  open,
  onOpenChange,
  models,
  onRemove,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  models: ModelResponse[];
  onRemove: (id: string) => void;
}) {
  if (models.length === 0) return null;

  type MetricRow = {
    label: string;
    values: string[];
    bestIndex?: number;
  };

  function findBestIndex(values: number[], higherIsBetter: boolean): number {
    if (values.length === 0) return -1;
    let bestIdx = 0;
    for (let i = 1; i < values.length; i++) {
      if (higherIsBetter ? values[i] > values[bestIdx] : values[i] < values[bestIdx]) {
        bestIdx = i;
      }
    }
    return bestIdx;
  }

  const qualityValues = models.map((m) => m.quality_stars);
  const speedValues = models.map((m) => speedSortValue(m.speed_rating));
  const costValues = models.map((m) => costSortValue(m.cost_rating));
  const contextValues = models.map((m) => m.context_length);
  const promptPriceValues = models.map((m) => m.prompt_price_per_m ?? Infinity);
  const completionPriceValues = models.map(
    (m) => m.completion_price_per_m ?? Infinity
  );

  const metrics: MetricRow[] = [
    {
      label: "Provider",
      values: models.map((m) => m.provider),
    },
    {
      label: "Tier",
      values: models.map((m) => TIER_META[m.tier]?.label ?? m.tier),
    },
    {
      label: "Qualidade",
      values: models.map((m) => `${m.quality_stars}/5`),
      bestIndex: findBestIndex(qualityValues, true),
    },
    {
      label: "Velocidade",
      values: models.map((m) => SPEED_LABELS[m.speed_rating] ?? m.speed_rating),
      bestIndex: findBestIndex(speedValues, true),
    },
    {
      label: "Custo",
      values: models.map((m) => COST_LABELS[m.cost_rating] ?? m.cost_rating),
      bestIndex: findBestIndex(costValues, false),
    },
    {
      label: "Contexto",
      values: models.map((m) => formatContextLength(m.context_length)),
      bestIndex: findBestIndex(contextValues, true),
    },
    {
      label: "Preço Prompt/1M",
      values: models.map((m) => formatPrice(m.prompt_price_per_m)),
      bestIndex: findBestIndex(promptPriceValues, false),
    },
    {
      label: "Preço Completion/1M",
      values: models.map((m) => formatPrice(m.completion_price_per_m)),
      bestIndex: findBestIndex(completionPriceValues, false),
    },
    {
      label: "Imagens",
      values: models.map((m) => (m.supports_images ? "Sim" : "Não")),
    },
    {
      label: "Tools",
      values: models.map((m) => (m.supports_tools ? "Sim" : "Não")),
    },
    {
      label: "Áudio",
      values: models.map((m) => (m.supports_audio ? "Sim" : "Não")),
    },
    {
      label: "Vídeo",
      values: models.map((m) => (m.supports_video ? "Sim" : "Não")),
    },
    {
      label: "Tags",
      values: models.map((m) => m.best_for.join(", ") || "—"),
    },
  ];

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="w-full sm:max-w-[600px] overflow-y-auto"
      >
        <SheetHeader>
          <SheetTitle>Comparar Modelos</SheetTitle>
          <SheetDescription>
            Comparação lado a lado de {models.length} modelos selecionados.
          </SheetDescription>
        </SheetHeader>

        <ScrollArea className="flex-1 px-4">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[120px]">Métrica</TableHead>
                {models.map((m) => (
                  <TableHead key={m.id}>
                    <div className="flex items-center gap-1">
                      <span className="truncate text-xs">{m.display_name}</span>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-5 w-5 shrink-0"
                        onClick={() => onRemove(m.id)}
                        aria-label={`Remover ${m.display_name} da comparação`}
                      >
                        <X className="h-3 w-3" aria-hidden="true" />
                      </Button>
                    </div>
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {metrics.map((row) => (
                <TableRow key={row.label}>
                  <TableCell className="text-xs font-medium text-muted-foreground">
                    {row.label}
                  </TableCell>
                  {row.values.map((val, i) => (
                    <TableCell
                      key={i}
                      className={`text-xs ${
                        row.bestIndex === i ? "font-bold text-primary" : ""
                      }`}
                    >
                      {val}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </ScrollArea>
      </SheetContent>
    </Sheet>
  );
}

// ---------------------------------------------------------------------------
// Table View
// ---------------------------------------------------------------------------

function ModelsTableView({
  models,
  selectedIds,
  onToggleSelect,
  onViewDetail,
  sortField,
  sortDirection,
  onSort,
}: {
  models: ModelResponse[];
  selectedIds: Set<string>;
  onToggleSelect: (id: string) => void;
  onViewDetail: (model: ModelResponse) => void;
  sortField: SortField;
  sortDirection: SortDirection;
  onSort: (field: SortField) => void;
}) {
  function SortableHeader({
    field,
    children,
  }: {
    field: SortField;
    children: React.ReactNode;
  }) {
    const isActive = sortField === field;
    return (
      <TableHead>
        <Button
          variant="ghost"
          size="sm"
          className="h-auto px-1 py-0 -ml-1 font-medium"
          onClick={() => onSort(field)}
        >
          {children}
          {isActive ? (
            sortDirection === "asc" ? (
              <ArrowUp className="ml-1 h-3 w-3" aria-hidden="true" />
            ) : (
              <ArrowDown className="ml-1 h-3 w-3" aria-hidden="true" />
            )
          ) : (
            <ArrowUpDown className="ml-1 h-3 w-3 opacity-40" aria-hidden="true" />
          )}
        </Button>
      </TableHead>
    );
  }

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-[40px]" />
            <SortableHeader field="display_name">Modelo</SortableHeader>
            <SortableHeader field="provider">Provider</SortableHeader>
            <SortableHeader field="quality_stars">Qualidade</SortableHeader>
            <SortableHeader field="speed_rating">Velocidade</SortableHeader>
            <SortableHeader field="cost_rating">Custo</SortableHeader>
            <SortableHeader field="context_length">Memória</SortableHeader>
            <TableHead>Imagens</TableHead>
            <TableHead>Tools</TableHead>
            <TableHead className="hidden lg:table-cell">Tags</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {models.map((model) => (
            <TableRow
              key={model.id}
              className="cursor-pointer hover:bg-muted/50"
              onClick={() => onViewDetail(model)}
            >
              <TableCell onClick={(e) => e.stopPropagation()}>
                <Checkbox
                  checked={selectedIds.has(model.id)}
                  onCheckedChange={() => onToggleSelect(model.id)}
                  aria-label={`Selecionar ${model.display_name}`}
                />
              </TableCell>
              <TableCell className="font-medium">
                <div className="flex items-center gap-2">
                  {model.display_name}
                  {model.is_recommended && (
                    <Star
                      className="h-3 w-3 fill-amber-400 text-amber-400"
                      aria-label="Recomendado"
                    />
                  )}
                </div>
              </TableCell>
              <TableCell>
                <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
                  {model.provider}
                </Badge>
              </TableCell>
              <TableCell>
                <QualityStars count={model.quality_stars} />
              </TableCell>
              <TableCell>
                <SpeedIndicator rating={model.speed_rating} />
              </TableCell>
              <TableCell className="font-mono text-xs">
                {COST_LABELS[model.cost_rating] ?? model.cost_rating}
              </TableCell>
              <TableCell>
                <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                  {formatContextLength(model.context_length)}
                </Badge>
              </TableCell>
              <TableCell>
                {model.supports_images ? (
                  <Badge
                    variant="default"
                    className="text-[10px] px-1.5 py-0"
                  >
                    Sim
                  </Badge>
                ) : (
                  <span className="text-xs text-muted-foreground">Não</span>
                )}
              </TableCell>
              <TableCell>
                {model.supports_tools ? (
                  <Badge
                    variant="default"
                    className="text-[10px] px-1.5 py-0"
                  >
                    Sim
                  </Badge>
                ) : (
                  <span className="text-xs text-muted-foreground">Não</span>
                )}
              </TableCell>
              <TableCell className="hidden lg:table-cell">
                <div className="flex flex-wrap gap-1 max-w-[200px]">
                  {model.best_for.slice(0, 3).map((tag) => (
                    <Badge
                      key={tag}
                      variant="secondary"
                      className="text-[10px] px-1.5 py-0 font-normal"
                    >
                      {tag}
                    </Badge>
                  ))}
                  {model.best_for.length > 3 && (
                    <span className="text-[10px] text-muted-foreground">
                      +{model.best_for.length - 3}
                    </span>
                  )}
                </div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Models Page
// ---------------------------------------------------------------------------

export function ModelsPage() {
  const queryClient = useQueryClient();
  const canCreate = usePermission("models", "create");
  const canUpdate = usePermission("models", "update");

  // ---- State ----
  const [viewMode, setViewMode] = useState<"cards" | "table">("cards");
  const [tierFilter, setTierFilter] = useState("all");
  const [useCaseFilter, setUseCaseFilter] = useState("all");
  const [providerFilter, setProviderFilter] = useState("all");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [compareOpen, setCompareOpen] = useState(false);
  const [detailModel, setDetailModel] = useState<ModelResponse | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [editingModel, setEditingModel] = useState<ModelResponse | null>(null);
  const [deletingModel, setDeletingModel] = useState<ModelResponse | null>(
    null
  );
  const [formKey, setFormKey] = useState(0);
  const [sortField, setSortField] = useState<SortField>("display_name");
  const [sortDirection, setSortDirection] = useState<SortDirection>("asc");

  // ---- Queries ----
  const {
    data: models,
    isLoading: isLoadingModels,
    error: modelsError,
  } = useQuery({
    queryKey: ["models"],
    queryFn: () => api.get<ModelResponse[]>("/models"),
  });

  const { data: agents } = useQuery({
    queryKey: ["agent-configs"],
    queryFn: () => api.get<AgentConfig[]>("/agents"),
  });

  // ---- Mutations ----
  const createMutation = useMutation({
    mutationFn: (data: ModelCreate) =>
      api.post<ModelResponse>("/models", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["models"] });
      toast.success("Modelo criado com sucesso.");
      setFormOpen(false);
    },
    onError: (err: Error) => {
      toast.error(`Erro ao criar modelo: ${err.message}`);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({
      modelId,
      update,
    }: {
      modelId: string;
      update: ModelCreate;
    }) =>
      api.put<ModelResponse>(
        `/models/${encodeURIComponent(modelId)}`,
        update
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["models"] });
      toast.success("Modelo atualizado com sucesso.");
      setFormOpen(false);
      setEditingModel(null);
    },
    onError: (err: Error) => {
      toast.error(`Erro ao atualizar modelo: ${err.message}`);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (modelId: string) =>
      api.delete<void>(`/models/${encodeURIComponent(modelId)}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["models"] });
      toast.success("Modelo excluído com sucesso.");
      setDeletingModel(null);
    },
    onError: (err: Error) => {
      toast.error(`Erro ao excluir modelo: ${err.message}`);
      setDeletingModel(null);
    },
  });

  const syncMutation = useMutation({
    mutationFn: () =>
      api.post<{ synced: number; message: string }>("/models/sync", {}),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["models"] });
      toast.success(
        data?.message ?? `Sincronização concluída: ${data?.synced ?? 0} modelos atualizados.`
      );
    },
    onError: (err: Error) => {
      toast.error(`Erro ao sincronizar: ${err.message}`);
    },
  });

  const assignAgentMutation = useMutation({
    mutationFn: ({
      agentName,
      modelId,
    }: {
      agentName: string;
      modelId: string;
    }) =>
      api.put<AgentConfig>(`/agents/${encodeURIComponent(agentName)}`, {
        model_id: modelId,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["agent-configs"] });
      toast.success("Modelo atribuído ao agente com sucesso.");
    },
    onError: (err: Error) => {
      toast.error(`Erro ao atribuir modelo: ${err.message}`);
    },
  });

  // ---- Derived data ----
  const activeModels = useMemo(
    () => (models ?? []).filter((m) => m.is_active),
    [models]
  );

  const uniqueBestFor = useMemo(() => {
    const tags = new Set<string>();
    (models ?? []).forEach((m) => m.best_for.forEach((t) => tags.add(t)));
    return Array.from(tags).sort();
  }, [models]);

  const uniqueProviders = useMemo(() => {
    const providers = new Set<string>();
    (models ?? []).forEach((m) => providers.add(m.provider));
    return Array.from(providers).sort();
  }, [models]);

  // Stats
  const totalActive = activeModels.length;

  const mostUsedModel = useMemo(() => {
    if (!agents || agents.length === 0 || !models || models.length === 0)
      return "—";
    const counts: Record<string, number> = {};
    agents.forEach((a) => {
      counts[a.model_id] = (counts[a.model_id] || 0) + 1;
    });
    const topModelId = Object.entries(counts).sort(
      ([, a], [, b]) => b - a
    )[0]?.[0];
    if (!topModelId) return "—";
    const found = models.find((m) => m.model_id === topModelId);
    return found?.display_name ?? topModelId.split("/").pop() ?? topModelId;
  }, [agents, models]);

  const avgCost = useMemo(() => {
    const withPrice = (models ?? []).filter(
      (m) => m.prompt_price_per_m !== null
    );
    if (withPrice.length === 0) return "N/A";
    const avg =
      withPrice.reduce((sum, m) => sum + (m.prompt_price_per_m ?? 0), 0) /
      withPrice.length;
    return formatPrice(avg);
  }, [models]);

  const lastSynced = useMemo(() => {
    const syncDates = (models ?? [])
      .filter((m) => m.last_synced_at)
      .map((m) => new Date(m.last_synced_at!).getTime());
    if (syncDates.length === 0) return "Nunca";
    const latest = new Date(Math.max(...syncDates)).toISOString();
    return formatRelativeTime(latest);
  }, [models]);

  // Filtered models
  const filteredModels = useMemo(() => {
    let result = models ?? [];

    if (tierFilter !== "all") {
      result = result.filter((m) => m.tier === tierFilter);
    }
    if (useCaseFilter !== "all") {
      result = result.filter((m) => m.best_for.includes(useCaseFilter));
    }
    if (providerFilter !== "all") {
      result = result.filter((m) => m.provider === providerFilter);
    }

    return result;
  }, [models, tierFilter, useCaseFilter, providerFilter]);

  // Sorted models (for table view)
  const sortedModels = useMemo(() => {
    const sorted = [...filteredModels];
    sorted.sort((a, b) => {
      let comparison = 0;
      switch (sortField) {
        case "display_name":
          comparison = a.display_name.localeCompare(b.display_name);
          break;
        case "provider":
          comparison = a.provider.localeCompare(b.provider);
          break;
        case "quality_stars":
          comparison = a.quality_stars - b.quality_stars;
          break;
        case "speed_rating":
          comparison =
            speedSortValue(a.speed_rating) - speedSortValue(b.speed_rating);
          break;
        case "cost_rating":
          comparison =
            costSortValue(a.cost_rating) - costSortValue(b.cost_rating);
          break;
        case "context_length":
          comparison = a.context_length - b.context_length;
          break;
      }
      return sortDirection === "asc" ? comparison : -comparison;
    });
    return sorted;
  }, [filteredModels, sortField, sortDirection]);

  // Grouped models (for cards view)
  const groupedModels = useMemo(() => {
    const groups: Record<string, ModelResponse[]> = {};
    for (const model of filteredModels) {
      const tier = model.tier || "outro";
      if (!groups[tier]) groups[tier] = [];
      groups[tier].push(model);
    }
    // Sort groups by TIER_META order
    return Object.entries(groups).sort(([a], [b]) => {
      const orderA = TIER_META[a]?.order ?? 99;
      const orderB = TIER_META[b]?.order ?? 99;
      return orderA - orderB;
    });
  }, [filteredModels]);

  const comparisonModels = useMemo(
    () => (models ?? []).filter((m) => selectedIds.has(m.id)),
    [models, selectedIds]
  );

  // ---- Handlers ----
  function handleToggleSelect(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else if (next.size < 3) {
        next.add(id);
      } else {
        toast.error("Máximo de 3 modelos para comparação.");
      }
      return next;
    });
  }

  function handleSort(field: SortField) {
    if (sortField === field) {
      setSortDirection((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDirection("asc");
    }
  }

  function handleOpenCreate() {
    setEditingModel(null);
    setFormKey((k) => k + 1);
    setFormOpen(true);
  }

  function handleOpenEdit(model: ModelResponse) {
    setEditingModel(model);
    setFormKey((k) => k + 1);
    setFormOpen(true);
  }

  function handleFormSubmit(data: ModelCreate, isEdit: boolean) {
    if (isEdit && editingModel) {
      updateMutation.mutate({
        modelId: editingModel.id,
        update: data,
      });
    } else {
      createMutation.mutate(data);
    }
  }

  function handleDeleteConfirm() {
    if (deletingModel) {
      deleteMutation.mutate(deletingModel.id);
    }
  }

  function handleAssignAgent(agentName: string, modelId: string) {
    assignAgentMutation.mutate({ agentName, modelId });
  }

  function handleRemoveFromComparison(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      next.delete(id);
      return next;
    });
  }

  const isSubmitting = createMutation.isPending || updateMutation.isPending;

  // ---- Render ----
  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Modelos IA</h1>
          <p className="mt-1 text-muted-foreground">
            Catálogo de modelos de inteligência artificial disponíveis para os
            agentes.
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <Button
            variant="outline"
            size="sm"
            onClick={() => syncMutation.mutate()}
            disabled={syncMutation.isPending}
            className="gap-2"
          >
            <RefreshCw
              className={`h-4 w-4 ${syncMutation.isPending ? "animate-spin" : ""}`}
              aria-hidden="true"
            />
            {syncMutation.isPending ? "Sincronizando..." : "Sincronizar Preços"}
          </Button>
          {canCreate && (
            <Button size="sm" onClick={handleOpenCreate} className="gap-2">
              <Plus className="h-4 w-4" aria-hidden="true" />
              Adicionar Modelo
            </Button>
          )}
        </div>
      </div>

      {/* Error state */}
      {modelsError && (
        <div
          role="alert"
          className="flex items-center gap-2 rounded-lg border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm text-destructive"
        >
          <AlertCircle className="h-4 w-4 shrink-0" aria-hidden="true" />
          {modelsError instanceof Error
            ? modelsError.message
            : "Erro ao carregar modelos."}
        </div>
      )}

      {/* Loading */}
      {isLoadingModels && <ModelsLoadingSkeleton />}

      {/* Content when loaded */}
      {!isLoadingModels && !modelsError && models && (
        <>
          {/* KPI Stats */}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <KpiCard
              title="Total modelos ativos"
              value={totalActive}
              icon={Cpu}
              loading={false}
            />
            <KpiCard
              title="Modelo em uso"
              value={mostUsedModel}
              icon={Brain}
              loading={false}
            />
            <KpiCard
              title="Custo médio por 1M tokens"
              value={avgCost}
              icon={DollarSign}
              loading={false}
            />
            <KpiCard
              title="Última sincronização"
              value={lastSynced}
              icon={RefreshCw}
              loading={false}
            />
          </div>

          {/* Filters and View Toggle */}
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex flex-wrap items-center gap-2">
              {/* Tier filter */}
              <Select value={tierFilter} onValueChange={setTierFilter}>
                <SelectTrigger className="w-[150px]">
                  <SelectValue placeholder="Tier" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Todos os Tiers</SelectItem>
                  {TIER_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              {/* Use case filter */}
              <Select value={useCaseFilter} onValueChange={setUseCaseFilter}>
                <SelectTrigger className="w-[170px]">
                  <SelectValue placeholder="Caso de uso" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Todos os usos</SelectItem>
                  {uniqueBestFor.map((tag) => (
                    <SelectItem key={tag} value={tag}>
                      {tag}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              {/* Provider filter */}
              <Select
                value={providerFilter}
                onValueChange={setProviderFilter}
              >
                <SelectTrigger className="w-[150px]">
                  <SelectValue placeholder="Provider" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Todos Providers</SelectItem>
                  {uniqueProviders.map((p) => (
                    <SelectItem key={p} value={p}>
                      {p}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="flex items-center gap-2">
              {/* Compare button */}
              <Button
                variant="outline"
                size="sm"
                disabled={selectedIds.size < 2}
                onClick={() => setCompareOpen(true)}
                className="gap-2"
              >
                <ArrowUpDown className="h-4 w-4" aria-hidden="true" />
                Comparar ({selectedIds.size})
              </Button>

              {/* View toggle */}
              <div className="flex items-center rounded-lg border p-0.5">
                <Button
                  variant={viewMode === "cards" ? "secondary" : "ghost"}
                  size="icon"
                  className="h-7 w-7"
                  onClick={() => setViewMode("cards")}
                  aria-label="Visualização em cards"
                  aria-pressed={viewMode === "cards"}
                >
                  <LayoutGrid className="h-4 w-4" aria-hidden="true" />
                </Button>
                <Button
                  variant={viewMode === "table" ? "secondary" : "ghost"}
                  size="icon"
                  className="h-7 w-7"
                  onClick={() => setViewMode("table")}
                  aria-label="Visualização em tabela"
                  aria-pressed={viewMode === "table"}
                >
                  <TableProperties className="h-4 w-4" aria-hidden="true" />
                </Button>
              </div>
            </div>
          </div>

          {/* Empty state */}
          {models.length === 0 && (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <div className="flex size-16 items-center justify-center rounded-full bg-muted">
                <Cpu
                  className="size-8 text-muted-foreground"
                  aria-hidden="true"
                />
              </div>
              <h3 className="mt-4 text-lg font-semibold">
                Nenhum modelo cadastrado
              </h3>
              <p className="mt-1 text-sm text-muted-foreground max-w-md">
                Adicione modelos de IA ou sincronize com os provedores para
                popular o catálogo.
              </p>
              <div className="mt-4 flex gap-2">
                {canCreate && (
                  <Button
                    onClick={handleOpenCreate}
                    variant="outline"
                    className="gap-2"
                  >
                    <Plus className="h-4 w-4" aria-hidden="true" />
                    Adicionar Modelo
                  </Button>
                )}
                <Button
                  onClick={() => syncMutation.mutate()}
                  variant="outline"
                  className="gap-2"
                >
                  <RefreshCw className="h-4 w-4" aria-hidden="true" />
                  Sincronizar
                </Button>
              </div>
            </div>
          )}

          {/* No results after filter */}
          {models.length > 0 && filteredModels.length === 0 && (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <p className="text-sm text-muted-foreground">
                Nenhum modelo encontrado com os filtros aplicados.
              </p>
              <Button
                variant="link"
                size="sm"
                className="mt-2"
                onClick={() => {
                  setTierFilter("all");
                  setUseCaseFilter("all");
                  setProviderFilter("all");
                }}
              >
                Limpar filtros
              </Button>
            </div>
          )}

          {/* Cards View */}
          {viewMode === "cards" && filteredModels.length > 0 && (
            <div className="space-y-8">
              {groupedModels.map(([tier, tierModels]) => {
                const meta = TIER_META[tier];
                const isRecommendedTier = tier === "recomendado";
                return (
                  <section key={tier} aria-label={`Modelos ${meta?.label ?? tier}`}>
                    <div className="mb-4 flex items-center gap-3">
                      <Badge
                        variant={isRecommendedTier ? "default" : "outline"}
                        className="text-xs uppercase tracking-wider"
                      >
                        {meta?.label ?? tier.toUpperCase()}
                      </Badge>
                      {meta?.description && (
                        <span className="text-sm text-muted-foreground">
                          {meta.description}
                        </span>
                      )}
                    </div>
                    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                      {tierModels
                        .sort((a, b) => a.display_order - b.display_order)
                        .map((model) => (
                          <ModelCard
                            key={model.id}
                            model={model}
                            isSelected={selectedIds.has(model.id)}
                            onToggleSelect={handleToggleSelect}
                            onViewDetail={setDetailModel}
                          />
                        ))}
                    </div>
                  </section>
                );
              })}
            </div>
          )}

          {/* Table View */}
          {viewMode === "table" && filteredModels.length > 0 && (
            <ModelsTableView
              models={sortedModels}
              selectedIds={selectedIds}
              onToggleSelect={handleToggleSelect}
              onViewDetail={setDetailModel}
              sortField={sortField}
              sortDirection={sortDirection}
              onSort={handleSort}
            />
          )}
        </>
      )}

      {/* Detail Dialog */}
      <ModelDetailDialog
        model={detailModel}
        open={!!detailModel}
        onOpenChange={(open) => {
          if (!open) setDetailModel(null);
        }}
        agents={agents ?? []}
        onAssignAgent={handleAssignAgent}
        onEdit={handleOpenEdit}
        canEdit={canUpdate}
      />

      {/* Form Dialog (create/edit) */}
      <ModelFormDialog
        key={formKey}
        open={formOpen}
        onOpenChange={(open) => {
          setFormOpen(open);
          if (!open) setEditingModel(null);
        }}
        editingModel={editingModel}
        onSubmit={handleFormSubmit}
        isSubmitting={isSubmitting}
      />

      {/* Delete Confirmation */}
      <DeleteModelDialog
        open={!!deletingModel}
        onOpenChange={(open) => {
          if (!open) setDeletingModel(null);
        }}
        model={deletingModel}
        onConfirm={handleDeleteConfirm}
        isDeleting={deleteMutation.isPending}
      />

      {/* Comparison Sheet */}
      <ComparisonSheet
        open={compareOpen}
        onOpenChange={setCompareOpen}
        models={comparisonModels}
        onRemove={handleRemoveFromComparison}
      />
    </div>
  );
}
