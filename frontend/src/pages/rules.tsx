import { useState, useMemo, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, ChevronsUpDown, X, Plus } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { usePermission } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface AssignmentRule {
  id: string;
  service_type: string;
  default_assignee_ids: string[];
  tags: string[];
}

interface AssignmentRuleUpdate {
  default_assignee_ids?: string[];
  tags?: string[];
}

interface TeamMember {
  id: string;
  clickup_user_id: string | null;
  name: string;
  role: string | null;
  telegram_chat_id: number;
  active: boolean;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SERVICE_TYPE_LABELS: Record<string, string> = {
  design: "Design",
  copy: "Copy",
  "design+copy": "Design + Copy",
};

// ---------------------------------------------------------------------------
// Assignee Multi-Select
// ---------------------------------------------------------------------------

interface AssigneeMultiSelectProps {
  selected: string[];
  onChange: (ids: string[]) => void;
  members: TeamMember[];
  memberMap: Map<string, string>;
}

function AssigneeMultiSelect({
  selected,
  onChange,
  members,
  memberMap,
}: AssigneeMultiSelectProps) {
  const [open, setOpen] = useState(false);

  const toggleMember = useCallback(
    (memberId: string) => {
      if (selected.includes(memberId)) {
        onChange(selected.filter((id) => id !== memberId));
      } else {
        onChange([...selected, memberId]);
      }
    },
    [selected, onChange]
  );

  const removeMember = useCallback(
    (memberId: string) => {
      onChange(selected.filter((id) => id !== memberId));
    },
    [selected, onChange]
  );

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-1.5">
        {selected.map((id) => (
          <Badge key={id} variant="secondary" className="gap-1">
            {memberMap.get(id) ?? id}
            <button
              type="button"
              onClick={() => removeMember(id)}
              className="ml-0.5 rounded-full outline-none hover:bg-secondary-foreground/20 focus-visible:ring-1 focus-visible:ring-ring"
              aria-label={`Remover ${memberMap.get(id) ?? id}`}
            >
              <X className="size-3" aria-hidden="true" />
            </button>
          </Badge>
        ))}
      </div>

      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            variant="outline"
            size="sm"
            role="combobox"
            aria-expanded={open}
            className="justify-between"
          >
            <Plus className="size-3" aria-hidden="true" />
            Adicionar membro
            <ChevronsUpDown className="ml-1 size-3 opacity-50" aria-hidden="true" />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-64 p-0" align="start">
          <Command>
            <CommandInput placeholder="Buscar membro..." />
            <CommandList>
              <CommandEmpty>Nenhum membro encontrado.</CommandEmpty>
              <CommandGroup>
                {members.map((member) => {
                  const isSelected = selected.includes(member.id);
                  return (
                    <CommandItem
                      key={member.id}
                      value={member.name}
                      onSelect={() => toggleMember(member.id)}
                    >
                      <Check
                        className={cn(
                          "size-4",
                          isSelected ? "opacity-100" : "opacity-0"
                        )}
                        aria-hidden="true"
                      />
                      {member.name}
                    </CommandItem>
                  );
                })}
              </CommandGroup>
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tags Editor
// ---------------------------------------------------------------------------

interface TagsEditorProps {
  tags: string[];
  onChange: (tags: string[]) => void;
}

function TagsEditor({ tags, onChange }: TagsEditorProps) {
  const [inputValue, setInputValue] = useState("");

  function handleAddTag(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      e.preventDefault();
      const tag = inputValue.trim().toLowerCase();
      if (tag && !tags.includes(tag)) {
        onChange([...tags, tag]);
      }
      setInputValue("");
    }
  }

  function handleRemoveTag(tag: string) {
    onChange(tags.filter((t) => t !== tag));
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-1.5">
        {tags.map((tag) => (
          <Badge key={tag} variant="outline" className="gap-1">
            {tag}
            <button
              type="button"
              onClick={() => handleRemoveTag(tag)}
              className="ml-0.5 rounded-full outline-none hover:bg-accent focus-visible:ring-1 focus-visible:ring-ring"
              aria-label={`Remover tag ${tag}`}
            >
              <X className="size-3" aria-hidden="true" />
            </button>
          </Badge>
        ))}
      </div>
      <Input
        value={inputValue}
        onChange={(e) => setInputValue(e.target.value)}
        onKeyDown={handleAddTag}
        placeholder="Digite uma tag e pressione Enter"
        className="h-8 text-sm"
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Assignment Rule Card
// ---------------------------------------------------------------------------

interface RuleCardProps {
  rule: AssignmentRule;
  members: TeamMember[];
  memberMap: Map<string, string>;
  onSave: (serviceType: string, update: AssignmentRuleUpdate) => void;
  isSaving: boolean;
  disabled?: boolean;
}

function AssignmentRuleCard({
  rule,
  members,
  memberMap,
  onSave,
  isSaving,
  disabled,
}: RuleCardProps) {
  const [assigneeIds, setAssigneeIds] = useState<string[]>(rule.default_assignee_ids);
  const [tags, setTags] = useState<string[]>(rule.tags);

  const isDirty = useMemo(() => {
    const assigneesChanged =
      JSON.stringify(assigneeIds.slice().sort()) !==
      JSON.stringify(rule.default_assignee_ids.slice().sort());
    const tagsChanged =
      JSON.stringify(tags.slice().sort()) !==
      JSON.stringify(rule.tags.slice().sort());
    return assigneesChanged || tagsChanged;
  }, [assigneeIds, tags, rule.default_assignee_ids, rule.tags]);

  function handleSave() {
    onSave(rule.service_type, {
      default_assignee_ids: assigneeIds,
      tags,
    });
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          {SERVICE_TYPE_LABELS[rule.service_type] ?? rule.service_type}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label>Responsáveis</Label>
          <AssigneeMultiSelect
            selected={assigneeIds}
            onChange={setAssigneeIds}
            members={members}
            memberMap={memberMap}
          />
        </div>

        <Separator />

        <div className="space-y-2">
          <Label>Tags</Label>
          <TagsEditor tags={tags} onChange={setTags} />
        </div>
      </CardContent>
      <CardFooter className="justify-end">
        <Button onClick={handleSave} disabled={!isDirty || isSaving || disabled} size="sm">
          {isSaving ? "Salvando..." : "Salvar"}
        </Button>
      </CardFooter>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Loading Skeleton
// ---------------------------------------------------------------------------

function RulesLoadingSkeleton() {
  return (
    <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
      {Array.from({ length: 3 }).map((_, i) => (
        <Card key={i}>
          <CardHeader>
            <Skeleton className="h-5 w-32" />
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Skeleton className="h-4 w-24" />
              <div className="flex gap-1.5">
                <Skeleton className="h-5 w-20 rounded-full" />
                <Skeleton className="h-5 w-24 rounded-full" />
              </div>
              <Skeleton className="h-8 w-36" />
            </div>
            <Skeleton className="h-px w-full" />
            <div className="space-y-2">
              <Skeleton className="h-4 w-16" />
              <div className="flex gap-1.5">
                <Skeleton className="h-5 w-16 rounded-full" />
                <Skeleton className="h-5 w-14 rounded-full" />
              </div>
              <Skeleton className="h-8 w-full" />
            </div>
          </CardContent>
          <CardFooter className="justify-end">
            <Skeleton className="h-8 w-20" />
          </CardFooter>
        </Card>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Rules Page
// ---------------------------------------------------------------------------

export function RulesPage() {
  const queryClient = useQueryClient();
  const canUpdate = usePermission("rules", "update");
  const [savingServiceType, setSavingServiceType] = useState<string | null>(null);

  // ---- Queries ----
  const {
    data: rules,
    isLoading: rulesLoading,
    error: rulesError,
  } = useQuery({
    queryKey: ["assignment-rules"],
    queryFn: () => api.get<AssignmentRule[]>("/rules/assignment"),
  });

  const { data: teamMembers } = useQuery({
    queryKey: ["team-members", "all"],
    queryFn: () =>
      api.get<{ items: TeamMember[]; total: number }>("/team-members?per_page=200").then((r) => r.items),
  });

  // ---- Derived data ----
  const activeMembers = useMemo(
    () => (teamMembers ?? []).filter((m) => m.active),
    [teamMembers]
  );

  const memberMap = useMemo(() => {
    const map = new Map<string, string>();
    if (teamMembers) {
      for (const m of teamMembers) {
        map.set(m.id, m.name);
      }
    }
    return map;
  }, [teamMembers]);

  // ---- Mutation ----
  const updateMutation = useMutation({
    mutationFn: ({
      serviceType,
      update,
    }: {
      serviceType: string;
      update: AssignmentRuleUpdate;
    }) =>
      api.put<AssignmentRule>(
        `/rules/assignment/${encodeURIComponent(serviceType)}`,
        update
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["assignment-rules"] });
      toast.success("Regra atualizada com sucesso.");
      setSavingServiceType(null);
    },
    onError: (err: Error) => {
      toast.error(`Erro ao atualizar regra: ${err.message}`);
      setSavingServiceType(null);
    },
  });

  // ---- Handlers ----
  function handleSave(serviceType: string, update: AssignmentRuleUpdate) {
    setSavingServiceType(serviceType);
    updateMutation.mutate({ serviceType, update });
  }

  // ---- Render ----
  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">
          Regras de Atribuição
        </h1>
        <p className="mt-1 text-muted-foreground">
          Configuração das regras de atribuição de tarefas por tipo de serviço.
        </p>
      </div>

      {/* Error state */}
      {rulesError && (
        <div
          role="alert"
          className="rounded-lg border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm text-destructive"
        >
          {rulesError instanceof Error
            ? rulesError.message
            : "Erro ao carregar regras de atribuição."}
        </div>
      )}

      {/* Loading */}
      {rulesLoading && <RulesLoadingSkeleton />}

      {/* Empty state */}
      {!rulesLoading && !rulesError && rules && rules.length === 0 && (
        <p className="py-12 text-center text-muted-foreground">
          Nenhuma regra de atribuição encontrada.
        </p>
      )}

      {/* Rule cards */}
      {!rulesLoading && rules && rules.length > 0 && (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {rules.map((rule) => (
            <AssignmentRuleCard
              key={rule.id}
              rule={rule}
              members={activeMembers}
              memberMap={memberMap}
              onSave={handleSave}
              isSaving={savingServiceType === rule.service_type}
              disabled={!canUpdate}
            />
          ))}
        </div>
      )}
    </div>
  );
}
