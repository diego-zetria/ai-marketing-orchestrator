import { useQuery } from "@tanstack/react-query";
import {
  RefreshCw,
  Database,
  Cloud,
  Mail,
  MessageSquare,
  CheckSquare,
  Activity,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  HelpCircle,
  Users,
  Webhook,
  Zap,
} from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ServiceHealth {
  name: string;
  status: "healthy" | "degraded" | "down" | "unknown";
  latency_ms: number;
  message?: string;
  checked_at: string;
}

interface HealthResponse {
  status: "healthy" | "degraded" | "down";
  services: ServiceHealth[];
  checked_at: string;
}

interface HealthMetrics {
  errors_24h: number;
  requests_today: number;
  active_admins_1h: number;
  webhook_deliveries_24h: number;
  checked_at: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const STATUS_CONFIG: Record<string, { icon: typeof CheckCircle2; color: string; label: string }> = {
  healthy: { icon: CheckCircle2, color: "text-emerald-500", label: "Saudável" },
  degraded: { icon: AlertTriangle, color: "text-amber-500", label: "Degradado" },
  down: { icon: XCircle, color: "text-red-500", label: "Indisponível" },
  unknown: { icon: HelpCircle, color: "text-gray-400", label: "Desconhecido" },
};

const SERVICE_ICONS: Record<string, typeof Database> = {
  database: Database,
  s3: Cloud,
  ses: Mail,
  clickup: CheckSquare,
  telegram: MessageSquare,
};

function formatLatency(ms: number): string {
  if (ms < 1) return "<1ms";
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function formatTime(dateStr: string): string {
  return new Date(dateStr).toLocaleTimeString("pt-BR", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

// ---------------------------------------------------------------------------
// Overall Status Banner
// ---------------------------------------------------------------------------

function OverallStatusBanner({ status, checkedAt }: { status: string; checkedAt: string }) {
  const config = STATUS_CONFIG[status] ?? STATUS_CONFIG.unknown;
  const Icon = config.icon;

  const bgColors: Record<string, string> = {
    healthy: "bg-emerald-500/10 border-emerald-200",
    degraded: "bg-amber-500/10 border-amber-200",
    down: "bg-red-500/10 border-red-200",
  };

  return (
    <div
      className={cn(
        "flex items-center gap-4 rounded-lg border p-4",
        bgColors[status] ?? "bg-muted"
      )}
    >
      <Icon className={cn("h-8 w-8", config.color)} />
      <div>
        <p className="text-lg font-semibold">{config.label}</p>
        <p className="text-sm text-muted-foreground">
          Última verificação: {formatTime(checkedAt)}
        </p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Service Card
// ---------------------------------------------------------------------------

function ServiceCard({ service }: { service: ServiceHealth }) {
  const statusConfig = STATUS_CONFIG[service.status] ?? STATUS_CONFIG.unknown;
  const StatusIcon = statusConfig.icon;
  const ServiceIcon = SERVICE_ICONS[service.name.toLowerCase()] ?? Activity;

  return (
    <div className="flex items-center gap-4 rounded-lg border bg-card p-4 transition-colors">
      {/* Service icon */}
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-muted">
        <ServiceIcon className="h-5 w-5 text-muted-foreground" />
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium capitalize">{service.name}</p>
        {service.message && (
          <p className="truncate text-xs text-muted-foreground">{service.message}</p>
        )}
      </div>

      {/* Latency */}
      <span className="shrink-0 text-xs text-muted-foreground">
        {formatLatency(service.latency_ms)}
      </span>

      {/* Status badge */}
      <Badge
        variant="outline"
        className={cn("shrink-0 gap-1", statusConfig.color)}
      >
        <StatusIcon className="h-3 w-3" />
        {statusConfig.label}
      </Badge>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Metric Card
// ---------------------------------------------------------------------------

function MetricCard({
  icon: Icon,
  label,
  value,
  suffix,
  colorClass,
}: {
  icon: typeof Activity;
  label: string;
  value: number | string;
  suffix?: string;
  colorClass?: string;
}) {
  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="flex items-center gap-2">
        <Icon className={cn("h-4 w-4", colorClass ?? "text-muted-foreground")} />
        <span className="text-xs text-muted-foreground">{label}</span>
      </div>
      <p className="mt-2 text-2xl font-bold tracking-tight">
        {value}
        {suffix && (
          <span className="ml-1 text-sm font-normal text-muted-foreground">
            {suffix}
          </span>
        )}
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export function HealthPage() {
  const {
    data: health,
    isLoading: healthLoading,
    refetch: refetchHealth,
    isFetching: healthFetching,
  } = useQuery({
    queryKey: ["health"],
    queryFn: () => api.get<HealthResponse>("/health"),
    refetchInterval: 60_000, // auto-refresh every 60s
  });

  const {
    data: metrics,
    isLoading: metricsLoading,
    refetch: refetchMetrics,
  } = useQuery({
    queryKey: ["health", "metrics"],
    queryFn: () => api.get<HealthMetrics>("/health/metrics"),
    refetchInterval: 60_000,
  });

  function handleRefresh() {
    refetchHealth();
    refetchMetrics();
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Status do Sistema</h1>
          <p className="text-sm text-muted-foreground">
            Monitoramento em tempo real dos serviços
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={handleRefresh}
          disabled={healthFetching}
        >
          <RefreshCw
            className={cn("mr-2 h-4 w-4", healthFetching && "animate-spin")}
          />
          Atualizar
        </Button>
      </div>

      {/* Overall status */}
      {healthLoading && <Skeleton className="h-20 rounded-lg" />}
      {health && (
        <OverallStatusBanner
          status={health.status}
          checkedAt={health.checked_at}
        />
      )}

      {/* Metrics */}
      <div>
        <h2 className="mb-3 text-sm font-semibold text-muted-foreground uppercase tracking-wider">
          Métricas (24h)
        </h2>
        {metricsLoading && (
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-24 rounded-lg" />
            ))}
          </div>
        )}
        {metrics && (
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <MetricCard
              icon={AlertTriangle}
              label="Erros (24h)"
              value={metrics.errors_24h}
              colorClass={metrics.errors_24h > 0 ? "text-red-500" : "text-emerald-500"}
            />
            <MetricCard
              icon={Zap}
              label="Requests hoje"
              value={metrics.requests_today}
              colorClass="text-blue-500"
            />
            <MetricCard
              icon={Users}
              label="Admins ativos (1h)"
              value={metrics.active_admins_1h}
              colorClass="text-violet-500"
            />
            <MetricCard
              icon={Webhook}
              label="Webhooks (24h)"
              value={metrics.webhook_deliveries_24h}
              colorClass="text-amber-500"
            />
          </div>
        )}
      </div>

      <Separator />

      {/* Services */}
      <div>
        <h2 className="mb-3 text-sm font-semibold text-muted-foreground uppercase tracking-wider">
          Serviços
        </h2>
        {healthLoading && (
          <div className="space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-16 rounded-lg" />
            ))}
          </div>
        )}
        {health && (
          <div className="space-y-3">
            {health.services.map((service) => (
              <ServiceCard key={service.name} service={service} />
            ))}
          </div>
        )}
      </div>

      {/* Auto-refresh indicator */}
      <p className="text-center text-xs text-muted-foreground">
        Atualiza automaticamente a cada 60 segundos
      </p>
    </div>
  );
}
