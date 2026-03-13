import { useState, useMemo, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Bot, Wrench, BookOpen, Sparkles, Cpu, FileText, ExternalLink } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { usePermission } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
} from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { BlockEditor } from "@/components/block-editor";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface AgentConfig {
  id: string;
  agent_name: string;
  model_id: string;
  instructions: string[];
  is_active: boolean;
  enabled_tools: string[];
}

interface AgentConfigUpdate {
  model_id?: string;
  instructions?: string[];
  is_active?: boolean;
  enabled_tools?: string[];
}

interface Tool {
  id: string;
  tool_key: string;
  display_name: string;
  description: string;
  category: string;
  is_global: boolean;
  config: Record<string, unknown>;
}

interface KnowledgeDoc {
  id: string;
  title: string;
  category: string;
  content: string;
  file_key: string | null;
  file_name: string | null;
  file_type: string | null;
  file_size: number | null;
  agent_access: string[];
  is_active: boolean;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const AGENT_META: Record<
  string,
  { label: string; description: string; icon: string }
> = {
  briefing_analyzer: {
    label: "Analisador de Briefing",
    description: "Analisa briefings recebidos via Telegram e cria tarefas no ClickUp.",
    icon: "briefing",
  },
  schedule_generator: {
    label: "Gerador de Cronograma",
    description: "Gera cronogramas de posts com base nos briefings analisados.",
    icon: "schedule",
  },
  summary_generator: {
    label: "Gerador de Resumo",
    description: "Gera resumos diários e semanais das atividades da equipe.",
    icon: "summary",
  },
  content_reviewer: {
    label: "Revisor de Conteúdo",
    description: "Revisa conteúdos e fornece feedback antes da aprovação final.",
    icon: "reviewer",
  },
};

const MODELS = [
  { value: "anthropic/claude-sonnet-4", label: "Claude Sonnet 4" },
  { value: "anthropic/claude-haiku-4-5-20251001", label: "Claude Haiku 4.5" },
  { value: "google/gemini-2.5-flash", label: "Gemini 2.5 Flash" },
  { value: "google/gemini-2.5-pro", label: "Gemini 2.5 Pro" },
  { value: "openai/gpt-4o", label: "GPT-4o" },
  { value: "openai/gpt-4o-mini", label: "GPT-4o Mini" },
] as const;

const MODEL_LABELS: Record<string, string> = Object.fromEntries(
  MODELS.map((m) => [m.value, m.label])
);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Group tools by category, returning entries sorted alphabetically by category. */
function groupToolsByCategory(tools: Tool[]): [string, Tool[]][] {
  const grouped: Record<string, Tool[]> = {};
  for (const tool of tools) {
    const cat = tool.category || "Geral";
    if (!grouped[cat]) grouped[cat] = [];
    grouped[cat].push(tool);
  }
  return Object.entries(grouped).sort(([a], [b]) => a.localeCompare(b));
}

// ---------------------------------------------------------------------------
// Section Header
// ---------------------------------------------------------------------------

function SectionHeader({
  icon: Icon,
  title,
  badge,
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  badge?: string;
}) {
  return (
    <div className="flex items-center gap-2">
      <Icon className="size-4 text-muted-foreground" />
      <span className="text-sm font-medium">{title}</span>
      {badge && (
        <Badge variant="outline" className="text-[10px] px-1.5 py-0">
          {badge}
        </Badge>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Agent Config Card
// ---------------------------------------------------------------------------

interface AgentCardProps {
  agent: AgentConfig;
  tools: Tool[];
  knowledgeDocs: KnowledgeDoc[];
  onSave: (agentName: string, update: AgentConfigUpdate) => void;
  isSaving: boolean;
  disabled?: boolean;
}

function AgentConfigCard({ agent, tools, knowledgeDocs, onSave, isSaving, disabled }: AgentCardProps) {
  const meta = AGENT_META[agent.agent_name] ?? {
    label: agent.agent_name,
    description: agent.agent_name,
    icon: "default",
  };

  const [modelId, setModelId] = useState(agent.model_id);
  const [isActive, setIsActive] = useState(agent.is_active);
  const [instructionsMarkdown, setInstructionsMarkdown] = useState(
    agent.instructions.join("\n")
  );
  const [enabledTools, setEnabledTools] = useState<string[]>(
    agent.enabled_tools ?? []
  );

  const isDirty = useMemo(() => {
    const modelChanged = modelId !== agent.model_id;
    const activeChanged = isActive !== agent.is_active;
    const currentInstructions = instructionsMarkdown
      .split("\n")
      .map((line) => line.trim())
      .filter((line) => line.length > 0);
    const instructionsChanged =
      JSON.stringify(currentInstructions) !==
      JSON.stringify(agent.instructions);
    const toolsChanged =
      JSON.stringify([...enabledTools].sort()) !==
      JSON.stringify([...(agent.enabled_tools ?? [])].sort());
    return modelChanged || activeChanged || instructionsChanged || toolsChanged;
  }, [modelId, isActive, instructionsMarkdown, enabledTools, agent]);

  const handleInstructionsChange = useCallback((md: string) => {
    setInstructionsMarkdown(md);
  }, []);

  function handleToolToggle(toolKey: string, checked: boolean) {
    setEnabledTools((prev) =>
      checked ? [...prev, toolKey] : prev.filter((k) => k !== toolKey)
    );
  }

  function handleSave() {
    const instructions = instructionsMarkdown
      .split("\n")
      .map((line) => line.trim())
      .filter((line) => line.length > 0);

    onSave(agent.agent_name, {
      model_id: modelId,
      instructions,
      is_active: isActive,
      enabled_tools: enabledTools,
    });
  }

  const toolGroups = useMemo(() => groupToolsByCategory(tools), [tools]);

  return (
    <Card className="overflow-hidden">
      {/* Header with agent name, status badge, and toggle */}
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10">
              <Bot className="size-5 text-primary" aria-hidden="true" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-semibold leading-none">{meta.label}</h3>
                <Badge
                  variant={isActive ? "default" : "secondary"}
                  className="text-[10px] px-1.5 py-0"
                >
                  {isActive ? "Ativo" : "Inativo"}
                </Badge>
              </div>
              <p className="mt-1 text-sm text-muted-foreground">
                {meta.description}
              </p>
            </div>
          </div>
          <Switch
            checked={isActive}
            onCheckedChange={setIsActive}
            aria-label={`${isActive ? "Desativar" : "Ativar"} agente ${meta.label}`}
          />
        </div>
      </CardHeader>

      <CardContent className="space-y-5">
        {/* Model Selection */}
        <div className="space-y-2">
          <SectionHeader icon={Cpu} title="Modelo" />
          <Select value={modelId} onValueChange={setModelId}>
            <SelectTrigger className="w-full">
              <SelectValue>{MODEL_LABELS[modelId] ?? modelId}</SelectValue>
            </SelectTrigger>
            <SelectContent>
              {MODELS.map((model) => (
                <SelectItem key={model.value} value={model.value}>
                  {model.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p className="text-xs text-muted-foreground font-mono">{modelId}</p>
        </div>

        <Separator />

        {/* Instructions - BlockNote Editor */}
        <div className="space-y-2">
          <SectionHeader icon={Sparkles} title="Instruções do Agente" />
          <div className="rounded-md border min-h-[200px]">
            <BlockEditor
              initialMarkdown={agent.instructions.join("\n")}
              onChange={handleInstructionsChange}
            />
          </div>
          <p className="text-xs text-muted-foreground">
            Defina o comportamento e personalidade do agente. Use formatação rica para organizar.
          </p>
        </div>

        <Separator />

        {/* Tools - Dynamic toggles grouped by category */}
        <div className="space-y-3">
          <SectionHeader icon={Wrench} title="Ferramentas" />
          {tools.length === 0 ? (
            <p className="text-xs text-muted-foreground">
              Nenhuma ferramenta cadastrada.
            </p>
          ) : (
            <div className="space-y-3">
              {toolGroups.map(([category, categoryTools]) => (
                <div key={category} className="space-y-1.5">
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                    {category}
                  </p>
                  <div className="space-y-1">
                    {categoryTools.map((tool) => (
                      <div
                        key={tool.tool_key}
                        className="flex items-center justify-between rounded-md px-2 py-1.5 hover:bg-muted/50 transition-colors"
                      >
                        <div className="flex flex-col gap-0.5">
                          <Label
                            htmlFor={`tool-${agent.agent_name}-${tool.tool_key}`}
                            className="text-sm font-normal cursor-pointer"
                          >
                            {tool.display_name}
                          </Label>
                          {tool.description && (
                            <span className="text-[11px] text-muted-foreground leading-tight">
                              {tool.description}
                            </span>
                          )}
                        </div>
                        <Switch
                          id={`tool-${agent.agent_name}-${tool.tool_key}`}
                          checked={enabledTools.includes(tool.tool_key)}
                          onCheckedChange={(checked) =>
                            handleToolToggle(tool.tool_key, checked)
                          }
                          aria-label={`${enabledTools.includes(tool.tool_key) ? "Desativar" : "Ativar"} ferramenta ${tool.display_name}`}
                        />
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
          <p className="text-xs text-muted-foreground">
            Ative ou desative as ferramentas que o agente pode utilizar.
          </p>
        </div>

        <Separator />

        {/* Knowledge - Linked documents */}
        <div className="space-y-2">
          <SectionHeader icon={BookOpen} title="Conhecimento" />
          {knowledgeDocs.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Nenhum documento vinculado
            </p>
          ) : (
            <div className="space-y-1.5">
              {knowledgeDocs.map((doc) => (
                <div
                  key={doc.id}
                  className="flex items-center gap-2 rounded-md px-2 py-1.5"
                >
                  <FileText className="size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
                  <span className="text-sm">{doc.title}</span>
                  <Badge variant="outline" className="text-[10px] px-1.5 py-0 ml-auto">
                    {doc.category}
                  </Badge>
                </div>
              ))}
            </div>
          )}
          <a
            href="/knowledge"
            className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
          >
            Gerenciar
            <ExternalLink className="size-3" aria-hidden="true" />
          </a>
        </div>
      </CardContent>

      <CardFooter className="justify-end border-t bg-muted/30 px-6 py-3">
        <Button onClick={handleSave} disabled={!isDirty || isSaving || disabled} size="sm">
          {isSaving ? "Salvando..." : "Salvar Configuração"}
        </Button>
      </CardFooter>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Loading Skeleton
// ---------------------------------------------------------------------------

function AgentsLoadingSkeleton() {
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      {Array.from({ length: 4 }).map((_, i) => (
        <Card key={i}>
          <CardHeader>
            <div className="flex items-start justify-between">
              <div className="flex items-start gap-3">
                <Skeleton className="size-10 rounded-lg" />
                <div className="space-y-2">
                  <Skeleton className="h-5 w-40" />
                  <Skeleton className="h-4 w-64" />
                </div>
              </div>
              <Skeleton className="h-5 w-10" />
            </div>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="space-y-2">
              <Skeleton className="h-4 w-16" />
              <Skeleton className="h-9 w-full" />
            </div>
            <Skeleton className="h-px w-full" />
            <div className="space-y-2">
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-[200px] w-full" />
            </div>
            <Skeleton className="h-px w-full" />
            <div className="space-y-2">
              <Skeleton className="h-4 w-24" />
              <div className="flex gap-1.5">
                <Skeleton className="h-5 w-20 rounded-full" />
                <Skeleton className="h-5 w-28 rounded-full" />
              </div>
            </div>
          </CardContent>
          <CardFooter className="justify-end border-t bg-muted/30">
            <Skeleton className="h-8 w-32" />
          </CardFooter>
        </Card>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Agents Page
// ---------------------------------------------------------------------------

export function AgentsPage() {
  const queryClient = useQueryClient();
  const canUpdate = usePermission("agents", "update");
  const [savingAgent, setSavingAgent] = useState<string | null>(null);

  // ---- Queries ----
  const {
    data: agents,
    isLoading: isLoadingAgents,
    error: agentsError,
  } = useQuery({
    queryKey: ["agent-configs"],
    queryFn: () => api.get<AgentConfig[]>("/agents"),
  });

  const { data: tools } = useQuery({
    queryKey: ["tools"],
    queryFn: () => api.get<Tool[]>("/tools"),
  });

  const { data: knowledgeDocs } = useQuery({
    queryKey: ["knowledge"],
    queryFn: () => api.get<KnowledgeDoc[]>("/knowledge"),
  });

  // ---- Mutation ----
  const updateMutation = useMutation({
    mutationFn: ({
      agentName,
      update,
    }: {
      agentName: string;
      update: AgentConfigUpdate;
    }) =>
      api.put<AgentConfig>(
        `/agents/${encodeURIComponent(agentName)}`,
        update
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["agent-configs"] });
      toast.success("Agente atualizado com sucesso.");
      setSavingAgent(null);
    },
    onError: (err: Error) => {
      toast.error(`Erro ao atualizar agente: ${err.message}`);
      setSavingAgent(null);
    },
  });

  // ---- Handlers ----
  function handleSave(agentName: string, update: AgentConfigUpdate) {
    setSavingAgent(agentName);
    updateMutation.mutate({ agentName, update });
  }

  // ---- Derived state ----
  const isLoading = isLoadingAgents;
  const error = agentsError;

  // ---- Render ----
  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Agentes IA</h1>
        <p className="mt-1 text-muted-foreground">
          Configure o comportamento, modelo e instruções de cada agente de inteligência artificial.
        </p>
      </div>

      {/* Error state */}
      {error && (
        <div
          role="alert"
          className="rounded-lg border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm text-destructive"
        >
          {error instanceof Error
            ? error.message
            : "Erro ao carregar configurações dos agentes."}
        </div>
      )}

      {/* Loading */}
      {isLoading && <AgentsLoadingSkeleton />}

      {/* Empty state */}
      {!isLoading && !error && agents && agents.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <div className="flex size-16 items-center justify-center rounded-full bg-muted">
            <Bot className="size-8 text-muted-foreground" aria-hidden="true" />
          </div>
          <h3 className="mt-4 text-lg font-semibold">Nenhum agente configurado</h3>
          <p className="mt-1 text-sm text-muted-foreground max-w-md">
            Os agentes serão criados automaticamente quando o sistema for iniciado pela primeira vez.
          </p>
        </div>
      )}

      {/* Agent cards */}
      {!isLoading && agents && agents.length > 0 && (
        <div className="grid gap-6 lg:grid-cols-2">
          {agents.map((agent) => (
            <AgentConfigCard
              key={agent.id}
              agent={agent}
              tools={tools ?? []}
              knowledgeDocs={
                (knowledgeDocs ?? []).filter((d) =>
                  d.agent_access.includes(agent.agent_name)
                )
              }
              onSave={handleSave}
              isSaving={savingAgent === agent.agent_name}
              disabled={!canUpdate}
            />
          ))}
        </div>
      )}
    </div>
  );
}
