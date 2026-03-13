import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { Bell, Check, CheckCheck, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Notification {
  id: string;
  title: string;
  message: string;
  link: string | null;
  icon: string | null;
  is_read: boolean;
  created_at: string;
}

interface NotificationsResponse {
  items: Notification[];
  total: number;
  unread_count: number;
}

interface UnreadCountResponse {
  count: number;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSeconds = Math.floor(diffMs / 1000);
  const diffMinutes = Math.floor(diffSeconds / 60);
  const diffHours = Math.floor(diffMinutes / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffSeconds < 60) return "agora";
  if (diffMinutes < 60) return `${diffMinutes}min`;
  if (diffHours < 24) return `${diffHours}h`;
  if (diffDays < 7) return `${diffDays}d`;

  return date.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
}

const ICON_COLORS: Record<string, string> = {
  approval: "bg-amber-500/10 text-amber-600",
  client: "bg-blue-500/10 text-blue-600",
  alert: "bg-red-500/10 text-red-600",
  system: "bg-gray-500/10 text-gray-600",
};

function getIconClass(icon: string | null): string {
  if (!icon) return "bg-primary/10 text-primary";
  return ICON_COLORS[icon] ?? "bg-primary/10 text-primary";
}

// ---------------------------------------------------------------------------
// Notification Item
// ---------------------------------------------------------------------------

interface NotificationItemProps {
  notification: Notification;
  onRead: (id: string) => void;
  onDelete: (id: string) => void;
  onNavigate: (link: string) => void;
}

function NotificationItem({ notification, onRead, onDelete, onNavigate }: NotificationItemProps) {
  function handleClick() {
    if (!notification.is_read) {
      onRead(notification.id);
    }
    if (notification.link) {
      onNavigate(notification.link);
    }
  }

  return (
    <div
      role="button"
      tabIndex={0}
      className={cn(
        "flex items-start gap-3 px-4 py-3 transition-colors",
        notification.link ? "cursor-pointer hover:bg-accent" : "",
        !notification.is_read && "bg-primary/5"
      )}
      onClick={handleClick}
      onKeyDown={(e) => { if (e.key === "Enter") handleClick(); }}
    >
      {/* Icon dot */}
      <div className={cn("mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-bold", getIconClass(notification.icon))}>
        <Bell className="h-3.5 w-3.5" />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-2">
          <p className={cn("text-sm leading-tight", !notification.is_read && "font-semibold")}>
            {notification.title}
          </p>
          <span className="shrink-0 text-[10px] text-muted-foreground">
            {formatRelativeTime(notification.created_at)}
          </span>
        </div>
        <p className="mt-0.5 text-xs text-muted-foreground line-clamp-2">
          {notification.message}
        </p>
      </div>

      {/* Actions */}
      <div className="flex shrink-0 items-center gap-0.5">
        {!notification.is_read && (
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6"
            onClick={(e) => { e.stopPropagation(); onRead(notification.id); }}
            aria-label="Marcar como lida"
          >
            <Check className="h-3 w-3" />
          </Button>
        )}
        <Button
          variant="ghost"
          size="icon"
          className="h-6 w-6 text-muted-foreground hover:text-destructive"
          onClick={(e) => { e.stopPropagation(); onDelete(notification.id); }}
          aria-label="Remover notificação"
        >
          <Trash2 className="h-3 w-3" />
        </Button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Notification Bell
// ---------------------------------------------------------------------------

export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  // Poll unread count every 30s (lightweight endpoint)
  const { data: unreadData } = useQuery({
    queryKey: ["notifications", "unread-count"],
    queryFn: () => api.get<UnreadCountResponse>("/notifications/unread-count"),
    refetchInterval: 30_000,
  });

  // Fetch full notification list only when popover is open
  const { data: notificationsData, isLoading } = useQuery({
    queryKey: ["notifications", "list"],
    queryFn: () => api.get<NotificationsResponse>("/notifications?per_page=20"),
    enabled: open,
  });

  const unreadCount = unreadData?.count ?? 0;
  const notifications = notificationsData?.items ?? [];

  // ---- Mutations ----
  const markReadMutation = useMutation({
    mutationFn: (id: string) => api.patch(`/notifications/${id}/read`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });

  const markAllReadMutation = useMutation({
    mutationFn: () => api.patch("/notifications/mark-all-read"),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/notifications/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });

  function handleNavigate(link: string) {
    setOpen(false);
    navigate({ to: link });
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="relative text-muted-foreground"
          aria-label={`Notificações${unreadCount > 0 ? ` (${unreadCount} não lidas)` : ""}`}
        >
          <Bell className="h-4 w-4" />
          {unreadCount > 0 && (
            <Badge
              variant="destructive"
              className="absolute -right-1 -top-1 h-4 min-w-4 px-1 text-[10px] leading-none"
            >
              {unreadCount > 99 ? "99+" : unreadCount}
            </Badge>
          )}
        </Button>
      </PopoverTrigger>

      <PopoverContent className="w-96 p-0" align="end" sideOffset={8}>
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3">
          <h3 className="text-sm font-semibold">Notificações</h3>
          {unreadCount > 0 && (
            <Button
              variant="ghost"
              size="sm"
              className="h-7 gap-1 text-xs"
              onClick={() => markAllReadMutation.mutate()}
              disabled={markAllReadMutation.isPending}
            >
              <CheckCheck className="h-3 w-3" />
              Marcar todas como lidas
            </Button>
          )}
        </div>
        <Separator />

        {/* Notification list */}
        <ScrollArea className="max-h-[400px]">
          {isLoading && (
            <div className="flex items-center justify-center py-8">
              <p className="text-sm text-muted-foreground">Carregando...</p>
            </div>
          )}

          {!isLoading && notifications.length === 0 && (
            <div className="flex flex-col items-center justify-center py-8">
              <Bell className="mb-2 h-8 w-8 text-muted-foreground/40" />
              <p className="text-sm text-muted-foreground">
                Nenhuma notificação
              </p>
            </div>
          )}

          {!isLoading && notifications.length > 0 && (
            <div className="divide-y">
              {notifications.map((notification) => (
                <NotificationItem
                  key={notification.id}
                  notification={notification}
                  onRead={(id) => markReadMutation.mutate(id)}
                  onDelete={(id) => deleteMutation.mutate(id)}
                  onNavigate={handleNavigate}
                />
              ))}
            </div>
          )}
        </ScrollArea>

        {/* Footer */}
        {notifications.length > 0 && (
          <>
            <Separator />
            <div className="px-4 py-2">
              <Button
                variant="ghost"
                size="sm"
                className="w-full text-xs"
                onClick={() => { setOpen(false); navigate({ to: "/activity" }); }}
              >
                Ver todas as atividades
              </Button>
            </div>
          </>
        )}
      </PopoverContent>
    </Popover>
  );
}
