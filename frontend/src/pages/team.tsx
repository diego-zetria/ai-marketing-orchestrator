import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Pencil, Trash2, Plus, Download } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { usePermission } from "@/lib/auth";
import { exportToCsv, csvFilename } from "@/lib/export";
import { DataTable, type ColumnDef, type SortingState } from "@/components/data-table";
import { DataTableFilters, type ActiveFilters, type FilterDefinition } from "@/components/data-table-filters";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface TeamMember {
  id: string;
  clickup_user_id: string | null;
  name: string;
  role: string | null;
  telegram_chat_id: number;
  active: boolean;
}

interface TeamMemberCreate {
  clickup_user_id: string;
  name: string;
  role?: string | null;
  telegram_chat_id?: number;
}

interface TeamMemberUpdate {
  name?: string | null;
  role?: string | null;
  telegram_chat_id?: number | null;
  active?: boolean | null;
}

interface PaginatedTeamMembers {
  items: TeamMember[];
  total: number;
  page: number;
  per_page: number;
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

const NONE_SENTINEL = "__none__";

// ---------------------------------------------------------------------------
// Member Form Dialog
// ---------------------------------------------------------------------------

interface MemberFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  member: TeamMember | null;
  onSubmit: (data: TeamMemberCreate | TeamMemberUpdate) => void;
  isPending: boolean;
}

function MemberFormDialog({
  open,
  onOpenChange,
  member,
  onSubmit,
  isPending,
}: MemberFormDialogProps) {
  const isEditing = member !== null;
  const [name, setName] = useState("");
  const [clickupUserId, setClickupUserId] = useState("");
  const [role, setRole] = useState<string>(NONE_SENTINEL);
  const [telegramChatId, setTelegramChatId] = useState("");

  function handleOpenChange(next: boolean) {
    if (next && member) {
      setName(member.name);
      setClickupUserId(member.clickup_user_id ?? "");
      setRole(member.role ?? NONE_SENTINEL);
      setTelegramChatId(member.telegram_chat_id ? String(member.telegram_chat_id) : "");
    } else if (next) {
      setName("");
      setClickupUserId("");
      setRole(NONE_SENTINEL);
      setTelegramChatId("");
    }
    onOpenChange(next);
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    const roleValue = role === NONE_SENTINEL ? null : role;

    if (isEditing) {
      const update: TeamMemberUpdate = {
        name: name || null,
        role: roleValue,
        telegram_chat_id: telegramChatId ? Number(telegramChatId) : null,
      };
      onSubmit(update);
    } else {
      const create: TeamMemberCreate = {
        name,
        clickup_user_id: clickupUserId,
        role: roleValue,
        telegram_chat_id: telegramChatId ? Number(telegramChatId) : undefined,
      };
      onSubmit(create);
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {isEditing ? "Editar Membro" : "Adicionar Membro"}
          </DialogTitle>
          <DialogDescription>
            {isEditing
              ? "Atualize as informações do membro da equipe."
              : "Preencha os dados para adicionar um novo membro."}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="member-name">Nome *</Label>
            <Input
              id="member-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Nome do membro"
              required
              autoFocus
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="member-clickup-id">ClickUp User ID *</Label>
            <Input
              id="member-clickup-id"
              value={clickupUserId}
              onChange={(e) => setClickupUserId(e.target.value)}
              placeholder="Ex: 89317548"
              required={!isEditing}
              disabled={isEditing}
              aria-describedby={isEditing ? "clickup-id-hint" : undefined}
            />
            {isEditing && (
              <p id="clickup-id-hint" className="text-xs text-muted-foreground">
                O ClickUp User ID não pode ser alterado.
              </p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="member-role">Cargo</Label>
            <Select value={role} onValueChange={setRole}>
              <SelectTrigger id="member-role" className="w-full">
                <SelectValue placeholder="Selecione um cargo" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={NONE_SENTINEL}>Nenhum</SelectItem>
                {ROLES.map((r) => (
                  <SelectItem key={r.value} value={r.value}>
                    {r.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="member-telegram-id">Telegram Chat ID</Label>
            <Input
              id="member-telegram-id"
              type="number"
              value={telegramChatId}
              onChange={(e) => setTelegramChatId(e.target.value)}
              placeholder="Ex: 123456789"
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
  memberName: string;
  onConfirm: () => void;
  isPending: boolean;
}

function DeleteMemberDialog({
  open,
  onOpenChange,
  memberName,
  onConfirm,
  isPending,
}: DeleteDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Remover Membro</DialogTitle>
          <DialogDescription>
            Tem certeza que deseja remover <strong>{memberName}</strong>? Essa
            ação não pode ser desfeita.
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
            {isPending ? "Removendo..." : "Remover"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Team Page
// ---------------------------------------------------------------------------

export function TeamPage() {
  const queryClient = useQueryClient();
  const canCreate = usePermission("team", "create");
  const canUpdate = usePermission("team", "update");
  const canDelete = usePermission("team", "delete");
  const [formOpen, setFormOpen] = useState(false);
  const [editingMember, setEditingMember] = useState<TeamMember | null>(null);
  const [deletingMember, setDeletingMember] = useState<TeamMember | null>(null);

  // ---- Server-side table state ----
  const [pageIndex, setPageIndex] = useState(0);
  const [pageSize, setPageSize] = useState(10);
  const [sorting, setSorting] = useState<SortingState>([]);
  const [search, setSearch] = useState("");
  const [activeFilters, setActiveFilters] = useState<ActiveFilters>({});

  const sortBy = sorting[0]?.id ?? "name";
  const sortOrder = sorting[0]?.desc ? "desc" : "asc";

  // ---- Filter definitions ----
  const filterDefs: FilterDefinition[] = [
    {
      id: "role",
      label: "Cargo",
      options: ROLES.map((r) => ({ value: r.value, label: r.label })),
    },
    {
      id: "active",
      label: "Status",
      options: [
        { value: "true", label: "Ativo" },
        { value: "false", label: "Inativo" },
      ],
    },
  ];

  function handleFiltersChange(filters: ActiveFilters) {
    setActiveFilters(filters);
    setPageIndex(0);
  }

  // ---- Queries ----
  const {
    data: membersData,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["team-members", { page: pageIndex + 1, per_page: pageSize, sort_by: sortBy, sort_order: sortOrder, search, filters: activeFilters }],
    queryFn: () => {
      const params = new URLSearchParams();
      params.set("page", String(pageIndex + 1));
      params.set("per_page", String(pageSize));
      if (sortBy) params.set("sort_by", sortBy);
      params.set("sort_order", sortOrder);
      if (search) params.set("search", search);
      // Filters
      if (activeFilters.role?.length) {
        for (const v of activeFilters.role) params.append("role", v);
      }
      if (activeFilters.active?.length) {
        params.set("active", activeFilters.active[0]);
      }
      return api.get<PaginatedTeamMembers>(`/team-members?${params.toString()}`);
    },
  });

  const members = membersData?.items ?? [];
  const totalRows = membersData?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(totalRows / pageSize));

  // ---- Columns ----
  const columns: ColumnDef<TeamMember, unknown>[] = [
    {
      accessorKey: "name",
      header: "Nome",
      cell: ({ getValue }) => (
        <span className="font-medium">{getValue() as string}</span>
      ),
    },
    {
      id: "clickup_user_id",
      header: "ClickUp ID",
      enableSorting: false,
      cell: ({ row }) => (
        <span className="font-mono text-xs">
          {row.original.clickup_user_id ?? "-"}
        </span>
      ),
    },
    {
      id: "telegram_chat_id",
      header: "Telegram Chat ID",
      enableSorting: false,
      cell: ({ row }) => (
        <span className="font-mono text-xs">
          {row.original.telegram_chat_id || "-"}
        </span>
      ),
    },
    {
      accessorKey: "role",
      header: "Cargo",
      cell: ({ getValue }) => {
        const role = getValue() as string | null;
        return role ? (
          <Badge variant="secondary">
            {ROLE_LABELS[role] ?? role}
          </Badge>
        ) : (
          <span className="text-muted-foreground">-</span>
        );
      },
    },
    {
      accessorKey: "active",
      header: "Ativo",
      cell: ({ getValue }) => {
        const active = getValue() as boolean;
        return active ? (
          <Badge className="bg-emerald-600 hover:bg-emerald-600 text-white">Ativo</Badge>
        ) : (
          <Badge variant="destructive">Inativo</Badge>
        );
      },
    },
    ...((canUpdate || canDelete) ? [{
      id: "actions",
      header: "",
      enableSorting: false,
      size: 80,
      cell: ({ row }: { row: { original: TeamMember } }) => {
        const member = row.original;
        return (
          <div className="flex items-center gap-1">
            {canUpdate && (
              <Button
                variant="ghost"
                size="icon-xs"
                onClick={() => handleEdit(member)}
                aria-label={`Editar ${member.name}`}
              >
                <Pencil aria-hidden="true" />
              </Button>
            )}
            {canDelete && (
              <Button
                variant="ghost"
                size="icon-xs"
                onClick={() => setDeletingMember(member)}
                aria-label={`Remover ${member.name}`}
              >
                <Trash2 className="text-destructive" aria-hidden="true" />
              </Button>
            )}
          </div>
        );
      },
    }] as ColumnDef<TeamMember, unknown>[] : []),
  ];

  // ---- Mutations ----
  const createMutation = useMutation({
    mutationFn: (data: TeamMemberCreate) =>
      api.post<TeamMember>("/team-members", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["team-members"] });
      toast.success("Membro adicionado com sucesso.");
      setFormOpen(false);
    },
    onError: (err: Error) => {
      toast.error(`Erro ao adicionar membro: ${err.message}`);
    },
  });

  const updateMutation = useMutation({
    mutationFn: (data: TeamMemberUpdate & { id: string }) => {
      const { id, ...body } = data;
      return api.put<TeamMember>(`/team-members/${id}`, body);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["team-members"] });
      toast.success("Membro atualizado com sucesso.");
      setFormOpen(false);
      setEditingMember(null);
    },
    onError: (err: Error) => {
      toast.error(`Erro ao atualizar membro: ${err.message}`);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) =>
      api.delete<{ message: string }>(`/team-members/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["team-members"] });
      toast.success("Membro removido com sucesso.");
      setDeletingMember(null);
    },
    onError: (err: Error) => {
      toast.error(`Erro ao remover membro: ${err.message}`);
    },
  });

  // ---- Handlers ----
  function handleAdd() {
    setEditingMember(null);
    setFormOpen(true);
  }

  function handleEdit(member: TeamMember) {
    setEditingMember(member);
    setFormOpen(true);
  }

  function handleFormSubmit(data: TeamMemberCreate | TeamMemberUpdate) {
    if (editingMember) {
      updateMutation.mutate({ ...data, id: editingMember.id });
    } else {
      createMutation.mutate(data as TeamMemberCreate);
    }
  }

  function handleDeleteConfirm() {
    if (deletingMember) {
      deleteMutation.mutate(deletingMember.id);
    }
  }

  const isMutating = createMutation.isPending || updateMutation.isPending;

  // ---- Render ----
  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Equipe</h1>
          <p className="mt-1 text-muted-foreground">
            Gerenciamento dos membros da equipe.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {totalRows > 0 && (
            <Button
              variant="outline"
              onClick={() =>
                exportToCsv(
                  members,
                  [
                    { header: "Nome", accessor: (m) => m.name },
                    { header: "ClickUp ID", accessor: (m) => m.clickup_user_id },
                    { header: "Telegram Chat ID", accessor: (m) => m.telegram_chat_id },
                    { header: "Cargo", accessor: (m) => (m.role ? (ROLE_LABELS[m.role] ?? m.role) : "") },
                    { header: "Ativo", accessor: (m) => (m.active ? "Sim" : "Não") },
                  ],
                  csvFilename("equipe")
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
              Adicionar Membro
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
          {error instanceof Error
            ? error.message
            : "Erro ao carregar membros da equipe."}
        </div>
      )}

      {/* Filters */}
      <DataTableFilters
        filters={filterDefs}
        activeFilters={activeFilters}
        onFiltersChange={handleFiltersChange}
      />

      {/* Data table */}
      <DataTable
        columns={columns}
        data={members}
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
        searchPlaceholder="Buscar membros..."
        isLoading={isLoading}
        emptyMessage="Nenhum membro encontrado."
        totalRows={totalRows}
      />

      {/* Form dialog (add / edit) */}
      <MemberFormDialog
        open={formOpen}
        onOpenChange={(open) => {
          setFormOpen(open);
          if (!open) setEditingMember(null);
        }}
        member={editingMember}
        onSubmit={handleFormSubmit}
        isPending={isMutating}
      />

      {/* Delete confirmation */}
      <DeleteMemberDialog
        open={deletingMember !== null}
        onOpenChange={(open) => {
          if (!open) setDeletingMember(null);
        }}
        memberName={deletingMember?.name ?? ""}
        onConfirm={handleDeleteConfirm}
        isPending={deleteMutation.isPending}
      />
    </div>
  );
}
