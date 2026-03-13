import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  LayoutGrid,
  List,
  Download,
  Eye,
  FileImage,
  FileVideo,
  FileText,
  File,
  X,
  Search,
  HardDrive,
} from "lucide-react";
import { api } from "@/lib/api";
import { exportToCsv, csvFilename } from "@/lib/export";
import { DataTableFilters, type ActiveFilters, type FilterDefinition } from "@/components/data-table-filters";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Dialog,
  DialogContent,
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
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface AssetVersion {
  version_number: number;
  file_url: string;
  thumbnail_url: string | null;
  file_type: string;
  file_size: number;
  created_at: string;
}

interface MediaAsset {
  id: string;
  title: string;
  client_id: string;
  client_name: string;
  status: string;
  latest_version: AssetVersion;
  created_at: string;
  updated_at: string;
}

interface MediaListResponse {
  items: MediaAsset[];
  total: number;
  page: number;
  per_page: number;
}

interface MediaDetail {
  id: string;
  title: string;
  client_id: string;
  client_name: string;
  status: string;
  versions: AssetVersion[];
  events: { event_type: string; created_at: string; metadata_: Record<string, unknown> }[];
  created_at: string;
}

interface MediaStats {
  total_assets: number;
  total_size_bytes: number;
  by_status: Record<string, number>;
  by_client: { client_id: string; client_name: string; count: number }[];
}

interface Client {
  id: string;
  name: string;
  display_name: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatFileSize(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

function FileIcon({ fileType, className }: { fileType: string; className?: string }) {
  if (fileType.startsWith("image/")) return <FileImage className={className} />;
  if (fileType.startsWith("video/")) return <FileVideo className={className} />;
  if (fileType.includes("pdf") || fileType.includes("document")) return <FileText className={className} />;
  return <File className={className} />;
}

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-amber-500/10 text-amber-700 border-amber-200",
  approved: "bg-emerald-500/10 text-emerald-700 border-emerald-200",
  changes_requested: "bg-red-500/10 text-red-700 border-red-200",
  archived: "bg-gray-500/10 text-gray-500 border-gray-200",
};

const STATUS_LABELS: Record<string, string> = {
  pending: "Pendente",
  approved: "Aprovado",
  changes_requested: "Alteração",
  archived: "Arquivado",
};

// ---------------------------------------------------------------------------
// Media Card (Grid View)
// ---------------------------------------------------------------------------

function MediaCard({
  asset,
  onClick,
}: {
  asset: MediaAsset;
  onClick: () => void;
}) {
  const hasThumbnail = asset.latest_version.thumbnail_url;

  return (
    <button
      onClick={onClick}
      className="group relative flex flex-col overflow-hidden rounded-lg border bg-card text-left transition-all hover:shadow-md hover:border-primary/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      {/* Thumbnail / Placeholder */}
      <div className="relative aspect-[4/3] bg-muted">
        {hasThumbnail ? (
          <img
            src={asset.latest_version.thumbnail_url!}
            alt={asset.title}
            className="h-full w-full object-cover"
            loading="lazy"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center">
            <FileIcon fileType={asset.latest_version.file_type} className="h-12 w-12 text-muted-foreground/30" />
          </div>
        )}
        {/* Overlay on hover */}
        <div className="absolute inset-0 flex items-center justify-center bg-black/50 opacity-0 transition-opacity group-hover:opacity-100">
          <Eye className="h-6 w-6 text-white" />
        </div>
        {/* Status badge */}
        <Badge
          variant="outline"
          className={cn(
            "absolute right-2 top-2 text-[10px]",
            STATUS_COLORS[asset.status] ?? "bg-muted text-muted-foreground"
          )}
        >
          {STATUS_LABELS[asset.status] ?? asset.status}
        </Badge>
      </div>

      {/* Info */}
      <div className="flex flex-1 flex-col gap-1 p-3">
        <p className="truncate text-sm font-medium">{asset.title}</p>
        <p className="truncate text-xs text-muted-foreground">{asset.client_name}</p>
        <div className="mt-auto flex items-center justify-between pt-1">
          <span className="text-[10px] text-muted-foreground">
            v{asset.latest_version.version_number}
          </span>
          <span className="text-[10px] text-muted-foreground">
            {formatFileSize(asset.latest_version.file_size)}
          </span>
        </div>
      </div>
    </button>
  );
}

// ---------------------------------------------------------------------------
// Media Row (List View)
// ---------------------------------------------------------------------------

function MediaRow({
  asset,
  onClick,
}: {
  asset: MediaAsset;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="flex w-full items-center gap-4 rounded-lg border bg-card px-4 py-3 text-left transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      {/* Thumbnail */}
      <div className="flex h-12 w-12 shrink-0 items-center justify-center overflow-hidden rounded-md bg-muted">
        {asset.latest_version.thumbnail_url ? (
          <img
            src={asset.latest_version.thumbnail_url}
            alt={asset.title}
            className="h-full w-full object-cover"
            loading="lazy"
          />
        ) : (
          <FileIcon fileType={asset.latest_version.file_type} className="h-5 w-5 text-muted-foreground/50" />
        )}
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <p className="truncate text-sm font-medium">{asset.title}</p>
        <p className="text-xs text-muted-foreground">{asset.client_name}</p>
      </div>

      {/* Meta */}
      <Badge
        variant="outline"
        className={cn(
          "shrink-0 text-[10px]",
          STATUS_COLORS[asset.status] ?? "bg-muted text-muted-foreground"
        )}
      >
        {STATUS_LABELS[asset.status] ?? asset.status}
      </Badge>
      <span className="shrink-0 text-xs text-muted-foreground">
        v{asset.latest_version.version_number}
      </span>
      <span className="hidden shrink-0 text-xs text-muted-foreground sm:inline">
        {formatFileSize(asset.latest_version.file_size)}
      </span>
      <span className="hidden shrink-0 text-xs text-muted-foreground md:inline">
        {formatDate(asset.created_at)}
      </span>
    </button>
  );
}

// ---------------------------------------------------------------------------
// Detail Dialog
// ---------------------------------------------------------------------------

function MediaDetailDialog({
  assetId,
  open,
  onClose,
}: {
  assetId: string | null;
  open: boolean;
  onClose: () => void;
}) {
  const { data, isLoading } = useQuery({
    queryKey: ["media", "detail", assetId],
    queryFn: () => api.get<MediaDetail>(`/media/${assetId}`),
    enabled: open && !!assetId,
  });

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle>{isLoading ? "Carregando..." : data?.title}</DialogTitle>
        </DialogHeader>

        {isLoading && (
          <div className="space-y-3 p-4">
            <Skeleton className="h-48 w-full" />
            <Skeleton className="h-4 w-2/3" />
            <Skeleton className="h-4 w-1/2" />
          </div>
        )}

        {data && (
          <ScrollArea className="flex-1 -mx-6 px-6">
            <div className="space-y-6 pb-4">
              {/* Preview */}
              {data.versions[0]?.thumbnail_url && (
                <div className="overflow-hidden rounded-lg border bg-muted">
                  <img
                    src={data.versions[0].thumbnail_url}
                    alt={data.title}
                    className="mx-auto max-h-64 object-contain"
                  />
                </div>
              )}

              {/* Info */}
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <p className="text-muted-foreground">Cliente</p>
                  <p className="font-medium">{data.client_name}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Status</p>
                  <Badge
                    variant="outline"
                    className={STATUS_COLORS[data.status] ?? ""}
                  >
                    {STATUS_LABELS[data.status] ?? data.status}
                  </Badge>
                </div>
                <div>
                  <p className="text-muted-foreground">Criado em</p>
                  <p className="font-medium">{formatDate(data.created_at)}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Versões</p>
                  <p className="font-medium">{data.versions.length}</p>
                </div>
              </div>

              <Separator />

              {/* Versions */}
              <div>
                <h4 className="mb-3 text-sm font-semibold">Histórico de Versões</h4>
                <div className="space-y-2">
                  {data.versions.map((v) => (
                      <div
                        key={v.version_number}
                        className="flex items-center gap-3 rounded-lg border p-3"
                      >
                        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded bg-muted">
                          <FileIcon fileType={v.file_type} className="h-4 w-4 text-muted-foreground" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium">
                            Versão {v.version_number}
                          </p>
                          <p className="text-xs text-muted-foreground">
                            {formatDate(v.created_at)} &middot;{" "}
                            {formatFileSize(v.file_size)}
                          </p>
                        </div>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <a
                              href={v.file_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="shrink-0"
                              onClick={(e) => e.stopPropagation()}
                            >
                              <Button variant="ghost" size="icon" className="h-7 w-7">
                                <Download className="h-3.5 w-3.5" />
                              </Button>
                            </a>
                          </TooltipTrigger>
                          <TooltipContent>Download</TooltipContent>
                        </Tooltip>
                      </div>
                  ))}
                </div>
              </div>

              {/* Events */}
              {data.events.length > 0 && (
                <>
                  <Separator />
                  <div>
                    <h4 className="mb-3 text-sm font-semibold">Eventos</h4>
                    <div className="space-y-1.5">
                      {data.events.map((evt, i) => (
                        <div
                          key={i}
                          className="flex items-center justify-between rounded px-2 py-1.5 text-xs"
                        >
                          <span className="font-medium">
                            {evt.event_type.replace(/_/g, " ")}
                          </span>
                          <span className="text-muted-foreground">
                            {formatDate(evt.created_at)}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                </>
              )}
            </div>
          </ScrollArea>
        )}
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Stats Bar
// ---------------------------------------------------------------------------

function StatsBar({ stats }: { stats: MediaStats | undefined }) {
  if (!stats) return null;

  return (
    <div className="flex flex-wrap items-center gap-4 rounded-lg border bg-muted/30 p-3 text-sm">
      <div className="flex items-center gap-2">
        <FileImage className="h-4 w-4 text-muted-foreground" />
        <span className="font-medium">{stats.total_assets}</span>
        <span className="text-muted-foreground">assets</span>
      </div>
      <Separator orientation="vertical" className="h-4" />
      <div className="flex items-center gap-2">
        <HardDrive className="h-4 w-4 text-muted-foreground" />
        <span className="font-medium">{formatFileSize(stats.total_size_bytes)}</span>
        <span className="text-muted-foreground">total</span>
      </div>
      {Object.entries(stats.by_status).map(([status, count]) => (
        <Badge
          key={status}
          variant="outline"
          className={cn("text-[10px]", STATUS_COLORS[status] ?? "")}
        >
          {STATUS_LABELS[status] ?? status}: {count}
        </Badge>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

type ViewMode = "grid" | "list";

export function MediaPage() {
  const [viewMode, setViewMode] = useState<ViewMode>("grid");
  const [page, setPage] = useState(1);
  const [perPage] = useState(24);
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState("created_at");
  const [sortDir, setSortDir] = useState("desc");
  const [activeFilters, setActiveFilters] = useState<ActiveFilters>({});
  const [selectedAssetId, setSelectedAssetId] = useState<string | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);

  // Build query params
  const queryParams = useMemo(() => {
    const params = new URLSearchParams();
    params.set("page", String(page));
    params.set("per_page", String(perPage));
    params.set("sort_by", sortBy);
    params.set("sort_dir", sortDir);
    if (search) params.set("search", search);
    if (activeFilters.status?.length) {
      for (const v of activeFilters.status) params.append("status", v);
    }
    if (activeFilters.client_id?.length) {
      for (const v of activeFilters.client_id) params.append("client_id", v);
    }
    if (activeFilters.media_type?.length) {
      for (const v of activeFilters.media_type) params.append("media_type", v);
    }
    return params.toString();
  }, [page, perPage, sortBy, sortDir, search, activeFilters]);

  const { data, isLoading } = useQuery({
    queryKey: ["media", "list", queryParams],
    queryFn: () => api.get<MediaListResponse>(`/media?${queryParams}`),
  });

  const { data: stats } = useQuery({
    queryKey: ["media", "stats"],
    queryFn: () => api.get<MediaStats>("/media/stats"),
  });

  const { data: clients } = useQuery({
    queryKey: ["clients", "all"],
    queryFn: () =>
      api.get<{ items: Client[] }>("/clients?per_page=200").then((r) => r.items),
  });

  // Filter definitions
  const filterDefs = useMemo<FilterDefinition[]>(() => {
    const defs: FilterDefinition[] = [
      {
        id: "status",
        label: "Status",
        options: [
          { label: "Pendente", value: "pending" },
          { label: "Aprovado", value: "approved" },
          { label: "Alteração", value: "changes_requested" },
          { label: "Arquivado", value: "archived" },
        ],
      },
      {
        id: "media_type",
        label: "Tipo",
        options: [
          { label: "Imagem", value: "image" },
          { label: "Vídeo", value: "video" },
          { label: "Documento", value: "document" },
        ],
      },
    ];
    if (clients?.length) {
      defs.push({
        id: "client_id",
        label: "Cliente",
        options: clients.map((c) => ({ label: c.display_name, value: c.id })),
      });
    }
    return defs;
  }, [clients]);

  const totalPages = data ? Math.ceil(data.total / perPage) : 0;
  const assets = data?.items ?? [];

  function handleFiltersChange(filters: ActiveFilters) {
    setActiveFilters(filters);
    setPage(1);
  }

  function openDetail(assetId: string) {
    setSelectedAssetId(assetId);
    setDetailOpen(true);
  }

  function handleExport() {
    if (!assets.length) return;
    exportToCsv(
      assets,
      [
        { header: "Título", accessor: (a) => a.title },
        { header: "Cliente", accessor: (a) => a.client_name },
        { header: "Status", accessor: (a) => STATUS_LABELS[a.status] ?? a.status },
        { header: "Versão", accessor: (a) => a.latest_version.version_number },
        { header: "Tipo", accessor: (a) => a.latest_version.file_type },
        { header: "Tamanho", accessor: (a) => formatFileSize(a.latest_version.file_size) },
        { header: "Criado em", accessor: (a) => formatDate(a.created_at) },
      ],
      csvFilename("media")
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Biblioteca de Mídia</h1>
          <p className="text-sm text-muted-foreground">
            Assets de aprovação e materiais dos clientes
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={handleExport}>
            <Download className="mr-2 h-4 w-4" />
            Exportar
          </Button>
        </div>
      </div>

      {/* Stats */}
      <StatsBar stats={stats} />

      {/* Controls */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2 flex-1">
          {/* Search */}
          <div className="relative max-w-xs flex-1">
            <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Buscar assets..."
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              className="pl-9 h-9"
            />
            {search && (
              <button
                onClick={() => {
                  setSearch("");
                  setPage(1);
                }}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </div>

          {/* Sort */}
          <Select value={sortBy} onValueChange={(v) => { setSortBy(v); setPage(1); }}>
            <SelectTrigger className="w-[140px] h-9">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="created_at">Data criação</SelectItem>
              <SelectItem value="updated_at">Atualizado</SelectItem>
              <SelectItem value="title">Nome</SelectItem>
            </SelectContent>
          </Select>

          <Button
            variant="ghost"
            size="icon"
            className="h-9 w-9"
            onClick={() => setSortDir((d) => (d === "asc" ? "desc" : "asc"))}
          >
            <span className="text-xs font-medium">
              {sortDir === "asc" ? "A-Z" : "Z-A"}
            </span>
          </Button>
        </div>

        {/* View mode toggle */}
        <div className="flex items-center gap-1 rounded-lg border p-0.5">
          <Button
            variant={viewMode === "grid" ? "secondary" : "ghost"}
            size="icon"
            className="h-7 w-7"
            onClick={() => setViewMode("grid")}
            aria-label="Visualização em grade"
          >
            <LayoutGrid className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant={viewMode === "list" ? "secondary" : "ghost"}
            size="icon"
            className="h-7 w-7"
            onClick={() => setViewMode("list")}
            aria-label="Visualização em lista"
          >
            <List className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      {/* Filters */}
      <DataTableFilters
        filters={filterDefs}
        activeFilters={activeFilters}
        onFiltersChange={handleFiltersChange}
      />

      {/* Loading */}
      {isLoading && (
        <div
          className={cn(
            viewMode === "grid"
              ? "grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5"
              : "space-y-2"
          )}
        >
          {Array.from({ length: 12 }).map((_, i) => (
            <Skeleton
              key={i}
              className={viewMode === "grid" ? "aspect-[4/3] rounded-lg" : "h-16 rounded-lg"}
            />
          ))}
        </div>
      )}

      {/* Empty state */}
      {!isLoading && assets.length === 0 && (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed py-16">
          <FileImage className="mb-3 h-10 w-10 text-muted-foreground/40" />
          <p className="text-sm font-medium text-muted-foreground">
            Nenhum asset encontrado
          </p>
          <p className="mt-1 text-xs text-muted-foreground/70">
            Assets aparecerão aqui quando forem enviados para aprovação
          </p>
        </div>
      )}

      {/* Grid view */}
      {!isLoading && assets.length > 0 && viewMode === "grid" && (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
          {assets.map((asset) => (
            <MediaCard
              key={asset.id}
              asset={asset}
              onClick={() => openDetail(asset.id)}
            />
          ))}
        </div>
      )}

      {/* List view */}
      {!isLoading && assets.length > 0 && viewMode === "list" && (
        <div className="space-y-2">
          {assets.map((asset) => (
            <MediaRow
              key={asset.id}
              asset={asset}
              onClick={() => openDetail(asset.id)}
            />
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between pt-2">
          <p className="text-sm text-muted-foreground">
            {data?.total ?? 0} assets &middot; Página {page} de {totalPages}
          </p>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
            >
              Anterior
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
            >
              Próximo
            </Button>
          </div>
        </div>
      )}

      {/* Detail dialog */}
      <MediaDetailDialog
        assetId={selectedAssetId}
        open={detailOpen}
        onClose={() => setDetailOpen(false)}
      />
    </div>
  );
}
