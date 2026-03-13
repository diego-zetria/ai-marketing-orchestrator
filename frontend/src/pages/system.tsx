import { useState, useMemo, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ExternalLink,
  Clock,
  Tag,
  Shield,
  Calendar,
  X,
  Save,
  RotateCcw,
} from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { usePermission } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import type { LucideIcon } from "lucide-react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface SystemConfig {
  key: string;
  value: string | number | boolean | string[] | Record<string, unknown>;
  description: string | null;
}

type FieldType = "text" | "number" | "tags";

interface FieldDef {
  key: string;
  label: string;
  type: FieldType;
}

interface SectionDef {
  title: string;
  icon: LucideIcon;
  keys: FieldDef[];
}

// ---------------------------------------------------------------------------
// Section Definitions
// ---------------------------------------------------------------------------

const SECTIONS: SectionDef[] = [
  {
    title: "ClickUp",
    icon: ExternalLink,
    keys: [
      { key: "default_list_id", label: "List ID Padrão", type: "text" },
      { key: "initial_status", label: "Status Inicial", type: "text" },
    ],
  },
  {
    title: "Thresholds (horas)",
    icon: Clock,
    keys: [
      { key: "critical_threshold_hours", label: "Crítico", type: "number" },
      { key: "attention_threshold_hours", label: "Atenção", type: "number" },
      { key: "stalled_threshold_hours", label: "Parado", type: "number" },
      {
        key: "bottleneck_threshold_hours",
        label: "Gargalo",
        type: "number",
      },
      {
        key: "deadline_window_hours",
        label: "Janela de Deadline",
        type: "number",
      },
    ],
  },
  {
    title: "Statuses",
    icon: Tag,
    keys: [
      { key: "valid_statuses", label: "Statuses Válidos", type: "tags" },
      { key: "done_statuses", label: "Statuses Concluídos", type: "tags" },
    ],
  },
  {
    title: "Limites",
    icon: Shield,
    keys: [
      {
        key: "max_file_size_mb",
        label: "Tamanho Max. Arquivo (MB)",
        type: "number",
      },
      {
        key: "min_briefing_length",
        label: "Comprimento Min. Briefing",
        type: "number",
      },
    ],
  },
  {
    title: "Schedule (Resumo Diário)",
    icon: Calendar,
    keys: [
      { key: "summary_daily_hour", label: "Hora", type: "number" },
      { key: "summary_daily_minute", label: "Minuto", type: "number" },
      { key: "summary_timezone", label: "Timezone", type: "text" },
    ],
  },
];

// ---------------------------------------------------------------------------
// Tags Editor
// ---------------------------------------------------------------------------

interface TagsFieldProps {
  value: string[];
  onChange: (tags: string[]) => void;
  id: string;
}

function TagsField({ value, onChange, id }: TagsFieldProps) {
  const [inputValue, setInputValue] = useState("");

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      e.preventDefault();
      const tag = inputValue.trim().toLowerCase();
      if (tag && !value.includes(tag)) {
        onChange([...value, tag]);
      }
      setInputValue("");
    }
  }

  function handleRemoveTag(tag: string) {
    onChange(value.filter((t) => t !== tag));
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-1.5">
        {value.map((tag) => (
          <Badge key={tag} variant="outline" className="gap-1">
            {tag}
            <button
              type="button"
              onClick={() => handleRemoveTag(tag)}
              className="ml-0.5 rounded-full outline-none hover:bg-accent focus-visible:ring-1 focus-visible:ring-ring"
              aria-label={`Remover ${tag}`}
            >
              <X className="size-3" aria-hidden="true" />
            </button>
          </Badge>
        ))}
      </div>
      <Input
        id={id}
        value={inputValue}
        onChange={(e) => setInputValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Digite e pressione Enter"
        className="h-8 text-sm"
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Loading Skeleton
// ---------------------------------------------------------------------------

function SystemLoadingSkeleton() {
  return (
    <div className="space-y-6">
      {Array.from({ length: 5 }).map((_, i) => (
        <Card key={i}>
          <CardHeader>
            <Skeleton className="h-5 w-40" />
          </CardHeader>
          <CardContent className="space-y-4">
            {Array.from({ length: 2 }).map((_, j) => (
              <div key={j} className="space-y-2">
                <Skeleton className="h-4 w-28" />
                <Skeleton className="h-9 w-full" />
              </div>
            ))}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// System Page
// ---------------------------------------------------------------------------

export function SystemPage() {
  const queryClient = useQueryClient();
  const canUpdate = usePermission("system", "update");
  const [localValues, setLocalValues] = useState<
    Record<string, string | number | boolean | string[]>
  >({});
  const [initialized, setInitialized] = useState(false);

  // ---- Query ----
  const {
    data: configs,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["system-config"],
    queryFn: () => api.get<SystemConfig[]>("/system-config"),
  });

  // ---- Build server values map ----
  const serverValues = useMemo(() => {
    const map: Record<string, string | number | boolean | string[]> = {};
    if (configs) {
      for (const config of configs) {
        if (Array.isArray(config.value)) {
          map[config.key] = config.value as string[];
        } else if (
          typeof config.value === "string" ||
          typeof config.value === "number" ||
          typeof config.value === "boolean"
        ) {
          map[config.key] = config.value;
        } else {
          map[config.key] = JSON.stringify(config.value);
        }
      }
    }
    return map;
  }, [configs]);

  // Initialize local state from server
  if (configs && !initialized) {
    setLocalValues({ ...serverValues });
    setInitialized(true);
  }

  // ---- Dirty check ----
  const dirtyKeys = useMemo(() => {
    const dirty: string[] = [];
    for (const key of Object.keys(localValues)) {
      const local = localValues[key];
      const server = serverValues[key];
      if (Array.isArray(local) && Array.isArray(server)) {
        if (JSON.stringify(local) !== JSON.stringify(server)) {
          dirty.push(key);
        }
      } else if (local !== server) {
        dirty.push(key);
      }
    }
    // Also check for keys in localValues not in serverValues
    for (const key of Object.keys(localValues)) {
      if (!(key in serverValues) && !dirty.includes(key)) {
        dirty.push(key);
      }
    }
    return dirty;
  }, [localValues, serverValues]);

  const isDirty = dirtyKeys.length > 0;

  // ---- Mutation ----
  const [isSaving, setIsSaving] = useState(false);

  const saveMutation = useMutation({
    mutationFn: async (keys: string[]) => {
      const promises = keys.map((key) =>
        api.put<SystemConfig>(`/system-config/${encodeURIComponent(key)}`, {
          value: localValues[key],
        })
      );
      return Promise.all(promises);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["system-config"] });
      setInitialized(false);
      toast.success("Configurações salvas com sucesso.");
      setIsSaving(false);
    },
    onError: (err: Error) => {
      toast.error(`Erro ao salvar configurações: ${err.message}`);
      setIsSaving(false);
    },
  });

  // ---- Handlers ----
  const updateValue = useCallback(
    (key: string, value: string | number | boolean | string[]) => {
      setLocalValues((prev) => ({ ...prev, [key]: value }));
    },
    []
  );

  function handleSave() {
    if (dirtyKeys.length === 0) return;
    setIsSaving(true);
    saveMutation.mutate(dirtyKeys);
  }

  function handleDiscard() {
    setLocalValues({ ...serverValues });
    toast.success("Alterações descartadas.");
  }

  function getFieldValue(key: string, type: FieldType) {
    const val = localValues[key];
    if (type === "tags") {
      return Array.isArray(val) ? val : [];
    }
    if (type === "number") {
      return typeof val === "number" ? val : typeof val === "string" ? val : "";
    }
    return typeof val === "string" ? val : val !== undefined ? String(val) : "";
  }

  // ---- Render ----
  return (
    <div className="space-y-6 pb-20">
      {/* Page header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">
          Configurações do Sistema
        </h1>
        <p className="mt-1 text-muted-foreground">
          Configurações gerais do sistema.
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
            : "Erro ao carregar configurações."}
        </div>
      )}

      {/* Loading */}
      {isLoading && <SystemLoadingSkeleton />}

      {/* Sections */}
      {!isLoading && !error && initialized && (
        <>
          {SECTIONS.map((section) => {
            const Icon = section.icon;
            return (
              <Card key={section.title}>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Icon
                      className="size-5 text-muted-foreground"
                      aria-hidden="true"
                    />
                    {section.title}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                    {section.keys.map((field) => {
                      const fieldId = `config-${field.key}`;
                      return (
                        <div key={field.key} className="space-y-2">
                          <Label htmlFor={fieldId}>{field.label}</Label>

                          {field.type === "text" && (
                            <Input
                              id={fieldId}
                              value={getFieldValue(field.key, "text") as string}
                              onChange={(e) =>
                                updateValue(field.key, e.target.value)
                              }
                              placeholder={field.label}
                            />
                          )}

                          {field.type === "number" && (
                            <Input
                              id={fieldId}
                              type="number"
                              value={getFieldValue(field.key, "number") as string | number}
                              onChange={(e) => {
                                const num = e.target.value === "" ? "" : Number(e.target.value);
                                updateValue(field.key, num);
                              }}
                              placeholder={field.label}
                            />
                          )}

                          {field.type === "tags" && (
                            <TagsField
                              id={fieldId}
                              value={
                                getFieldValue(field.key, "tags") as string[]
                              }
                              onChange={(tags) =>
                                updateValue(field.key, tags)
                              }
                            />
                          )}
                        </div>
                      );
                    })}
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </>
      )}

      {/* Sticky save bar */}
      {!isLoading && !error && initialized && (
        <div className="sticky bottom-0 z-10 -mx-6 border-t bg-background px-6 py-3">
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
              {isDirty
                ? `${dirtyKeys.length} ${dirtyKeys.length === 1 ? "campo alterado" : "campos alterados"}`
                : "Nenhuma alteração pendente"}
            </p>
            {canUpdate && (
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleDiscard}
                  disabled={!isDirty || isSaving}
                >
                  <RotateCcw className="size-4" aria-hidden="true" />
                  Descartar
                </Button>
                <Button
                  size="sm"
                  onClick={handleSave}
                  disabled={!isDirty || isSaving}
                >
                  <Save className="size-4" aria-hidden="true" />
                  {isSaving ? "Salvando..." : "Salvar Alterações"}
                </Button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
