import { useState, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { usePermission } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface NotificationRule {
  id: string;
  status: string;
  notify_roles: string[];
  message_template: string;
  is_active: boolean;
}

interface NotificationRuleCreate {
  status: string;
  notify_roles: string[];
  message_template: string;
  is_active?: boolean;
}

interface NotificationRuleUpdate {
  notify_roles?: string[];
  message_template?: string;
  is_active?: boolean;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const ROLES = [
  { value: "admin", label: "Admin" },
  { value: "strategy_reviewer", label: "Revisor de Estratégia" },
  { value: "content_reviewer", label: "Revisor de Conteúdo" },
  { value: "designer", label: "Designer" },
  { value: "account", label: "Atendimento" },
  { value: "ads", label: "Ads/Performance" },
  { value: "video", label: "Vídeo" },
] as const;

const ROLE_LABELS: Record<string, string> = Object.fromEntries(
  ROLES.map((r) => [r.value, r.label])
);

// ---------------------------------------------------------------------------
// Role Toggle List
// ---------------------------------------------------------------------------

interface RoleToggleListProps {
  selected: string[];
  onChange: (roles: string[]) => void;
}

function RoleToggleList({ selected, onChange }: RoleToggleListProps) {
  const toggle = useCallback(
    (role: string) => {
      if (selected.includes(role)) {
        onChange(selected.filter((r) => r !== role));
      } else {
        onChange([...selected, role]);
      }
    },
    [selected, onChange]
  );

  return (
    <div className="flex flex-wrap gap-2">
      {ROLES.map((role) => {
        const isSelected = selected.includes(role.value);
        return (
          <button
            key={role.value}
            type="button"
            onClick={() => toggle(role.value)}
            className={
              "inline-flex items-center rounded-full border px-3 py-1 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring " +
              (isSelected
                ? "border-primary bg-primary text-primary-foreground"
                : "border-border bg-background text-foreground hover:bg-accent")
            }
            aria-pressed={isSelected}
          >
            {role.label}
          </button>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Notification Rule Form Dialog
// ---------------------------------------------------------------------------

interface RuleFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  rule: NotificationRule | null;
  onSubmit: (data: NotificationRuleCreate | NotificationRuleUpdate) => void;
  isPending: boolean;
}

function RuleFormDialog({
  open,
  onOpenChange,
  rule,
  onSubmit,
  isPending,
}: RuleFormDialogProps) {
  const isEditing = rule !== null;
  const [status, setStatus] = useState("");
  const [notifyRoles, setNotifyRoles] = useState<string[]>([]);
  const [messageTemplate, setMessageTemplate] = useState("");
  const [isActive, setIsActive] = useState(true);

  function handleOpenChange(next: boolean) {
    if (next && rule) {
      setStatus(rule.status);
      setNotifyRoles([...rule.notify_roles]);
      setMessageTemplate(rule.message_template);
      setIsActive(rule.is_active);
    } else if (next) {
      setStatus("");
      setNotifyRoles([]);
      setMessageTemplate("");
      setIsActive(true);
    }
    onOpenChange(next);
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    if (isEditing) {
      const update: NotificationRuleUpdate = {
        notify_roles: notifyRoles,
        message_template: messageTemplate,
        is_active: isActive,
      };
      onSubmit(update);
    } else {
      const create: NotificationRuleCreate = {
        status,
        notify_roles: notifyRoles,
        message_template: messageTemplate,
        is_active: isActive,
      };
      onSubmit(create);
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {isEditing ? "Editar Regra de Notificação" : "Adicionar Regra de Notificação"}
          </DialogTitle>
          <DialogDescription>
            {isEditing
              ? "Atualize as configurações da regra de notificação."
              : "Preencha os dados para criar uma nova regra de notificação."}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="rule-status">Status *</Label>
            <Input
              id="rule-status"
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              placeholder="Ex: revisão, alteração, aprovado"
              required
              disabled={isEditing}
              autoFocus={!isEditing}
              aria-describedby={isEditing ? "status-hint" : undefined}
            />
            {isEditing && (
              <p id="status-hint" className="text-xs text-muted-foreground">
                O status não pode ser alterado.
              </p>
            )}
          </div>

          <div className="space-y-2">
            <Label>Roles Notificados</Label>
            <RoleToggleList selected={notifyRoles} onChange={setNotifyRoles} />
          </div>

          <div className="space-y-2">
            <Label htmlFor="rule-template">Template de Mensagem *</Label>
            <Textarea
              id="rule-template"
              value={messageTemplate}
              onChange={(e) => setMessageTemplate(e.target.value)}
              placeholder="Ex: A tarefa precisa de revisão"
              required
              rows={3}
            />
          </div>

          <div className="flex items-center gap-3">
            <Switch
              id="rule-active"
              checked={isActive}
              onCheckedChange={setIsActive}
            />
            <Label htmlFor="rule-active">Ativa</Label>
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
              {isPending ? "Salvando..." : isEditing ? "Salvar" : "Adicionar"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Loading Skeleton
// ---------------------------------------------------------------------------

function NotificationsTableSkeleton() {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Status</TableHead>
          <TableHead>Roles Notificados</TableHead>
          <TableHead>Template de Mensagem</TableHead>
          <TableHead>Ativo</TableHead>
          <TableHead className="w-16">
            <span className="sr-only">Ações</span>
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {Array.from({ length: 4 }).map((_, i) => (
          <TableRow key={i}>
            <TableCell><Skeleton className="h-5 w-20 rounded-full" /></TableCell>
            <TableCell>
              <div className="flex gap-1">
                <Skeleton className="h-5 w-24 rounded-full" />
                <Skeleton className="h-5 w-20 rounded-full" />
              </div>
            </TableCell>
            <TableCell><Skeleton className="h-4 w-48" /></TableCell>
            <TableCell><Skeleton className="h-5 w-8" /></TableCell>
            <TableCell><Skeleton className="h-8 w-8" /></TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

// ---------------------------------------------------------------------------
// Notifications Page
// ---------------------------------------------------------------------------

export function NotificationsPage() {
  const queryClient = useQueryClient();
  const canCreate = usePermission("notifications", "create");
  const canUpdate = usePermission("notifications", "update");
  const [formOpen, setFormOpen] = useState(false);
  const [editingRule, setEditingRule] = useState<NotificationRule | null>(null);

  // ---- Queries ----
  const {
    data: rules,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["notification-rules"],
    queryFn: () => api.get<NotificationRule[]>("/rules/notification"),
  });

  // ---- Mutations ----
  const createMutation = useMutation({
    mutationFn: (data: NotificationRuleCreate) =>
      api.post<NotificationRule>("/rules/notification", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notification-rules"] });
      toast.success("Regra criada com sucesso.");
      setFormOpen(false);
    },
    onError: (err: Error) => {
      toast.error(`Erro ao criar regra: ${err.message}`);
    },
  });

  const updateMutation = useMutation({
    mutationFn: (data: NotificationRuleUpdate & { status: string }) => {
      const { status, ...body } = data;
      return api.put<NotificationRule>(
        `/rules/notification/${encodeURIComponent(status)}`,
        body
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notification-rules"] });
      toast.success("Regra atualizada com sucesso.");
      setFormOpen(false);
      setEditingRule(null);
    },
    onError: (err: Error) => {
      toast.error(`Erro ao atualizar regra: ${err.message}`);
    },
  });

  const toggleActiveMutation = useMutation({
    mutationFn: ({
      status,
      is_active,
    }: {
      status: string;
      is_active: boolean;
    }) =>
      api.put<NotificationRule>(
        `/rules/notification/${encodeURIComponent(status)}`,
        { is_active }
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notification-rules"] });
      toast.success("Status atualizado com sucesso.");
    },
    onError: (err: Error) => {
      toast.error(`Erro ao atualizar status: ${err.message}`);
    },
  });

  // ---- Handlers ----
  function handleAdd() {
    setEditingRule(null);
    setFormOpen(true);
  }

  function handleEdit(rule: NotificationRule) {
    setEditingRule(rule);
    setFormOpen(true);
  }

  function handleFormSubmit(data: NotificationRuleCreate | NotificationRuleUpdate) {
    if (editingRule) {
      updateMutation.mutate({ ...data, status: editingRule.status });
    } else {
      createMutation.mutate(data as NotificationRuleCreate);
    }
  }

  function handleToggleActive(rule: NotificationRule) {
    toggleActiveMutation.mutate({
      status: rule.status,
      is_active: !rule.is_active,
    });
  }

  const isMutating = createMutation.isPending || updateMutation.isPending;

  // ---- Render ----
  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">
            Regras de Notificação
          </h1>
          <p className="mt-1 text-muted-foreground">
            Configuração das regras de notificação por status de tarefa.
          </p>
        </div>
        {canCreate && (
          <Button onClick={handleAdd}>
            <Plus aria-hidden="true" />
            Adicionar Regra
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
            : "Erro ao carregar regras de notificação."}
        </div>
      )}

      {/* Loading */}
      {isLoading && <NotificationsTableSkeleton />}

      {/* Empty state */}
      {!isLoading && !error && rules && rules.length === 0 && (
        <p className="py-12 text-center text-muted-foreground">
          Nenhuma regra de notificação encontrada.
        </p>
      )}

      {/* Data table */}
      {!isLoading && rules && rules.length > 0 && (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Status</TableHead>
              <TableHead>Roles Notificados</TableHead>
              <TableHead>Template de Mensagem</TableHead>
              <TableHead>Ativo</TableHead>
              {canUpdate && (
                <TableHead className="w-16">
                  <span className="sr-only">Ações</span>
                </TableHead>
              )}
            </TableRow>
          </TableHeader>
          <TableBody>
            {rules.map((rule) => (
              <TableRow key={rule.id}>
                <TableCell>
                  <Badge variant="secondary">{rule.status}</Badge>
                </TableCell>
                <TableCell>
                  <div className="flex flex-wrap gap-1">
                    {rule.notify_roles.length > 0 ? (
                      rule.notify_roles.map((role) => (
                        <Badge key={role} variant="outline" className="text-xs">
                          {ROLE_LABELS[role] ?? role}
                        </Badge>
                      ))
                    ) : (
                      <span className="text-muted-foreground">-</span>
                    )}
                  </div>
                </TableCell>
                <TableCell className="max-w-xs truncate text-sm">
                  {rule.message_template || "-"}
                </TableCell>
                <TableCell>
                  <Switch
                    checked={rule.is_active}
                    onCheckedChange={() => handleToggleActive(rule)}
                    aria-label={`${rule.is_active ? "Desativar" : "Ativar"} regra para ${rule.status}`}
                    disabled={!canUpdate}
                  />
                </TableCell>
                {canUpdate && (
                  <TableCell>
                    <Button
                      variant="ghost"
                      size="icon-xs"
                      onClick={() => handleEdit(rule)}
                      aria-label={`Editar regra para ${rule.status}`}
                    >
                      <Pencil aria-hidden="true" />
                    </Button>
                  </TableCell>
                )}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      {/* Form dialog */}
      <RuleFormDialog
        open={formOpen}
        onOpenChange={(open) => {
          setFormOpen(open);
          if (!open) setEditingRule(null);
        }}
        rule={editingRule}
        onSubmit={handleFormSubmit}
        isPending={isMutating}
      />
    </div>
  );
}
