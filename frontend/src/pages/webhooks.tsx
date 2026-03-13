import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Plus,
  Download,
  Send,
  ChevronDown,
  ChevronRight,
  CheckCircle2,
  XCircle,
  Loader2,
} from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { usePermission } from "@/lib/auth";
import { exportToCsv, csvFilename } from "@/lib/export";
import { DataTable, type ColumnDef, type SortingState } from "@/components/data-table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface WebhookLastDelivery {
  status_code: number | null;
  success: boolean;
  created_at: string;
}

interface Webhook {
  id: string;
  url: string;
  description: string | null;
  events: string[];
  secret: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  last_delivery: WebhookLastDelivery | null;
}

interface PaginatedWebhooks {
  items: Webhook[];
  total: number;
  page: number;
  per_page: number;
}

interface WebhookDelivery {
  id: string;
  event: string;
  payload: Record<string, unknown>;
  status_code: number | null;
  response_body: string | null;
  error: string | null;
  duration_ms: number | null;
  success: boolean;
  created_at: string;
}

interface PaginatedDeliveries {
  items: WebhookDelivery[];
  total: number;
  page: number;
  per_page: number;
}

interface WebhookCreate {
  url: string;
  description?: string | null;
  events: string[];
  secret?: string | null;
  is_active?: boolean;
}

interface WebhookUpdate {
  url?: string;
  description?: string | null;
  events?: string[];
  secret?: string | null;
  is_active?: boolean;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const WEBHOOK_EVENTS = [
  { value: "client_created", label: "Cliente criado" },
  { value: "client_updated", label: "Cliente atualizado" },
  { value: "client_deleted", label: "Cliente removido" },
  { value: "member_created", label: "Membro criado" },
  { value: "member_updated", label: "Membro atualizado" },
  { value: "approval_status_changed", label: "Status de aprovação alterado" },
  { value: "approval_comment_added", label: "Comentário de aprovação" },
] as const;

const EVENT_LABELS: Record<string, string> = Object.fromEntries(
  WEBHOOK_EVENTS.map((e) => [e.value, e.label])
);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatDate(iso: string): string {
  if (!iso) return "-";
  return new Date(iso).toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

// ---------------------------------------------------------------------------
// Webhook Form Dialog
// ---------------------------------------------------------------------------

interface WebhookFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  webhook: Webhook | null;
  onSubmit: (data: WebhookCreate | WebhookUpdate) => void;
  isPending: boolean;
}

function WebhookFormDialog({
  open,
  onOpenChange,
  webhook,
  onSubmit,
  isPending,
}: WebhookFormDialogProps) {
  const isEditing = webhook !== null;
  const [url, setUrl] = useState("");
  const [description, setDescription] = useState("");
  const [secret, setSecret] = useState("");
  const [selectedEvents, setSelectedEvents] = useState<string[]>([]);

  function handleOpenChange(next: boolean) {
    if (next && webhook) {
      setUrl(webhook.url);
      setDescription(webhook.description ?? "");
      setSecret("");
      setSelectedEvents(webhook.events);
    } else if (next) {
      setUrl("");
      setDescription("");
      setSecret("");
      setSelectedEvents([]);
    }
    onOpenChange(next);
  }

  function toggleEvent(value: string) {
    setSelectedEvents((prev) =>
      prev.includes(value) ? prev.filter((v) => v !== value) : [...prev, value]
    );
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (selectedEvents.length === 0) {
      toast.error("Selecione pelo menos um evento.");
      return;
    }

    if (isEditing) {
      const update: WebhookUpdate = {
        url: url || undefined,
        description: description || null,
        events: selectedEvents,
        secret: secret || undefined,
      };
      onSubmit(update);
    } else {
      const create: WebhookCreate = {
        url,
        description: description || null,
        events: selectedEvents,
        secret: secret || null,
      };
      onSubmit(create);
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>
            {isEditing ? "Editar Webhook" : "Adicionar Webhook"}
          </DialogTitle>
          <DialogDescription>
            {isEditing
              ? "Atualize a configuração do webhook."
              : "Configure um novo webhook para receber eventos."}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="webhook-url">URL *</Label>
            <Input
              id="webhook-url"
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://example.com/webhook"
              required
              autoFocus
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="webhook-description">Descrição</Label>
            <Input
              id="webhook-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Ex: Notificações Slack"
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="webhook-secret">Secret (HMAC)</Label>
            <Input
              id="webhook-secret"
              value={secret}
              onChange={(e) => setSecret(e.target.value)}
              placeholder={isEditing ? "Deixe vazio para manter" : "Opcional"}
              type="password"
            />
            <p className="text-xs text-muted-foreground">
              Usado para assinar payloads com HMAC-SHA256.
            </p>
          </div>

          <Separator />

          <div className="space-y-2">
            <Label>Eventos *</Label>
            <div className="grid grid-cols-1 gap-1.5">
              {WEBHOOK_EVENTS.map((event) => (
                <label
                  key={event.value}
                  className="flex cursor-pointer items-center gap-2 rounded-sm px-2 py-1.5 text-sm hover:bg-accent"
                >
                  <Checkbox
                    checked={selectedEvents.includes(event.value)}
                    onCheckedChange={() => toggleEvent(event.value)}
                  />
                  <span>{event.label}</span>
                  <span className="ml-auto text-xs text-muted-foreground font-mono">
                    {event.value}
                  </span>
                </label>
              ))}
            </div>
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
// Delete Confirmation Dialog
// ---------------------------------------------------------------------------

interface DeleteDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  webhookUrl: string;
  onConfirm: () => void;
  isPending: boolean;
}

function DeleteWebhookDialog({
  open,
  onOpenChange,
  webhookUrl,
  onConfirm,
  isPending,
}: DeleteDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Remover Webhook</DialogTitle>
          <DialogDescription>
            Tem certeza que deseja remover o webhook <strong className="break-all">{webhookUrl}</strong>?
            Todas as entregas serão removidas.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isPending}>
            Cancelar
          </Button>
          <Button variant="destructive" onClick={onConfirm} disabled={isPending}>
            {isPending ? "Removendo..." : "Remover"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Delivery Log Dialog
// ---------------------------------------------------------------------------

interface DeliveryLogDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  webhookId: string;
  webhookUrl: string;
}

function DeliveryLogDialog({ open, onOpenChange, webhookId, webhookUrl }: DeliveryLogDialogProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["webhook-deliveries", webhookId],
    queryFn: () => api.get<PaginatedDeliveries>(`/webhooks/${webhookId}/deliveries?per_page=50`),
    enabled: open,
  });

  const deliveries = data?.items ?? [];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl max-h-[80vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle>Entregas do Webhook</DialogTitle>
          <DialogDescription className="break-all">{webhookUrl}</DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto">
          {isLoading && (
            <div className="space-y-2 p-4">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          )}

          {!isLoading && deliveries.length === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">
              Nenhuma entrega registrada.
            </p>
          )}

          {!isLoading && deliveries.length > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-8" />
                  <TableHead>Evento</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Duração</TableHead>
                  <TableHead>Data</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {deliveries.map((delivery) => {
                  const isExpanded = expandedId === delivery.id;
                  return (
                    <DeliveryRow
                      key={delivery.id}
                      delivery={delivery}
                      isExpanded={isExpanded}
                      onToggle={() => setExpandedId(isExpanded ? null : delivery.id)}
                    />
                  );
                })}
              </TableBody>
            </Table>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

function DeliveryRow({
  delivery,
  isExpanded,
  onToggle,
}: {
  delivery: WebhookDelivery;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  return (
    <>
      <TableRow className="cursor-pointer" onClick={onToggle}>
        <TableCell>
          {isExpanded ? (
            <ChevronDown className="size-4 text-muted-foreground" />
          ) : (
            <ChevronRight className="size-4 text-muted-foreground" />
          )}
        </TableCell>
        <TableCell>
          <Badge variant="secondary" className="font-mono text-xs">
            {delivery.event}
          </Badge>
        </TableCell>
        <TableCell>
          {delivery.success ? (
            <Badge className="bg-emerald-600 text-white gap-1">
              <CheckCircle2 className="size-3" />
              {delivery.status_code}
            </Badge>
          ) : (
            <Badge variant="destructive" className="gap-1">
              <XCircle className="size-3" />
              {delivery.status_code ?? "Erro"}
            </Badge>
          )}
        </TableCell>
        <TableCell className="text-xs text-muted-foreground">
          {delivery.duration_ms != null ? `${delivery.duration_ms}ms` : "-"}
        </TableCell>
        <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
          {formatDate(delivery.created_at)}
        </TableCell>
      </TableRow>
      {isExpanded && (
        <TableRow>
          <TableCell colSpan={5} className="bg-muted/50 p-0">
            <div className="p-4 space-y-3">
              {delivery.error && (
                <div>
                  <p className="text-xs font-semibold text-destructive mb-1">Erro:</p>
                  <pre className="text-xs font-mono bg-destructive/10 p-2 rounded">{delivery.error}</pre>
                </div>
              )}
              <div>
                <p className="text-xs font-semibold text-muted-foreground mb-1">Payload:</p>
                <pre className="text-xs font-mono bg-background p-2 rounded overflow-x-auto max-h-40">
                  {JSON.stringify(delivery.payload, null, 2)}
                </pre>
              </div>
              {delivery.response_body && (
                <div>
                  <p className="text-xs font-semibold text-muted-foreground mb-1">Resposta:</p>
                  <pre className="text-xs font-mono bg-background p-2 rounded overflow-x-auto max-h-40">
                    {delivery.response_body}
                  </pre>
                </div>
              )}
            </div>
          </TableCell>
        </TableRow>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// Webhooks Page
// ---------------------------------------------------------------------------

export function WebhooksPage() {
  const queryClient = useQueryClient();
  const canCreate = usePermission("webhooks", "create");
  const canUpdate = usePermission("webhooks", "update");
  const [formOpen, setFormOpen] = useState(false);
  const [editingWebhook, setEditingWebhook] = useState<Webhook | null>(null);
  const [deletingWebhook, setDeletingWebhook] = useState<Webhook | null>(null);
  const [deliveryWebhook, setDeliveryWebhook] = useState<Webhook | null>(null);
  const [testingId, setTestingId] = useState<string | null>(null);

  // ---- Server-side table state ----
  const [pageIndex, setPageIndex] = useState(0);
  const [pageSize, setPageSize] = useState(10);
  const [sorting, setSorting] = useState<SortingState>([{ id: "created_at", desc: true }]);
  const [search, setSearch] = useState("");

  const sortBy = sorting[0]?.id ?? "created_at";
  const sortOrder = sorting[0]?.desc ? "desc" : "asc";

  // ---- Queries ----
  const {
    data: webhooksData,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["webhooks", { page: pageIndex + 1, per_page: pageSize, sort_by: sortBy, sort_order: sortOrder, search }],
    queryFn: () => {
      const params = new URLSearchParams();
      params.set("page", String(pageIndex + 1));
      params.set("per_page", String(pageSize));
      if (sortBy) params.set("sort_by", sortBy);
      params.set("sort_order", sortOrder);
      if (search) params.set("search", search);
      return api.get<PaginatedWebhooks>(`/webhooks?${params.toString()}`);
    },
  });

  const webhooks = webhooksData?.items ?? [];
  const totalRows = webhooksData?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(totalRows / pageSize));

  // ---- Columns ----
  const columns = useMemo<ColumnDef<Webhook, unknown>[]>(
    () => [
      {
        accessorKey: "url",
        header: "URL",
        cell: ({ getValue }) => (
          <span className="font-mono text-xs break-all max-w-[300px] block">
            {getValue() as string}
          </span>
        ),
      },
      {
        id: "events",
        header: "Eventos",
        enableSorting: false,
        cell: ({ row }) => {
          const events = row.original.events;
          return (
            <div className="flex flex-wrap gap-1">
              {events.length <= 2 ? (
                events.map((e) => (
                  <Badge key={e} variant="secondary" className="text-[10px]">
                    {EVENT_LABELS[e] ?? e}
                  </Badge>
                ))
              ) : (
                <Badge variant="secondary" className="text-[10px]">
                  {events.length} eventos
                </Badge>
              )}
            </div>
          );
        },
      },
      {
        accessorKey: "is_active",
        header: "Status",
        cell: ({ getValue }) => {
          const active = getValue() as boolean;
          return active ? (
            <Badge className="bg-emerald-600 hover:bg-emerald-600 text-white">Ativo</Badge>
          ) : (
            <Badge variant="secondary">Inativo</Badge>
          );
        },
      },
      {
        id: "last_delivery",
        header: "Última Entrega",
        enableSorting: false,
        cell: ({ row }) => {
          const ld = row.original.last_delivery;
          if (!ld) return <span className="text-muted-foreground text-xs">-</span>;
          return (
            <div className="flex items-center gap-1.5">
              {ld.success ? (
                <CheckCircle2 className="size-3.5 text-emerald-600" />
              ) : (
                <XCircle className="size-3.5 text-destructive" />
              )}
              <span className="text-xs text-muted-foreground">
                {ld.status_code ?? "Erro"} &middot; {formatDate(ld.created_at)}
              </span>
            </div>
          );
        },
      },
      {
        accessorKey: "created_at",
        header: "Criado em",
        cell: ({ getValue }) => (
          <span className="text-xs text-muted-foreground whitespace-nowrap">
            {formatDate(getValue() as string)}
          </span>
        ),
      },
      {
        id: "actions",
        header: "",
        enableSorting: false,
        size: 140,
        cell: ({ row }) => {
          const webhook = row.original;
          const isTesting = testingId === webhook.id;
          return (
            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="sm"
                className="h-7 text-xs"
                onClick={(e) => { e.stopPropagation(); setDeliveryWebhook(webhook); }}
              >
                Entregas
              </Button>
              <Button
                variant="ghost"
                size="icon-xs"
                onClick={(e) => { e.stopPropagation(); handleTest(webhook.id); }}
                disabled={isTesting}
                aria-label="Enviar teste"
              >
                {isTesting ? (
                  <Loader2 className="size-3.5 animate-spin" />
                ) : (
                  <Send className="size-3.5" />
                )}
              </Button>
            </div>
          );
        },
      },
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [testingId]
  );

  // ---- Mutations ----
  const createMutation = useMutation({
    mutationFn: (data: WebhookCreate) => api.post<Webhook>("/webhooks", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["webhooks"] });
      toast.success("Webhook criado com sucesso.");
      setFormOpen(false);
    },
    onError: (err: Error) => toast.error(`Erro ao criar webhook: ${err.message}`),
  });

  const updateMutation = useMutation({
    mutationFn: (data: WebhookUpdate & { id: string }) => {
      const { id, ...body } = data;
      return api.put<Webhook>(`/webhooks/${id}`, body);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["webhooks"] });
      toast.success("Webhook atualizado com sucesso.");
      setFormOpen(false);
      setEditingWebhook(null);
    },
    onError: (err: Error) => toast.error(`Erro ao atualizar webhook: ${err.message}`),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete<{ message: string }>(`/webhooks/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["webhooks"] });
      toast.success("Webhook removido com sucesso.");
      setDeletingWebhook(null);
    },
    onError: (err: Error) => toast.error(`Erro ao remover webhook: ${err.message}`),
  });

  // ---- Handlers ----
  function handleAdd() {
    setEditingWebhook(null);
    setFormOpen(true);
  }

  function handleFormSubmit(data: WebhookCreate | WebhookUpdate) {
    if (editingWebhook) {
      updateMutation.mutate({ ...data, id: editingWebhook.id });
    } else {
      createMutation.mutate(data as WebhookCreate);
    }
  }

  function handleDeleteConfirm() {
    if (deletingWebhook) {
      deleteMutation.mutate(deletingWebhook.id);
    }
  }

  async function handleTest(webhookId: string) {
    setTestingId(webhookId);
    try {
      await api.post(`/webhooks/${webhookId}/test`, {});
      toast.success("Teste enviado com sucesso.");
      queryClient.invalidateQueries({ queryKey: ["webhooks"] });
      queryClient.invalidateQueries({ queryKey: ["webhook-deliveries", webhookId] });
    } catch (err) {
      toast.error(`Erro no teste: ${err instanceof Error ? err.message : "erro desconhecido"}`);
    } finally {
      setTestingId(null);
    }
  }

  function handleRowClick(webhook: Webhook) {
    setEditingWebhook(webhook);
    setFormOpen(true);
  }

  const isMutating = createMutation.isPending || updateMutation.isPending;

  // ---- Render ----
  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Webhooks</h1>
          <p className="mt-1 text-muted-foreground">
            Gerencie webhooks para integrações externas.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {totalRows > 0 && (
            <Button
              variant="outline"
              onClick={() =>
                exportToCsv(
                  webhooks,
                  [
                    { header: "URL", accessor: (w) => w.url },
                    { header: "Descrição", accessor: (w) => w.description },
                    { header: "Eventos", accessor: (w) => w.events.join(", ") },
                    { header: "Ativo", accessor: (w) => (w.is_active ? "Sim" : "Não") },
                    { header: "Criado em", accessor: (w) => formatDate(w.created_at) },
                  ],
                  csvFilename("webhooks")
                )
              }
            >
              <Download aria-hidden="true" />
              Exportar CSV
            </Button>
          )}
          {canCreate && (
            <Button onClick={handleAdd}>
              <Plus aria-hidden="true" />
              Adicionar Webhook
            </Button>
          )}
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div
          role="alert"
          className="rounded-lg border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm text-destructive"
        >
          {error instanceof Error ? error.message : "Erro ao carregar webhooks."}
        </div>
      )}

      {/* Data table */}
      <DataTable
        columns={columns}
        data={webhooks}
        manualPagination
        manualSorting
        pageCount={pageCount}
        pageIndex={pageIndex}
        pageSize={pageSize}
        onPaginationChange={({ pageIndex: pi, pageSize: ps }) => {
          setPageIndex(pi);
          setPageSize(ps);
        }}
        sorting={sorting}
        onSortingChange={setSorting}
        searchValue={search}
        onSearchChange={(v) => { setSearch(v); setPageIndex(0); }}
        searchPlaceholder="Buscar webhooks..."
        isLoading={isLoading}
        emptyMessage="Nenhum webhook configurado."
        totalRows={totalRows}
        onRowClick={canUpdate ? handleRowClick : undefined}
      />

      {/* Form dialog */}
      <WebhookFormDialog
        open={formOpen}
        onOpenChange={(open) => {
          setFormOpen(open);
          if (!open) setEditingWebhook(null);
        }}
        webhook={editingWebhook}
        onSubmit={handleFormSubmit}
        isPending={isMutating}
      />

      {/* Delete confirmation */}
      <DeleteWebhookDialog
        open={deletingWebhook !== null}
        onOpenChange={(open) => { if (!open) setDeletingWebhook(null); }}
        webhookUrl={deletingWebhook?.url ?? ""}
        onConfirm={handleDeleteConfirm}
        isPending={deleteMutation.isPending}
      />

      {/* Delivery log */}
      {deliveryWebhook && (
        <DeliveryLogDialog
          open={deliveryWebhook !== null}
          onOpenChange={(open) => { if (!open) setDeliveryWebhook(null); }}
          webhookId={deliveryWebhook.id}
          webhookUrl={deliveryWebhook.url}
        />
      )}
    </div>
  );
}
