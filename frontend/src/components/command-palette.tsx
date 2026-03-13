import { useCallback } from "react";
import { useNavigate } from "@tanstack/react-router";
import {
  LayoutDashboard,
  Users,
  Building2,
  CheckSquare,
  GitBranch,
  Bell,
  Bot,
  Wrench,
  Palette,
  Cpu,
  BookOpen,
  Settings,
  ScrollText,
  Plus,
  Download,
  Moon,
  Sun,
} from "lucide-react";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command";
import { useTheme } from "@/lib/theme";
import { exportToCsv, csvFilename } from "@/lib/export";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface CommandAction {
  label: string;
  icon: typeof LayoutDashboard;
  onSelect: () => void;
  keywords?: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function CommandPalette({ open, onOpenChange }: CommandPaletteProps) {
  const navigate = useNavigate();
  const { setTheme } = useTheme();

  const go = useCallback(
    (to: string) => {
      navigate({ to });
      onOpenChange(false);
    },
    [navigate, onOpenChange]
  );

  const navItems: CommandAction[] = [
    { label: "Dashboard", icon: LayoutDashboard, onSelect: () => go("/"), keywords: "inicio home" },
    { label: "Aprovações", icon: CheckSquare, onSelect: () => go("/approvals"), keywords: "approval assets" },
    { label: "Equipe", icon: Users, onSelect: () => go("/team"), keywords: "team membros" },
    { label: "Clientes", icon: Building2, onSelect: () => go("/clients"), keywords: "clients empresas" },
    { label: "Regras", icon: GitBranch, onSelect: () => go("/rules"), keywords: "rules atribuição" },
    { label: "Notificações", icon: Bell, onSelect: () => go("/notifications"), keywords: "notifications alertas" },
    { label: "Agentes IA", icon: Bot, onSelect: () => go("/agents"), keywords: "agents ai" },
    { label: "Ferramentas IA", icon: Wrench, onSelect: () => go("/tools"), keywords: "tools ai" },
    { label: "Modelos IA", icon: Cpu, onSelect: () => go("/models"), keywords: "models ai" },
    { label: "Diretrizes", icon: Palette, onSelect: () => go("/brands"), keywords: "brands marca" },
    { label: "Conhecimento", icon: BookOpen, onSelect: () => go("/knowledge"), keywords: "knowledge base" },
    { label: "Configurações", icon: Settings, onSelect: () => go("/system"), keywords: "system config" },
    { label: "Atividades", icon: ScrollText, onSelect: () => go("/activity"), keywords: "activity log" },
  ];

  const quickActions: CommandAction[] = [
    {
      label: "Novo Cliente",
      icon: Plus,
      keywords: "add criar cliente",
      onSelect: () => {
        go("/clients");
        // The page will open, user clicks "Adicionar Cliente"
      },
    },
    {
      label: "Novo Membro",
      icon: Plus,
      keywords: "add criar membro equipe",
      onSelect: () => {
        go("/team");
      },
    },
    {
      label: "Exportar Clientes CSV",
      icon: Download,
      keywords: "export download",
      onSelect: () => {
        // Trigger empty CSV with just headers as a shortcut — real data export is on the page
        exportToCsv(
          [],
          [{ header: "Nome", accessor: () => "" }],
          csvFilename("clientes")
        );
        onOpenChange(false);
      },
    },
  ];

  const themeActions: CommandAction[] = [
    {
      label: "Tema Claro",
      icon: Sun,
      keywords: "light theme",
      onSelect: () => { setTheme("light"); onOpenChange(false); },
    },
    {
      label: "Tema Escuro",
      icon: Moon,
      keywords: "dark theme",
      onSelect: () => { setTheme("dark"); onOpenChange(false); },
    },
  ];

  return (
    <CommandDialog open={open} onOpenChange={onOpenChange}>
      <CommandInput placeholder="Buscar páginas, ações..." />
      <CommandList>
        <CommandEmpty>Nenhum resultado encontrado.</CommandEmpty>

        <CommandGroup heading="Navegação">
          {navItems.map((item) => (
            <CommandItem
              key={item.label}
              onSelect={item.onSelect}
              keywords={item.keywords ? [item.keywords] : undefined}
            >
              <item.icon className="mr-2 h-4 w-4" />
              {item.label}
            </CommandItem>
          ))}
        </CommandGroup>

        <CommandSeparator />

        <CommandGroup heading="Ações Rápidas">
          {quickActions.map((item) => (
            <CommandItem
              key={item.label}
              onSelect={item.onSelect}
              keywords={item.keywords ? [item.keywords] : undefined}
            >
              <item.icon className="mr-2 h-4 w-4" />
              {item.label}
            </CommandItem>
          ))}
        </CommandGroup>

        <CommandSeparator />

        <CommandGroup heading="Tema">
          {themeActions.map((item) => (
            <CommandItem
              key={item.label}
              onSelect={item.onSelect}
              keywords={item.keywords ? [item.keywords] : undefined}
            >
              <item.icon className="mr-2 h-4 w-4" />
              {item.label}
            </CommandItem>
          ))}
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}
