import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Users,
  Building2,
  GitBranch,
  Bot,
  ScrollText,
  AlertCircle,
  Clock,
  CheckCircle2,
  AlertTriangle,
  TrendingUp,
} from "lucide-react";
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api } from "@/lib/api";
import type { LucideIcon } from "lucide-react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface DashboardStats {
  total_team_members: number;
  total_clients: number;
  total_rules: number;
  total_agents: number;
  recent_activity_count: number;
  pending_approvals: number;
  approved_this_month: number;
  overdue_approvals: number;
  avg_revisions: number;
  approval_rate: number;
}

interface ActivityEntry {
  id: string;
  action: string;
  entity_type: string;
  entity_id: string;
  details: Record<string, unknown>;
  user: string;
  created_at: string;
}

interface TrendPoint {
  week: string;
  pending: number;
  approved: number;
  changes_requested: number;
}

interface ApprovalTrendsResponse {
  trends: TrendPoint[];
}

interface PipelineEntry {
  status: string;
  label: string;
  count: number;
}

interface ApprovalPipelineResponse {
  pipeline: PipelineEntry[];
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const ACTION_LABELS: Record<string, string> = {
  member_created: "Membro criado",
  member_updated: "Membro atualizado",
  member_deleted: "Membro removido",
  client_created: "Cliente criado",
  client_updated: "Cliente atualizado",
  client_deleted: "Cliente removido",
  rule_created: "Regra criada",
  rule_updated: "Regra atualizada",
  rule_deleted: "Regra removida",
  notification_created: "Notificação criada",
  notification_updated: "Notificação atualizada",
  notification_deleted: "Notificação removida",
  agent_created: "Agente criado",
  agent_updated: "Agente atualizado",
  agent_deleted: "Agente removido",
  brand_created: "Diretriz criada",
  brand_updated: "Diretriz atualizada",
  brand_deleted: "Diretriz removida",
  config_created: "Configuração criada",
  config_updated: "Configuração atualizada",
  config_deleted: "Configuração removida",
};

const ENTITY_LABELS: Record<string, string> = {
  team_member: "Membro",
  client: "Cliente",
  assignment_rule: "Regra",
  notification_rule: "Notificação",
  agent_config: "Agente",
  brand_guideline: "Diretriz",
  system_config: "Configuração",
};

function formatAction(action: string): string {
  return ACTION_LABELS[action] ?? action.replace(/_/g, " ");
}

function formatEntityType(entityType: string): string {
  return ENTITY_LABELS[entityType] ?? entityType.replace(/_/g, " ");
}

function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSeconds = Math.floor(diffMs / 1000);
  const diffMinutes = Math.floor(diffSeconds / 60);
  const diffHours = Math.floor(diffMinutes / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffSeconds < 60) return "agora";
  if (diffMinutes < 60) return `${diffMinutes}min atrás`;
  if (diffHours < 24) return `${diffHours}h atrás`;
  if (diffDays < 7) return `${diffDays}d atrás`;

  return date.toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
  });
}

function formatWeekLabel(isoDate: string): string {
  const d = new Date(isoDate + "T00:00:00");
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
}

// ---------------------------------------------------------------------------
// KPI Card
// ---------------------------------------------------------------------------

interface KpiCardProps {
  title: string;
  value: number | string | undefined;
  icon: LucideIcon;
  loading: boolean;
  colorClass?: string;
  suffix?: string;
}

function KpiCard({ title, value, icon: Icon, loading, colorClass, suffix }: KpiCardProps) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {title}
        </CardTitle>
        <Icon className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
      </CardHeader>
      <CardContent>
        {loading ? (
          <Skeleton className="h-8 w-16" />
        ) : (
          <p className={`text-2xl font-bold ${colorClass ?? ""}`}>
            {value ?? 0}{suffix ?? ""}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Charts
// ---------------------------------------------------------------------------

const CHART_COLORS = {
  pending: "#f59e0b",
  approved: "#059669",
  changes_requested: "#ef4444",
};

function ApprovalTrendsChart({ data, loading }: { data: TrendPoint[] | undefined; loading: boolean }) {
  if (loading) {
    return <Skeleton className="h-[300px] w-full" />;
  }

  if (!data || data.length === 0) {
    return (
      <p className="flex h-[300px] items-center justify-center text-sm text-muted-foreground">
        Sem dados de aprovações no período.
      </p>
    );
  }

  const chartData = data.map((d) => ({
    ...d,
    weekLabel: formatWeekLabel(d.week),
  }));

  return (
    <ResponsiveContainer width="100%" height={300}>
      <AreaChart data={chartData} margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
        <XAxis dataKey="weekLabel" tick={{ fontSize: 12 }} className="text-muted-foreground" />
        <YAxis tick={{ fontSize: 12 }} allowDecimals={false} className="text-muted-foreground" />
        <Tooltip
          contentStyle={{ fontSize: 12, borderRadius: 8 }}
          labelFormatter={(label) => `Semana de ${label}`}
        />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Area
          type="monotone"
          dataKey="approved"
          name="Aprovados"
          stroke={CHART_COLORS.approved}
          fill={CHART_COLORS.approved}
          fillOpacity={0.15}
          strokeWidth={2}
        />
        <Area
          type="monotone"
          dataKey="pending"
          name="Pendentes"
          stroke={CHART_COLORS.pending}
          fill={CHART_COLORS.pending}
          fillOpacity={0.15}
          strokeWidth={2}
        />
        <Area
          type="monotone"
          dataKey="changes_requested"
          name="Alterações"
          stroke={CHART_COLORS.changes_requested}
          fill={CHART_COLORS.changes_requested}
          fillOpacity={0.1}
          strokeWidth={2}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

function ApprovalPipelineChart({ data, loading }: { data: PipelineEntry[] | undefined; loading: boolean }) {
  if (loading) {
    return <Skeleton className="h-[250px] w-full" />;
  }

  if (!data || data.length === 0) {
    return (
      <p className="flex h-[250px] items-center justify-center text-sm text-muted-foreground">
        Sem dados de pipeline.
      </p>
    );
  }

  const STATUS_COLORS: Record<string, string> = {
    pending_review: CHART_COLORS.pending,
    approved: CHART_COLORS.approved,
    changes_requested: CHART_COLORS.changes_requested,
    expired: "#6b7280",
  };

  const chartData = data.map((d) => ({
    ...d,
    fill: STATUS_COLORS[d.status] ?? "#8b5cf6",
  }));

  return (
    <ResponsiveContainer width="100%" height={250}>
      <BarChart data={chartData} margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
        <XAxis dataKey="label" tick={{ fontSize: 12 }} className="text-muted-foreground" />
        <YAxis tick={{ fontSize: 12 }} allowDecimals={false} className="text-muted-foreground" />
        <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
        <Bar dataKey="count" name="Quantidade" radius={[4, 4, 0, 0]}>
          {chartData.map((entry, index) => (
            <Cell key={index} fill={entry.fill} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

// ---------------------------------------------------------------------------
// Activity List
// ---------------------------------------------------------------------------

function ActivityList({
  entries,
  loading,
}: {
  entries: ActivityEntry[] | undefined;
  loading: boolean;
}) {
  if (loading) {
    return (
      <div className="space-y-4" role="status" aria-label="Carregando atividades">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="flex items-start gap-3">
            <Skeleton className="mt-1 h-4 w-4 shrink-0 rounded-full" />
            <div className="flex-1 space-y-1">
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-3 w-1/3" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (!entries || entries.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        Nenhuma atividade recente
      </p>
    );
  }

  return (
    <ul className="space-y-4" aria-label="Atividades recentes">
      {entries.map((entry) => (
        <li key={entry.id} className="flex items-start gap-3">
          <ScrollText
            className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground"
            aria-hidden="true"
          />
          <div className="flex-1 min-w-0">
            <p className="text-sm">
              <span className="font-medium">{formatAction(entry.action)}</span>
              <span className="text-muted-foreground">
                {" "}
                &mdash; {formatEntityType(entry.entity_type)}
              </span>
            </p>
            <p className="text-xs text-muted-foreground">
              {formatRelativeTime(entry.created_at)}
              {entry.user && ` por ${entry.user}`}
            </p>
          </div>
        </li>
      ))}
    </ul>
  );
}

// ---------------------------------------------------------------------------
// Error State
// ---------------------------------------------------------------------------

function ErrorBanner({ message }: { message: string }) {
  return (
    <div
      role="alert"
      className="flex items-center gap-2 rounded-lg border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm text-destructive"
    >
      <AlertCircle className="h-4 w-4 shrink-0" aria-hidden="true" />
      <p>{message}</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Dashboard Page
// ---------------------------------------------------------------------------

export function DashboardPage() {
  const [trendDays, setTrendDays] = useState("30");

  const {
    data: stats,
    isLoading: statsLoading,
    error: statsError,
  } = useQuery({
    queryKey: ["dashboard", "stats"],
    queryFn: () => api.get<DashboardStats>("/dashboard/stats"),
  });

  const {
    data: activity,
    isLoading: activityLoading,
    error: activityError,
  } = useQuery({
    queryKey: ["dashboard", "activity"],
    queryFn: () => api.get<ActivityEntry[]>("/dashboard/activity"),
  });

  const {
    data: trends,
    isLoading: trendsLoading,
  } = useQuery({
    queryKey: ["dashboard", "approval-trends", trendDays],
    queryFn: () => api.get<ApprovalTrendsResponse>(`/dashboard/approval-trends?days=${trendDays}`),
  });

  const {
    data: pipeline,
    isLoading: pipelineLoading,
  } = useQuery({
    queryKey: ["dashboard", "approval-pipeline"],
    queryFn: () => api.get<ApprovalPipelineResponse>("/dashboard/approval-pipeline"),
  });

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
        <p className="mt-1 text-muted-foreground">
          Visão geral do sistema Marketing Briefing Bot.
        </p>
      </div>

      {/* Stats error */}
      {statsError && (
        <ErrorBanner
          message={
            statsError instanceof Error
              ? statsError.message
              : "Erro ao carregar estatísticas"
          }
        />
      )}

      {/* Primary KPI cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          title="Membros da Equipe"
          value={stats?.total_team_members}
          icon={Users}
          loading={statsLoading}
        />
        <KpiCard
          title="Clientes Ativos"
          value={stats?.total_clients}
          icon={Building2}
          loading={statsLoading}
        />
        <KpiCard
          title="Regras Configuradas"
          value={stats?.total_rules}
          icon={GitBranch}
          loading={statsLoading}
        />
        <KpiCard
          title="Agentes IA"
          value={stats?.total_agents}
          icon={Bot}
          loading={statsLoading}
        />
      </div>

      {/* Approval KPI cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          title="Pendentes Revisão"
          value={stats?.pending_approvals}
          icon={Clock}
          loading={statsLoading}
          colorClass="text-amber-500"
        />
        <KpiCard
          title="Aprovados (mês)"
          value={stats?.approved_this_month}
          icon={CheckCircle2}
          loading={statsLoading}
          colorClass="text-emerald-600"
        />
        <KpiCard
          title="Atrasados (>3 dias)"
          value={stats?.overdue_approvals}
          icon={AlertTriangle}
          loading={statsLoading}
          colorClass={stats?.overdue_approvals ? "text-destructive" : ""}
        />
        <KpiCard
          title="Taxa de Aprovação"
          value={stats?.approval_rate}
          icon={TrendingUp}
          loading={statsLoading}
          suffix="%"
          colorClass="text-emerald-600"
        />
      </div>

      {/* Charts row */}
      <div className="grid gap-4 lg:grid-cols-3">
        {/* Approval trends - area chart (2/3 width) */}
        <Card className="lg:col-span-2">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-base">Tendência de Aprovações</CardTitle>
            <Select value={trendDays} onValueChange={setTrendDays}>
              <SelectTrigger className="w-[130px] h-8">
                <SelectValue />
              </SelectTrigger>
              <SelectContent align="end">
                <SelectItem value="7">7 dias</SelectItem>
                <SelectItem value="30">30 dias</SelectItem>
                <SelectItem value="90">90 dias</SelectItem>
                <SelectItem value="180">6 meses</SelectItem>
              </SelectContent>
            </Select>
          </CardHeader>
          <CardContent>
            <ApprovalTrendsChart data={trends?.trends} loading={trendsLoading} />
          </CardContent>
        </Card>

        {/* Pipeline - bar chart (1/3 width) */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Pipeline de Aprovações</CardTitle>
          </CardHeader>
          <CardContent>
            <ApprovalPipelineChart data={pipeline?.pipeline} loading={pipelineLoading} />
          </CardContent>
        </Card>
      </div>

      {/* Activity section */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ScrollText className="h-5 w-5" aria-hidden="true" />
            Atividades Recentes
          </CardTitle>
        </CardHeader>
        <CardContent>
          {activityError ? (
            <ErrorBanner
              message={
                activityError instanceof Error
                  ? activityError.message
                  : "Erro ao carregar atividades"
              }
            />
          ) : (
            <ActivityList entries={activity} loading={activityLoading} />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
