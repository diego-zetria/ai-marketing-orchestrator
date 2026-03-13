import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { Eye, Download } from "lucide-react";
import { api } from "@/lib/api";
import { exportToCsv, csvFilename } from "@/lib/export";
import { DataTable, type ColumnDef, type SortingState } from "@/components/data-table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
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

interface ApprovalStats {
  total_assets: number;
  pending_review: number;
  approved: number;
  changes_requested: number;
}

interface ApprovalAsset {
  id: string;
  client_name: string;
  title: string;
  status: string;
  current_version: number;
  clickup_task_id: string;
  created_at: string;
  updated_at: string;
}

interface PaginatedApprovals {
  items: ApprovalAsset[];
  total: number;
  page: number;
  per_page: number;
}

interface Client {
  id: string;
  name: string;
  display_name: string;
  is_active: boolean;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const ALL_SENTINEL = "__all__";

const STATUS_CONFIG: Record<string, { label: string; variant: "default" | "secondary" | "destructive" | "outline" }> = {
  pending_review: { label: "Pendente", variant: "default" },
  approved: { label: "Aprovado", variant: "outline" },
  changes_requested: { label: "Alteração", variant: "destructive" },
  expired: { label: "Expirado", variant: "secondary" },
};

function StatusBadge({ status }: { status: string }) {
  const config = STATUS_CONFIG[status] ?? { label: status, variant: "secondary" as const };
  if (status === "approved") {
    return (
      <Badge className="bg-emerald-600 hover:bg-emerald-600 text-white">
        {config.label}
      </Badge>
    );
  }
  if (status === "pending_review") {
    return (
      <Badge className="bg-amber-500 hover:bg-amber-500 text-white">
        {config.label}
      </Badge>
    );
  }
  return <Badge variant={config.variant}>{config.label}</Badge>;
}

// ---------------------------------------------------------------------------
// Approvals Page
// ---------------------------------------------------------------------------

export function ApprovalsPage() {
  const navigate = useNavigate();
  const [statusFilter, setStatusFilter] = useState(ALL_SENTINEL);
  const [clientFilter, setClientFilter] = useState(ALL_SENTINEL);
  const [search, setSearch] = useState("");

  // ---- Server-side table state ----
  const [pageIndex, setPageIndex] = useState(0);
  const [pageSize, setPageSize] = useState(10);
  const [sorting, setSorting] = useState<SortingState>([{ id: "created_at", desc: true }]);

  const sortBy = sorting[0]?.id ?? "created_at";
  const sortOrder = sorting[0]?.desc ? "desc" : "asc";

  // ---- Queries ----
  const { data: stats } = useQuery({
    queryKey: ["approvals", "stats"],
    queryFn: () => api.get<ApprovalStats>("/approvals/stats"),
  });

  const { data: clients } = useQuery({
    queryKey: ["clients"],
    queryFn: () =>
      api.get<{ items: Client[]; total: number }>("/clients?per_page=200").then((r) => r.items),
  });

  const statusParam = statusFilter === ALL_SENTINEL ? "" : statusFilter;
  const clientParam = clientFilter === ALL_SENTINEL ? "" : clientFilter;

  const {
    data: approvalsData,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["approvals", { status: statusParam, client_id: clientParam, search, page: pageIndex + 1, per_page: pageSize, sort_by: sortBy, sort_order: sortOrder }],
    queryFn: () => {
      const params = new URLSearchParams();
      params.set("page", String(pageIndex + 1));
      params.set("per_page", String(pageSize));
      if (statusParam) params.set("status", statusParam);
      if (clientParam) params.set("client_id", clientParam);
      if (search) params.set("search", search);
      if (sortBy) params.set("sort_by", sortBy);
      params.set("sort_order", sortOrder);
      return api.get<PaginatedApprovals>(`/approvals?${params.toString()}`);
    },
  });

  const assets = approvalsData?.items ?? [];
  const totalRows = approvalsData?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(totalRows / pageSize));

  function formatDate(iso: string): string {
    if (!iso) return "-";
    return new Date(iso).toLocaleDateString("pt-BR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    });
  }

  // ---- Columns ----
  const columns = useMemo<ColumnDef<ApprovalAsset, unknown>[]>(
    () => [
      {
        accessorKey: "client_name",
        header: "Cliente",
        enableSorting: false,
        cell: ({ getValue }) => (
          <span className="font-medium">{getValue() as string}</span>
        ),
      },
      {
        accessorKey: "title",
        header: "Título",
        cell: ({ getValue }) => getValue() as string,
      },
      {
        accessorKey: "status",
        header: "Status",
        cell: ({ getValue }) => <StatusBadge status={getValue() as string} />,
      },
      {
        id: "current_version",
        header: "Versão",
        enableSorting: false,
        cell: ({ row }) => `v${row.original.current_version}`,
      },
      {
        accessorKey: "created_at",
        header: "Criado em",
        cell: ({ getValue }) => formatDate(getValue() as string),
      },
      {
        id: "actions",
        header: "",
        enableSorting: false,
        size: 48,
        cell: ({ row }) => (
          <Button
            variant="ghost"
            size="icon-xs"
            onClick={(e) => {
              e.stopPropagation();
              navigate({ to: "/approvals/$assetId", params: { assetId: row.original.id } });
            }}
            aria-label={`Ver detalhe de ${row.original.title}`}
          >
            <Eye aria-hidden="true" />
          </Button>
        ),
      },
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []
  );

  // Reset page when filters change
  function handleStatusChange(value: string) {
    setStatusFilter(value);
    setPageIndex(0);
  }
  function handleClientChange(value: string) {
    setClientFilter(value);
    setPageIndex(0);
  }

  // ---- Render ----
  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Aprovações</h1>
          <p className="mt-1 text-muted-foreground">
            Gerencie os assets de aprovação dos clientes.
          </p>
        </div>
        {totalRows > 0 && (
          <Button
            variant="outline"
            onClick={() =>
              exportToCsv(
                assets,
                [
                  { header: "Cliente", accessor: (a) => a.client_name },
                  { header: "Título", accessor: (a) => a.title },
                  { header: "Status", accessor: (a) => (STATUS_CONFIG[a.status]?.label ?? a.status) },
                  { header: "Versão", accessor: (a) => a.current_version },
                  { header: "ClickUp Task", accessor: (a) => a.clickup_task_id },
                  { header: "Criado em", accessor: (a) => formatDate(a.created_at) },
                  { header: "Atualizado em", accessor: (a) => formatDate(a.updated_at) },
                ],
                csvFilename("approvals")
              )
            }
          >
            <Download aria-hidden="true" />
            Exportar CSV
          </Button>
        )}
      </div>

      {/* KPI Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Total</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.total_assets ?? 0}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Pendentes</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-amber-500">{stats?.pending_review ?? 0}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Aprovados</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-emerald-600">{stats?.approved ?? 0}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Alterações</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-destructive">{stats?.changes_requested ?? 0}</div>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <Select value={statusFilter} onValueChange={handleStatusChange}>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL_SENTINEL}>Todos os status</SelectItem>
            <SelectItem value="pending_review">Pendente</SelectItem>
            <SelectItem value="approved">Aprovado</SelectItem>
            <SelectItem value="changes_requested">Alteração</SelectItem>
            <SelectItem value="expired">Expirado</SelectItem>
          </SelectContent>
        </Select>

        <Select value={clientFilter} onValueChange={handleClientChange}>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="Cliente" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL_SENTINEL}>Todos os clientes</SelectItem>
            {(clients ?? []).map((c) => (
              <SelectItem key={c.id} value={c.id}>
                {c.display_name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Error state */}
      {error && (
        <div
          role="alert"
          className="rounded-lg border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm text-destructive"
        >
          {error instanceof Error
            ? error.message
            : "Erro ao carregar aprovações."}
        </div>
      )}

      {/* Data table */}
      <DataTable
        columns={columns}
        data={assets}
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
        searchPlaceholder="Buscar por título..."
        isLoading={isLoading}
        emptyMessage="Nenhuma aprovação encontrada."
        totalRows={totalRows}
      />
    </div>
  );
}
