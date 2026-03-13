import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Wrench, Plus, Pencil, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { usePermission } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Tool {
  id: string;
  tool_key: string;
  display_name: string;
  description: string;
  category: string;
  is_global: boolean;
  config: Record<string, unknown> | null;
}

interface ToolCreate {
  tool_key: string;
  display_name: string;
  description: string;
  category: string;
  is_global?: boolean;
  config?: Record<string, unknown>;
}

interface ToolUpdate {
  display_name?: string;
  description?: string;
  category?: string;
  is_global?: boolean;
  config?: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const CATEGORY_LABELS: Record<string, string> = {
  clickup: "ClickUp",
  telegram: "Telegram",
  pesquisa: "Pesquisa",
  conhecimento: "Conhecimento",
  outro: "Outro",
};

const CATEGORY_OPTIONS = [
  { value: "clickup", label: "ClickUp" },
  { value: "telegram", label: "Telegram" },
  { value: "pesquisa", label: "Pesquisa" },
  { value: "conhecimento", label: "Conhecimento" },
  { value: "outro", label: "Outro" },
] as const;

const EMPTY_FORM = {
  tool_key: "",
  display_name: "",
  description: "",
  category: "",
  is_global: true,
};

// ---------------------------------------------------------------------------
// Tool Form Dialog
// ---------------------------------------------------------------------------

interface ToolFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  editingTool: Tool | null;
  onSubmit: (data: ToolCreate | ToolUpdate, isEdit: boolean) => void;
  isSubmitting: boolean;
}

function ToolFormDialog({
  open,
  onOpenChange,
  editingTool,
  onSubmit,
  isSubmitting,
}: ToolFormDialogProps) {
  const isEdit = !!editingTool;

  const [form, setForm] = useState(
    editingTool
      ? {
          tool_key: editingTool.tool_key,
          display_name: editingTool.display_name,
          description: editingTool.description,
          category: editingTool.category,
          is_global: editingTool.is_global,
        }
      : { ...EMPTY_FORM }
  );

  // Reset form when dialog opens/closes or editingTool changes
  // We handle this by keying the dialog externally

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    if (!form.tool_key || !form.display_name || !form.description || !form.category) {
      toast.error("Preencha todos os campos obrigatórios.");
      return;
    }

    if (isEdit) {
      const update: ToolUpdate = {
        display_name: form.display_name,
        description: form.description,
        category: form.category,
        is_global: form.is_global,
      };
      onSubmit(update, true);
    } else {
      const create: ToolCreate = {
        tool_key: form.tool_key,
        display_name: form.display_name,
        description: form.description,
        category: form.category,
        is_global: form.is_global,
      };
      onSubmit(create, false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[480px]">
        <DialogHeader>
          <DialogTitle>
            {isEdit ? "Editar Ferramenta" : "Adicionar Ferramenta"}
          </DialogTitle>
          <DialogDescription>
            {isEdit
              ? "Atualize as informações da ferramenta."
              : "Preencha os dados para criar uma nova ferramenta."}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="tool_key">Chave da Ferramenta</Label>
            <Input
              id="tool_key"
              value={form.tool_key}
              onChange={(e) =>
                setForm((f) => ({ ...f, tool_key: e.target.value }))
              }
              placeholder="ex: clickup_create_task"
              disabled={isEdit}
              className={isEdit ? "opacity-60" : "font-mono"}
              required
            />
            {!isEdit && (
              <p className="text-xs text-muted-foreground">
                Identificador único, formato slug (ex: minha_ferramenta).
              </p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="display_name">Nome de Exibição</Label>
            <Input
              id="display_name"
              value={form.display_name}
              onChange={(e) =>
                setForm((f) => ({ ...f, display_name: e.target.value }))
              }
              placeholder="ex: Criar Tarefa ClickUp"
              required
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="description">Descrição</Label>
            <Textarea
              id="description"
              value={form.description}
              onChange={(e) =>
                setForm((f) => ({ ...f, description: e.target.value }))
              }
              placeholder="Descreva o que esta ferramenta faz..."
              rows={3}
              required
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="category">Categoria</Label>
            <Select
              value={form.category}
              onValueChange={(value) =>
                setForm((f) => ({ ...f, category: value }))
              }
            >
              <SelectTrigger id="category">
                <SelectValue placeholder="Selecione uma categoria" />
              </SelectTrigger>
              <SelectContent>
                {CATEGORY_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex items-center justify-between rounded-lg border p-3">
            <div className="space-y-0.5">
              <Label htmlFor="is_global">Ferramenta Global</Label>
              <p className="text-xs text-muted-foreground">
                Disponível para todos os agentes automaticamente.
              </p>
            </div>
            <Switch
              id="is_global"
              checked={form.is_global}
              onCheckedChange={(checked) =>
                setForm((f) => ({ ...f, is_global: checked }))
              }
            />
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Cancelar
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting
                ? "Salvando..."
                : isEdit
                  ? "Salvar Alterações"
                  : "Criar Ferramenta"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Delete Confirmation Dialog
// ---------------------------------------------------------------------------

interface DeleteDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  tool: Tool | null;
  onConfirm: () => void;
  isDeleting: boolean;
}

function DeleteConfirmDialog({
  open,
  onOpenChange,
  tool,
  onConfirm,
  isDeleting,
}: DeleteDialogProps) {
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Excluir ferramenta?</AlertDialogTitle>
          <AlertDialogDescription>
            Tem certeza que deseja excluir a ferramenta{" "}
            <strong>{tool?.display_name}</strong>? Esta ação não pode ser
            desfeita.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancelar</AlertDialogCancel>
          <AlertDialogAction
            onClick={onConfirm}
            disabled={isDeleting}
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
          >
            {isDeleting ? "Excluindo..." : "Excluir"}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

// ---------------------------------------------------------------------------
// Loading Skeleton
// ---------------------------------------------------------------------------

function ToolsLoadingSkeleton() {
  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead><Skeleton className="h-4 w-24" /></TableHead>
            <TableHead><Skeleton className="h-4 w-20" /></TableHead>
            <TableHead><Skeleton className="h-4 w-16" /></TableHead>
            <TableHead className="hidden md:table-cell"><Skeleton className="h-4 w-40" /></TableHead>
            <TableHead><Skeleton className="h-4 w-12" /></TableHead>
            <TableHead><Skeleton className="h-4 w-16" /></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {Array.from({ length: 5 }).map((_, i) => (
            <TableRow key={i}>
              <TableCell><Skeleton className="h-4 w-32" /></TableCell>
              <TableCell><Skeleton className="h-5 w-28 rounded-full" /></TableCell>
              <TableCell><Skeleton className="h-5 w-20 rounded-full" /></TableCell>
              <TableCell className="hidden md:table-cell"><Skeleton className="h-4 w-48" /></TableCell>
              <TableCell><Skeleton className="h-5 w-10" /></TableCell>
              <TableCell><Skeleton className="h-8 w-20" /></TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tools Page
// ---------------------------------------------------------------------------

export function ToolsPage() {
  const queryClient = useQueryClient();
  const canCreate = usePermission("tools", "create");
  const canUpdate = usePermission("tools", "update");
  const canDelete = usePermission("tools", "delete");

  // ---- Dialog state ----
  const [formOpen, setFormOpen] = useState(false);
  const [editingTool, setEditingTool] = useState<Tool | null>(null);
  const [deletingTool, setDeletingTool] = useState<Tool | null>(null);
  const [formKey, setFormKey] = useState(0);

  // ---- Query ----
  const {
    data: tools,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["tools"],
    queryFn: () => api.get<Tool[]>("/tools"),
  });

  // ---- Mutations ----
  const createMutation = useMutation({
    mutationFn: (data: ToolCreate) => api.post<Tool>("/tools", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tools"] });
      toast.success("Ferramenta criada com sucesso.");
      setFormOpen(false);
    },
    onError: (err: Error) => {
      toast.error(`Erro ao criar ferramenta: ${err.message}`);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({
      toolKey,
      update,
    }: {
      toolKey: string;
      update: ToolUpdate;
    }) =>
      api.put<Tool>(
        `/tools/${encodeURIComponent(toolKey)}`,
        update
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tools"] });
      toast.success("Ferramenta atualizada com sucesso.");
      setFormOpen(false);
      setEditingTool(null);
    },
    onError: (err: Error) => {
      toast.error(`Erro ao atualizar ferramenta: ${err.message}`);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (toolKey: string) =>
      api.delete<void>(`/tools/${encodeURIComponent(toolKey)}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tools"] });
      toast.success("Ferramenta excluída com sucesso.");
      setDeletingTool(null);
    },
    onError: (err: Error) => {
      toast.error(`Erro ao excluir ferramenta: ${err.message}`);
      setDeletingTool(null);
    },
  });

  // ---- Handlers ----
  function handleOpenCreate() {
    setEditingTool(null);
    setFormKey((k) => k + 1);
    setFormOpen(true);
  }

  function handleOpenEdit(tool: Tool) {
    setEditingTool(tool);
    setFormKey((k) => k + 1);
    setFormOpen(true);
  }

  function handleFormSubmit(data: ToolCreate | ToolUpdate, isEdit: boolean) {
    if (isEdit && editingTool) {
      updateMutation.mutate({
        toolKey: editingTool.tool_key,
        update: data as ToolUpdate,
      });
    } else {
      createMutation.mutate(data as ToolCreate);
    }
  }

  function handleDeleteConfirm() {
    if (deletingTool) {
      deleteMutation.mutate(deletingTool.tool_key);
    }
  }

  const isSubmitting = createMutation.isPending || updateMutation.isPending;

  // ---- Render ----
  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">
            Ferramentas IA
          </h1>
          <p className="mt-1 text-muted-foreground">
            Gerencie as ferramentas disponíveis para os agentes de IA.
          </p>
        </div>
        {canCreate && (
          <Button onClick={handleOpenCreate} className="gap-2">
            <Plus className="size-4" aria-hidden="true" />
            Adicionar Ferramenta
          </Button>
        )}
      </div>

      {/* Error state */}
      {error && (
        <div
          role="alert"
          className="rounded-lg border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm text-destructive"
        >
          {error instanceof Error
            ? error.message
            : "Erro ao carregar ferramentas."}
        </div>
      )}

      {/* Loading */}
      {isLoading && <ToolsLoadingSkeleton />}

      {/* Empty state */}
      {!isLoading && !error && tools && tools.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <div className="flex size-16 items-center justify-center rounded-full bg-muted">
            <Wrench className="size-8 text-muted-foreground" aria-hidden="true" />
          </div>
          <h3 className="mt-4 text-lg font-semibold">
            Nenhuma ferramenta cadastrada
          </h3>
          <p className="mt-1 text-sm text-muted-foreground max-w-md">
            Adicione ferramentas para que os agentes de IA possam utiliza-las em
            suas operações.
          </p>
          {canCreate && (
            <Button onClick={handleOpenCreate} variant="outline" className="mt-4 gap-2">
              <Plus className="size-4" aria-hidden="true" />
              Adicionar Ferramenta
            </Button>
          )}
        </div>
      )}

      {/* Tools table */}
      {!isLoading && tools && tools.length > 0 && (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Nome</TableHead>
                <TableHead>Chave</TableHead>
                <TableHead>Categoria</TableHead>
                <TableHead className="hidden md:table-cell">
                  Descrição
                </TableHead>
                <TableHead>Global</TableHead>
                {(canUpdate || canDelete) && (
                  <TableHead className="text-right">Ações</TableHead>
                )}
              </TableRow>
            </TableHeader>
            <TableBody>
              {tools.map((tool) => (
                <TableRow key={tool.id}>
                  <TableCell className="font-medium">
                    {tool.display_name}
                  </TableCell>
                  <TableCell>
                    <Badge variant="secondary" className="font-mono text-xs">
                      {tool.tool_key}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline">
                      {CATEGORY_LABELS[tool.category] ?? tool.category}
                    </Badge>
                  </TableCell>
                  <TableCell className="hidden md:table-cell max-w-xs truncate text-muted-foreground">
                    {tool.description}
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={tool.is_global ? "default" : "secondary"}
                      className="text-[10px] px-1.5 py-0"
                    >
                      {tool.is_global ? "Sim" : "Não"}
                    </Badge>
                  </TableCell>
                  {(canUpdate || canDelete) && (
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-1">
                        {canUpdate && (
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => handleOpenEdit(tool)}
                            aria-label={`Editar ${tool.display_name}`}
                          >
                            <Pencil className="size-4" aria-hidden="true" />
                          </Button>
                        )}
                        {canDelete && (
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => setDeletingTool(tool)}
                            aria-label={`Excluir ${tool.display_name}`}
                          >
                            <Trash2 className="size-4 text-destructive" aria-hidden="true" />
                          </Button>
                        )}
                      </div>
                    </TableCell>
                  )}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Form Dialog (create / edit) */}
      <ToolFormDialog
        key={formKey}
        open={formOpen}
        onOpenChange={(open) => {
          setFormOpen(open);
          if (!open) setEditingTool(null);
        }}
        editingTool={editingTool}
        onSubmit={handleFormSubmit}
        isSubmitting={isSubmitting}
      />

      {/* Delete Confirmation Dialog */}
      <DeleteConfirmDialog
        open={!!deletingTool}
        onOpenChange={(open) => {
          if (!open) setDeletingTool(null);
        }}
        tool={deletingTool}
        onConfirm={handleDeleteConfirm}
        isDeleting={deleteMutation.isPending}
      />
    </div>
  );
}
