import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "@tanstack/react-router";
import {
  ArrowLeft,
  ExternalLink,
  Mail,
  MessageSquare,
  Send,
} from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { usePermission } from "@/lib/auth";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
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

interface AssetVersion {
  id: string;
  version_number: number;
  file_type: string;
  file_format: string;
  original_url: string;
  thumbnail_url: string | null;
  file_size_bytes: number | null;
  created_at: string;
}

interface Comment {
  id: string;
  author_type: string;
  author_name: string;
  content: string;
  created_at: string;
}

interface Decision {
  id: string;
  version_id: string;
  decision: string;
  comment: string | null;
  decided_by: string;
  decided_at: string;
}

interface Event {
  id: string;
  event_type: string;
  actor: string;
  metadata_: Record<string, unknown> | null;
  created_at: string;
}

interface ApprovalAssetDetail {
  id: string;
  client_name: string;
  title: string;
  status: string;
  current_version: number;
  clickup_task_id: string;
  created_at: string;
  updated_at: string;
  description: string | null;
  versions: AssetVersion[];
  comments: Comment[];
  decisions: Decision[];
}

// ---------------------------------------------------------------------------
// Status badge (same as list page)
// ---------------------------------------------------------------------------

const STATUS_CONFIG: Record<string, { label: string }> = {
  pending_review: { label: "Pendente" },
  approved: { label: "Aprovado" },
  changes_requested: { label: "Alteração" },
  expired: { label: "Expirado" },
};

function StatusBadge({ status }: { status: string }) {
  const config = STATUS_CONFIG[status] ?? { label: status };
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
  if (status === "changes_requested") {
    return <Badge variant="destructive">{config.label}</Badge>;
  }
  return <Badge variant="secondary">{config.label}</Badge>;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatDateTime(iso: string): string {
  if (!iso) return "-";
  return new Date(iso).toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatFileSize(bytes: number | null): string {
  if (bytes === null || bytes === undefined) return "-";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// ---------------------------------------------------------------------------
// Approval Detail Page
// ---------------------------------------------------------------------------

export function ApprovalDetailPage() {
  const { assetId } = useParams({ strict: false }) as { assetId: string };
  const queryClient = useQueryClient();
  const canUpdate = usePermission("approvals", "update");
  const [commentText, setCommentText] = useState("");
  const [resendDialogOpen, setResendDialogOpen] = useState(false);
  const [mediaDialogUrl, setMediaDialogUrl] = useState<string | null>(null);

  // ---- Queries ----
  const {
    data: asset,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["approvals", assetId],
    queryFn: () => api.get<ApprovalAssetDetail>(`/approvals/${assetId}`),
    enabled: !!assetId,
  });

  const { data: events } = useQuery({
    queryKey: ["approvals", assetId, "events"],
    queryFn: () => api.get<Event[]>(`/approvals/${assetId}/events`),
    enabled: !!assetId,
  });

  // ---- Mutations ----
  const addCommentMutation = useMutation({
    mutationFn: (content: string) =>
      api.post<Comment>(`/approvals/${assetId}/comments`, { content }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["approvals", assetId] });
      queryClient.invalidateQueries({ queryKey: ["approvals", assetId, "events"] });
      toast.success("Comentário adicionado.");
      setCommentText("");
    },
    onError: (err: Error) => {
      toast.error(`Erro ao adicionar comentário: ${err.message}`);
    },
  });

  const resendEmailMutation = useMutation({
    mutationFn: () =>
      api.post<{ message: string }>(`/approvals/${assetId}/resend-email`, {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["approvals", assetId, "events"] });
      toast.success("Email reenviado com sucesso.");
      setResendDialogOpen(false);
    },
    onError: (err: Error) => {
      toast.error(`Erro ao reenviar email: ${err.message}`);
      setResendDialogOpen(false);
    },
  });

  function handleSubmitComment(e: React.FormEvent) {
    e.preventDefault();
    if (!commentText.trim()) return;
    addCommentMutation.mutate(commentText.trim());
  }

  async function handleViewMedia(versionId: string) {
    try {
      const result = await api.get<{ url: string }>(
        `/approvals/${assetId}/media-url/${versionId}`
      );
      setMediaDialogUrl(result.url);
    } catch {
      toast.error("Erro ao carregar mídia.");
    }
  }

  // ---- Loading ----
  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-64" />
        <div className="grid gap-6 lg:grid-cols-3">
          <div className="lg:col-span-2 space-y-4">
            <Skeleton className="h-48 w-full" />
          </div>
          <div className="space-y-4">
            <Skeleton className="h-64 w-full" />
          </div>
        </div>
      </div>
    );
  }

  // ---- Error ----
  if (error) {
    return (
      <div
        role="alert"
        className="rounded-lg border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm text-destructive"
      >
        {error instanceof Error ? error.message : "Erro ao carregar aprovação."}
      </div>
    );
  }

  if (!asset) return null;

  // ---- Render ----
  return (
    <div className="space-y-6">
      {/* Breadcrumb + Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <Link
            to="/approvals"
            className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="h-4 w-4" />
            Aprovações
          </Link>
          <span className="text-muted-foreground">/</span>
          <h1 className="text-xl font-bold tracking-tight">{asset.title}</h1>
          <StatusBadge status={asset.status} />
        </div>
        <div className="flex items-center gap-2">
          {canUpdate && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setResendDialogOpen(true)}
            >
              <Mail className="mr-1 h-4 w-4" />
              Reenviar Email
            </Button>
          )}
          <Button variant="outline" size="sm" asChild>
            <a
              href={`https://app.clickup.com/t/${asset.clickup_task_id}`}
              target="_blank"
              rel="noopener noreferrer"
            >
              <ExternalLink className="mr-1 h-4 w-4" />
              ClickUp
            </a>
          </Button>
        </div>
      </div>

      {/* Info */}
      <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
        <span>Cliente: <strong className="text-foreground">{asset.client_name}</strong></span>
        <span>Versão atual: <strong className="text-foreground">v{asset.current_version}</strong></span>
        <span>Criado em: <strong className="text-foreground">{formatDateTime(asset.created_at)}</strong></span>
      </div>

      {asset.description && (
        <p className="text-sm text-muted-foreground">{asset.description}</p>
      )}

      {/* Main grid */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Left: Media + Versions */}
        <div className="lg:col-span-2 space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Versões</CardTitle>
            </CardHeader>
            <CardContent>
              {asset.versions.length === 0 ? (
                <p className="text-sm text-muted-foreground">Nenhuma versão disponível.</p>
              ) : (
                <div className="grid gap-4 sm:grid-cols-2">
                  {asset.versions.map((v) => (
                    <div
                      key={v.id}
                      className="rounded-lg border p-3 space-y-2 cursor-pointer hover:bg-accent/50 transition-colors"
                      onClick={() => handleViewMedia(v.id)}
                    >
                      {v.thumbnail_url ? (
                        <img
                          src={v.thumbnail_url}
                          alt={`Versão ${v.version_number}`}
                          className="h-32 w-full rounded object-cover"
                        />
                      ) : (
                        <div className="flex h-32 items-center justify-center rounded bg-muted text-muted-foreground text-xs">
                          {v.file_type.toUpperCase()} / {v.file_format.toUpperCase()}
                        </div>
                      )}
                      <div className="flex items-center justify-between text-xs text-muted-foreground">
                        <span>v{v.version_number}</span>
                        <span>{formatFileSize(v.file_size_bytes)}</span>
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {formatDateTime(v.created_at)}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Decisions */}
          {asset.decisions.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Decisões</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {asset.decisions.map((d) => (
                  <div key={d.id} className="flex items-start gap-3 text-sm">
                    <Badge
                      variant={d.decision === "approved" ? "outline" : "destructive"}
                      className={d.decision === "approved" ? "bg-emerald-600 text-white border-0" : ""}
                    >
                      {d.decision === "approved" ? "Aprovado" : "Alteração"}
                    </Badge>
                    <div>
                      <p className="font-medium">{d.decided_by}</p>
                      {d.comment && <p className="text-muted-foreground">{d.comment}</p>}
                      <p className="text-xs text-muted-foreground">{formatDateTime(d.decided_at)}</p>
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}
        </div>

        {/* Right sidebar: Timeline + Comments */}
        <div className="space-y-6">
          {/* Timeline */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Timeline</CardTitle>
            </CardHeader>
            <CardContent>
              {!events || events.length === 0 ? (
                <p className="text-sm text-muted-foreground">Nenhum evento registrado.</p>
              ) : (
                <div className="space-y-3">
                  {events.map((ev) => (
                    <div key={ev.id} className="flex gap-3 text-sm">
                      <div className="mt-1 h-2 w-2 shrink-0 rounded-full bg-primary" />
                      <div>
                        <p className="font-medium">{ev.event_type}</p>
                        <p className="text-xs text-muted-foreground">
                          {ev.actor} &middot; {formatDateTime(ev.created_at)}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Comments */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <MessageSquare className="h-4 w-4" />
                Comentários ({asset.comments.length})
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {asset.comments.length === 0 && (
                <p className="text-sm text-muted-foreground">Nenhum comentário.</p>
              )}

              {asset.comments.map((c) => (
                <div key={c.id} className="space-y-1">
                  <div className="flex items-center gap-2 text-sm">
                    <span className="font-medium">{c.author_name}</span>
                    <Badge variant="secondary" className="text-xs">
                      {c.author_type}
                    </Badge>
                  </div>
                  <p className="text-sm">{c.content}</p>
                  <p className="text-xs text-muted-foreground">
                    {formatDateTime(c.created_at)}
                  </p>
                  <Separator />
                </div>
              ))}

              {/* Add comment form */}
              {canUpdate && (
                <form onSubmit={handleSubmitComment} className="space-y-2">
                  <Textarea
                    placeholder="Adicionar comentário..."
                    value={commentText}
                    onChange={(e) => setCommentText(e.target.value)}
                    rows={3}
                  />
                  <Button
                    type="submit"
                    size="sm"
                    disabled={!commentText.trim() || addCommentMutation.isPending}
                  >
                    <Send className="mr-1 h-4 w-4" />
                    {addCommentMutation.isPending ? "Enviando..." : "Enviar"}
                  </Button>
                </form>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Media dialog */}
      <Dialog open={!!mediaDialogUrl} onOpenChange={() => setMediaDialogUrl(null)}>
        <DialogContent className="max-w-4xl">
          <DialogHeader>
            <DialogTitle>Visualizar Mídia</DialogTitle>
          </DialogHeader>
          {mediaDialogUrl && (
            <div className="flex items-center justify-center">
              <img
                src={mediaDialogUrl}
                alt="Media preview"
                className="max-h-[70vh] rounded object-contain"
              />
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Resend email confirmation */}
      <Dialog open={resendDialogOpen} onOpenChange={setResendDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reenviar Email</DialogTitle>
            <DialogDescription>
              Tem certeza que deseja reenviar o email de aprovação para o cliente?
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setResendDialogOpen(false)}
              disabled={resendEmailMutation.isPending}
            >
              Cancelar
            </Button>
            <Button
              onClick={() => resendEmailMutation.mutate()}
              disabled={resendEmailMutation.isPending}
            >
              {resendEmailMutation.isPending ? "Enviando..." : "Reenviar"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
