import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface ShortcutEntry {
  keys: string[];
  description: string;
}

interface ShortcutGroup {
  label: string;
  shortcuts: ShortcutEntry[];
}

const shortcutGroups: ShortcutGroup[] = [
  {
    label: "Geral",
    shortcuts: [
      { keys: ["⌘", "K"], description: "Abrir busca rápida" },
      { keys: ["⌘", "B"], description: "Recolher/expandir sidebar" },
      { keys: ["?"], description: "Mostrar atalhos de teclado" },
      { keys: ["Esc"], description: "Fechar diálogo" },
    ],
  },
  {
    label: "Navegação",
    shortcuts: [
      { keys: ["G", "D"], description: "Ir para Dashboard" },
      { keys: ["G", "A"], description: "Ir para Aprovações" },
      { keys: ["G", "E"], description: "Ir para Equipe" },
      { keys: ["G", "C"], description: "Ir para Clientes" },
    ],
  },
];

function Kbd({ children }: { children: string }) {
  return (
    <kbd className="inline-flex h-5 min-w-5 items-center justify-center rounded border bg-muted px-1 font-mono text-[11px] font-medium text-muted-foreground">
      {children}
    </kbd>
  );
}

export function KeyboardShortcutsDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Atalhos de Teclado</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          {shortcutGroups.map((group) => (
            <div key={group.label}>
              <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                {group.label}
              </p>
              <div className="space-y-1.5">
                {group.shortcuts.map((shortcut) => (
                  <div
                    key={shortcut.description}
                    className="flex items-center justify-between py-1"
                  >
                    <span className="text-sm">{shortcut.description}</span>
                    <div className="flex items-center gap-1">
                      {shortcut.keys.map((key, i) => (
                        <span key={i} className="flex items-center gap-0.5">
                          {i > 0 && (
                            <span className="text-xs text-muted-foreground">+</span>
                          )}
                          <Kbd>{key}</Kbd>
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}
