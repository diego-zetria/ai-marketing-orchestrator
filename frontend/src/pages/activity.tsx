import { useState, useCallback, useRef, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, ChevronRight, ChevronLeft, ChevronUp, ChevronsUpDown, Download, Search } from "lucide-react";
import { api } from "@/lib/api";
import { exportToCsv, csvFilename } from "@/lib/export";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
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

interface ActivityLogEntry {
  id: string;
  action: string;
  entity_type: string | null;
  entity_id: string | null;
  details: Record<string, unknown> | null;
  user: string;
  created_at: string;
}

interface PaginatedResponse {
  items: ActivityLogEntry[];
  total: number;
  page: number;
  per_page: number;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const ENTITY_TYPES = [
  { value: "team_member", label: "Membro" },
  { value: "client", label: "Cliente" },
  { value: "assignment_rule", label: "Regra de Atribuição" },
  { value: "notification_rule", label: "Regra de Notificação" },
  { value: "agent_config", label: "Agente IA" },
  { value: "brand_guideline", label: "Diretriz de Marca" },
  { value: "system_config", label: "Config. Sistema" },
] as const;

const ENTITY_TYPE_LABELS: Record<string, string> = Object.fromEntries(
  ENTITY_TYPES.map((t) => [t.value, t.label])
);

const NONE_SENTINEL = "__all__";

const PER_PAGE = 20;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatDate(iso: string): string {
  const d = new Date(iso);
  const day = String(d.getDate()).padStart(2, "0");
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const year = d.getFullYear();
  const hours = String(d.getHours()).padStart(2, "0");
  const minutes = String(d.getMinutes()).padStart(2, "0");
  return `${day}/${month}/${year} ${hours}:${minutes}`;
}

function getEntityBadgeVariant(
  entityType: string | null
): "default" | "secondary" | "outline" | "destructive" {
  if (!entityType) return "outline";
  switch (entityType) {
    case "team_member":
    case "client":
      return "default";
    case "agent_config":
    case "brand_guideline":
      return "secondary";
    case "system_config":
      return "outline";
    default:
      return "secondary";
  }
}

// ---------------------------------------------------------------------------
// Expandable Row
// ---------------------------------------------------------------------------

interface ExpandableRowProps {
  entry: ActivityLogEntry;
  isExpanded: boolean;
  onToggle: () => void;
}

function ExpandableRow({ entry, isExpanded, onToggle }: ExpandableRowProps) {
  const hasDetails = entry.details !== null && Object.keys(entry.details).length > 0;

  return (
    <>
      <TableRow
        className={hasDetails ? "cursor-pointer" : undefined}
        onClick={hasDetails ? onToggle : undefined}
      >
        <TableCell className="text-sm font-mono whitespace-nowrap">
          <div className="flex items-center gap-1">
            {hasDetails && (
              isExpanded ? (
                <ChevronDown className="size-4 text-muted-foreground shrink-0" aria-hidden="true" />
              ) : (
                <ChevronRight className="size-4 text-muted-foreground shrink-0" aria-hidden="true" />
              )
            )}
            {!hasDetails && <span className="inline-block w-4" />}
            {formatDate(entry.created_at)}
          </div>
        </TableCell>
        <TableCell>
          <Badge variant="secondary">{entry.action}</Badge>
        </TableCell>
        <TableCell>
          {entry.entity_type ? (
            <Badge variant={getEntityBadgeVariant(entry.entity_type)}>
              {ENTITY_TYPE_LABELS[entry.entity_type] ?? entry.entity_type}
            </Badge>
          ) : (
            <span className="text-muted-foreground">-</span>
          )}
        </TableCell>
        <TableCell className="font-mono text-xs">
          {entry.entity_id ?? "-"}
        </TableCell>
        <TableCell className="text-sm">{entry.user}</TableCell>
      </TableRow>
      {isExpanded && hasDetails && (
        <TableRow>
          <TableCell colSpan={5} className="bg-muted/50 p-0">
            <pre className="overflow-x-auto p-4 text-xs font-mono whitespace-pre-wrap">
              {JSON.stringify(entry.details, null, 2)}
            </pre>
          </TableCell>
        </TableRow>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// Loading Skeleton
// ---------------------------------------------------------------------------

function ActivityTableSkeleton() {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Data</TableHead>
          <TableHead>Ação</TableHead>
          <TableHead>Entidade</TableHead>
          <TableHead>ID</TableHead>
          <TableHead>Usuário</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {Array.from({ length: 10 }).map((_, i) => (
          <TableRow key={i}>
            <TableCell><Skeleton className="h-4 w-32" /></TableCell>
            <TableCell><Skeleton className="h-5 w-16 rounded-full" /></TableCell>
            <TableCell><Skeleton className="h-5 w-24 rounded-full" /></TableCell>
            <TableCell><Skeleton className="h-4 w-20" /></TableCell>
            <TableCell><Skeleton className="h-4 w-20" /></TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

// ---------------------------------------------------------------------------
// Activity Page
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Debounce hook
// ---------------------------------------------------------------------------

function useDebouncedCallback(callback: (value: string) => void, delay: number) {
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const debouncedFn = useCallback(
    (value: string) => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      timeoutRef.current = setTimeout(() => callback(value), delay);
    },
    [callback, delay],
  );
  useEffect(() => () => { if (timeoutRef.current) clearTimeout(timeoutRef.current); }, []);
  return debouncedFn;
}

// ---------------------------------------------------------------------------
// Sort indicator
// ---------------------------------------------------------------------------

type SortDir = "asc" | "desc" | null;

function SortIndicator({ direction }: { direction: SortDir }) {
  if (direction === "asc") return <ChevronUp className="ml-1 size-3.5" aria-hidden="true" />;
  if (direction === "desc") return <ChevronDown className="ml-1 size-3.5" aria-hidden="true" />;
  return <ChevronsUpDown className="ml-1 size-3.5 opacity-40" aria-hidden="true" />;
}

// ---------------------------------------------------------------------------
// Activity Page
// ---------------------------------------------------------------------------

export function ActivityPage() {
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(PER_PAGE);
  const [entityType, setEntityType] = useState(NONE_SENTINEL);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState("created_at");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");

  const entityTypeFilter = entityType === NONE_SENTINEL ? undefined : entityType;

  const debouncedSearch = useDebouncedCallback(
    useCallback((v: string) => { setSearch(v); setPage(1); }, []),
    300,
  );

  function handleSearchInput(value: string) {
    setSearchInput(value);
    debouncedSearch(value);
  }

  function toggleSort(column: string) {
    if (sortBy === column) {
      setSortOrder((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(column);
      setSortOrder("desc");
    }
    setPage(1);
  }

  function getSortDir(column: string): SortDir {
    return sortBy === column ? sortOrder : null;
  }

  // ---- Query ----
  const {
    data,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["activity-log", page, perPage, entityTypeFilter, sortBy, sortOrder, search],
    queryFn: () => {
      const params = new URLSearchParams();
      params.set("page", String(page));
      params.set("per_page", String(perPage));
      if (entityTypeFilter) params.set("entity_type", entityTypeFilter);
      if (sortBy) params.set("sort_by", sortBy);
      params.set("sort_order", sortOrder);
      if (search) params.set("search", search);
      return api.get<PaginatedResponse>(`/activity-log?${params.toString()}`);
    },
  });

  const totalPages = data ? Math.max(1, Math.ceil(data.total / perPage)) : 1;

  // ---- Handlers ----
  function handleEntityTypeChange(value: string) {
    setEntityType(value);
    setPage(1);
    setExpandedId(null);
  }

  function handleToggleExpand(id: string) {
    setExpandedId((prev) => (prev === id ? null : id));
  }

  // ---- Render ----
  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">
            Log de Atividades
          </h1>
          <p className="mt-1 text-muted-foreground">
            Histórico de ações realizadas no painel administrativo.
          </p>
        </div>
        {data && data.items.length > 0 && (
          <Button
            variant="outline"
            onClick={() =>
              exportToCsv(
                data.items,
                [
                  { header: "Data", accessor: (e) => formatDate(e.created_at) },
                  { header: "Ação", accessor: (e) => e.action },
                  { header: "Entidade", accessor: (e) => (e.entity_type ? (ENTITY_TYPE_LABELS[e.entity_type] ?? e.entity_type) : "") },
                  { header: "ID", accessor: (e) => e.entity_id },
                  { header: "Usuário", accessor: (e) => e.user },
                  { header: "Detalhes", accessor: (e) => (e.details ? JSON.stringify(e.details) : "") },
                ],
                csvFilename("atividades")
              )
            }
          >
            <Download aria-hidden="true" />
            Exportar CSV
          </Button>
        )}
      </div>

      {/* Filters + Search */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
        <div className="space-y-1">
          <label
            htmlFor="filter-entity-type"
            className="text-xs font-medium text-muted-foreground"
          >
            Tipo de Entidade
          </label>
          <Select value={entityType} onValueChange={handleEntityTypeChange}>
            <SelectTrigger id="filter-entity-type" className="w-[220px]">
              <SelectValue placeholder="Todas" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={NONE_SENTINEL}>Todas</SelectItem>
              {ENTITY_TYPES.map((t) => (
                <SelectItem key={t.value} value={t.value}>
                  {t.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="relative sm:max-w-xs flex-1">
          <Search className="absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
          <Input
            placeholder="Buscar atividades..."
            value={searchInput}
            onChange={(e) => handleSearchInput(e.target.value)}
            className="pl-8"
            aria-label="Buscar atividades"
          />
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
            : "Erro ao carregar log de atividades."}
        </div>
      )}

      {/* Loading */}
      {isLoading && <ActivityTableSkeleton />}

      {/* Empty state */}
      {!isLoading && !error && data && data.items.length === 0 && (
        <p className="py-12 text-center text-muted-foreground">
          Nenhuma atividade encontrada.
        </p>
      )}

      {/* Data table */}
      {!isLoading && data && data.items.length > 0 && (
        <>
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>
                    <button
                      type="button"
                      className="inline-flex items-center gap-0.5 hover:text-foreground transition-colors -ml-1 px-1 py-0.5 rounded-sm"
                      onClick={() => toggleSort("created_at")}
                    >
                      Data
                      <SortIndicator direction={getSortDir("created_at")} />
                    </button>
                  </TableHead>
                  <TableHead>
                    <button
                      type="button"
                      className="inline-flex items-center gap-0.5 hover:text-foreground transition-colors -ml-1 px-1 py-0.5 rounded-sm"
                      onClick={() => toggleSort("action")}
                    >
                      Ação
                      <SortIndicator direction={getSortDir("action")} />
                    </button>
                  </TableHead>
                  <TableHead>
                    <button
                      type="button"
                      className="inline-flex items-center gap-0.5 hover:text-foreground transition-colors -ml-1 px-1 py-0.5 rounded-sm"
                      onClick={() => toggleSort("entity_type")}
                    >
                      Entidade
                      <SortIndicator direction={getSortDir("entity_type")} />
                    </button>
                  </TableHead>
                  <TableHead>ID</TableHead>
                  <TableHead>
                    <button
                      type="button"
                      className="inline-flex items-center gap-0.5 hover:text-foreground transition-colors -ml-1 px-1 py-0.5 rounded-sm"
                      onClick={() => toggleSort("user")}
                    >
                      Usuário
                      <SortIndicator direction={getSortDir("user")} />
                    </button>
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.map((entry) => (
                  <ExpandableRow
                    key={entry.id}
                    entry={entry}
                    isExpanded={expandedId === entry.id}
                    onToggle={() => handleToggleExpand(entry.id)}
                  />
                ))}
              </TableBody>
            </Table>
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between px-2 py-4">
            <p className="text-sm text-muted-foreground">
              {data.total} {data.total === 1 ? "registro" : "registros"} no total
            </p>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">Linhas</span>
                <Select
                  value={String(perPage)}
                  onValueChange={(value) => { setPerPage(Number(value)); setPage(1); }}
                >
                  <SelectTrigger className="w-[70px] h-8">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent align="end">
                    {[10, 20, 50].map((size) => (
                      <SelectItem key={size} value={String(size)}>{size}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <span className="text-sm text-muted-foreground">
                Página {page} de {totalPages}
              </span>
              <div className="flex items-center gap-1">
                <Button
                  variant="outline"
                  size="icon"
                  className="h-8 w-8"
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page <= 1}
                  aria-label="Página anterior"
                >
                  <ChevronLeft className="size-4" />
                </Button>
                <Button
                  variant="outline"
                  size="icon"
                  className="h-8 w-8"
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page >= totalPages}
                  aria-label="Próxima página"
                >
                  <ChevronRight className="size-4" />
                </Button>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
