import { Link, useLocation, useNavigate } from "@tanstack/react-router";
import { Breadcrumbs } from "@/components/breadcrumbs";
import {
  LayoutDashboard,
  Users,
  Building2,
  CheckSquare,
  GitBranch,
  Workflow,
  Zap,
  Bell,
  Bot,
  Wrench,
  Palette,
  Cpu,
  BookOpen,
  Settings,
  ScrollText,
  Webhook,
  ImageIcon,
  HeartPulse,
  LogOut,
  Menu,
  Sun,
  Moon,
  Monitor,
  PanelLeftClose,
  PanelLeftOpen,
  Shield,
  UserCircle,
  Key,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import {
  Sheet,
  SheetContent,
  SheetTrigger,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { CommandPalette } from "@/components/command-palette";
import { NotificationBell } from "@/components/notification-bell";
import { KeyboardShortcutsDialog } from "@/components/keyboard-shortcuts";
import { useKeyboardShortcuts } from "@/lib/use-keyboard-shortcuts";
import { useCommandPalette } from "@/lib/use-command-palette";
import { useAuth } from "@/lib/auth";
import { useTheme } from "@/lib/theme";
import { useSidebarState } from "@/lib/sidebar-state";
import { useState, useEffect, useMemo, type ReactNode } from "react";
import { cn } from "@/lib/utils";

interface NavItem {
  label: string;
  href: string;
  icon: typeof LayoutDashboard;
}

function NavLink({
  item,
  isActive,
  collapsed,
  onClick,
}: {
  item: NavItem;
  isActive: boolean;
  collapsed?: boolean;
  onClick?: () => void;
}) {
  const Icon = item.icon;

  const link = (
    <Link
      to={item.href}
      onClick={onClick}
      className={cn(
        "flex items-center rounded-lg text-sm font-medium transition-colors",
        "hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring",
        collapsed ? "justify-center px-2 py-2" : "gap-3 px-3 py-2",
        isActive
          ? "bg-sidebar-accent text-sidebar-accent-foreground"
          : "text-sidebar-foreground/70"
      )}
      aria-current={isActive ? "page" : undefined}
    >
      <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
      {!collapsed && <span>{item.label}</span>}
    </Link>
  );

  if (collapsed) {
    return (
      <Tooltip>
        <TooltipTrigger asChild>{link}</TooltipTrigger>
        <TooltipContent side="right">{item.label}</TooltipContent>
      </Tooltip>
    );
  }

  return link;
}

interface NavGroup {
  label: string;
  items: NavItem[];
}

const navGroups: NavGroup[] = [
  {
    label: "Principal",
    items: [
      { label: "Dashboard", href: "/", icon: LayoutDashboard },
      { label: "Aprovações", href: "/approvals", icon: CheckSquare },
      { label: "Media", href: "/media", icon: ImageIcon },
    ],
  },
  {
    label: "Cadastros",
    items: [
      { label: "Equipe", href: "/team", icon: Users },
      { label: "Clientes", href: "/clients", icon: Building2 },
    ],
  },
  {
    label: "Automação",
    items: [
      { label: "Regras", href: "/rules", icon: GitBranch },
      { label: "Fluxos", href: "/admin/workflows", icon: Workflow },
      { label: "Automações", href: "/admin/automations", icon: Zap },
      { label: "Notificações", href: "/notifications", icon: Bell },
    ],
  },
  {
    label: "IA",
    items: [
      { label: "Agentes", href: "/agents", icon: Bot },
      { label: "Ferramentas", href: "/tools", icon: Wrench },
      { label: "Modelos", href: "/models", icon: Cpu },
      { label: "Diretrizes", href: "/brands", icon: Palette },
      { label: "Conhecimento", href: "/knowledge", icon: BookOpen },
    ],
  },
  {
    label: "Sistema",
    items: [
      { label: "Usuários", href: "/users", icon: Shield },
      { label: "Configurações", href: "/system", icon: Settings },
      { label: "Webhooks", href: "/webhooks", icon: Webhook },
      { label: "Status", href: "/health", icon: HeartPulse },
      { label: "Atividades", href: "/activity", icon: ScrollText },
    ],
  },
];

function SidebarContent({
  collapsed,
  onNavigate,
}: {
  collapsed?: boolean;
  onNavigate?: () => void;
}) {
  const location = useLocation();

  return (
    <div className="flex h-full flex-col bg-sidebar text-sidebar-foreground">
      {/* Logo */}
      <div className={cn("flex h-14 items-center", collapsed ? "justify-center px-2" : "px-4")}>
        <Link
          to="/"
          className="flex items-center gap-2 font-semibold tracking-tight"
        >
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground text-sm font-bold">
            FK
          </div>
          {!collapsed && (
            <span className="text-lg text-sidebar-foreground">Agency Admin</span>
          )}
        </Link>
      </div>
      <Separator className="bg-sidebar-border" />

      {/* Navigation */}
      <ScrollArea className={cn("flex-1 min-h-0 py-4", collapsed ? "px-2" : "px-3")}>
        <nav className="flex flex-col gap-4" aria-label="Menu principal">
          {navGroups.map((group) => (
            <div key={group.label}>
              {!collapsed && (
                <p className="mb-1 px-3 text-xs font-semibold uppercase tracking-wider text-sidebar-foreground/40">
                  {group.label}
                </p>
              )}
              {collapsed && (
                <Separator className="mx-auto mb-2 w-6 bg-sidebar-border" />
              )}
              <div className="flex flex-col gap-0.5">
                {group.items.map((item) => {
                  const isActive =
                    item.href === "/"
                      ? location.pathname === "/" ||
                        location.pathname === "/"
                      : location.pathname.startsWith(item.href);
                  return (
                    <NavLink
                      key={item.href}
                      item={item}
                      isActive={isActive}
                      collapsed={collapsed}
                      onClick={onNavigate}
                    />
                  );
                })}
              </div>
            </div>
          ))}
        </nav>
      </ScrollArea>
    </div>
  );
}

function ThemeToggle() {
  const { theme, setTheme, resolvedTheme } = useTheme();
  const Icon = resolvedTheme === "dark" ? Moon : Sun;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="text-muted-foreground"
          aria-label="Alterar tema"
        >
          <Icon className="h-4 w-4" aria-hidden="true" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem
          onClick={() => setTheme("light")}
          className={cn(theme === "light" && "bg-accent")}
        >
          <Sun className="mr-2 h-4 w-4" /> Claro
        </DropdownMenuItem>
        <DropdownMenuItem
          onClick={() => setTheme("dark")}
          className={cn(theme === "dark" && "bg-accent")}
        >
          <Moon className="mr-2 h-4 w-4" /> Escuro
        </DropdownMenuItem>
        <DropdownMenuItem
          onClick={() => setTheme("system")}
          className={cn(theme === "system" && "bg-accent")}
        >
          <Monitor className="mr-2 h-4 w-4" /> Sistema
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export function Layout({ children }: { children: ReactNode }) {
  const { logout, user } = useAuth();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);
  const { collapsed, toggle } = useSidebarState();
  const cmdPalette = useCommandPalette();
  const shortcutCallbacks = useMemo(
    () => ({
      onToggleSidebar: toggle,
      onOpenCommandPalette: () => cmdPalette.setOpen(true),
      onNavigate: (to: string) => navigate({ to }),
    }),
    [toggle, cmdPalette, navigate]
  );
  const { showHelp, setShowHelp } = useKeyboardShortcuts(shortcutCallbacks);

  // Cmd+B to toggle sidebar
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "b") {
        e.preventDefault();
        toggle();
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [toggle]);

  const CollapseIcon = collapsed ? PanelLeftOpen : PanelLeftClose;

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* Desktop sidebar */}
      <aside
        className={cn(
          "hidden lg:flex lg:flex-col lg:border-r lg:border-sidebar-border transition-all duration-200 overflow-hidden",
          collapsed ? "lg:w-16" : "lg:w-64"
        )}
      >
        <SidebarContent collapsed={collapsed} />
        {/* Collapse toggle */}
        <div className="border-t border-sidebar-border bg-sidebar p-2">
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                onClick={toggle}
                className={cn(
                  "flex w-full items-center rounded-lg px-3 py-2 text-sm font-medium text-sidebar-foreground/50 transition-colors",
                  "hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
                  collapsed && "justify-center px-2"
                )}
                aria-label={collapsed ? "Expandir sidebar" : "Recolher sidebar"}
              >
                <CollapseIcon className="h-4 w-4 shrink-0" aria-hidden="true" />
                {!collapsed && <span className="ml-3">Recolher</span>}
              </button>
            </TooltipTrigger>
            <TooltipContent side="right" className={collapsed ? "" : "hidden"}>
              Expandir sidebar
            </TooltipContent>
          </Tooltip>
        </div>
      </aside>

      {/* Main area */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Header */}
        <header className="flex h-14 items-center gap-4 border-b px-4 lg:px-6">
          {/* Mobile menu button */}
          <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
            <SheetTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="lg:hidden"
                aria-label="Abrir menu"
              >
                <Menu className="h-5 w-5" />
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="w-64 p-0 bg-sidebar border-sidebar-border">
              <SheetTitle className="sr-only">Menu de navegação</SheetTitle>
              <SidebarContent onNavigate={() => setMobileOpen(false)} />
            </SheetContent>
          </Sheet>

          {/* Search trigger */}
          <button
            onClick={() => cmdPalette.setOpen(true)}
            className="hidden sm:flex flex-1 items-center gap-2 rounded-lg border bg-muted/50 px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-muted max-w-xs"
          >
            <span>Buscar...</span>
            <kbd className="pointer-events-none ml-auto hidden select-none rounded border bg-background px-1.5 py-0.5 font-mono text-[10px] font-medium text-muted-foreground sm:inline-block">
              ⌘K
            </kbd>
          </button>
          <div className="flex-1 sm:hidden" />

          {/* Notifications */}
          <NotificationBell />

          {/* Theme toggle */}
          <ThemeToggle />

          {/* User menu */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="sm" className="gap-2 text-muted-foreground">
                <UserCircle className="h-4 w-4" aria-hidden="true" />
                <span className="hidden sm:inline max-w-[120px] truncate">
                  {user?.name ?? "Usuário"}
                </span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              <div className="px-2 py-1.5">
                <p className="text-sm font-medium">{user?.name}</p>
                <p className="text-xs text-muted-foreground">{user?.email}</p>
                <p className="mt-0.5 text-xs text-muted-foreground capitalize">
                  <Shield className="mr-1 inline h-3 w-3" />{user?.role}
                </p>
              </div>
              <Separator />
              <DropdownMenuItem onClick={() => navigate({ to: "/change-password" })}>
                <Key className="mr-2 h-4 w-4" /> Alterar senha
              </DropdownMenuItem>
              <DropdownMenuItem onClick={logout}>
                <LogOut className="mr-2 h-4 w-4" /> Sair
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </header>

        {/* Breadcrumbs + Page content */}
        <div className="flex-1 overflow-y-auto">
          <Breadcrumbs />
          <main className="p-4 lg:p-6">
            {children}
          </main>
        </div>
      </div>

      {/* Command palette */}
      <CommandPalette open={cmdPalette.open} onOpenChange={cmdPalette.setOpen} />
      <KeyboardShortcutsDialog open={showHelp} onOpenChange={setShowHelp} />
    </div>
  );
}
