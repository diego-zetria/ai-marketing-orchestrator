import { useState, useMemo, useCallback, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  BookOpen,
  Upload,
  FileText,
  Plus,
  Search,
  Trash2,
  Save,
  File,
} from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { usePermission } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Skeleton } from "@/components/ui/skeleton";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import { BlockEditor } from "@/components/block-editor";
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

interface KnowledgeDocument {
  id: string;
  title: string;
  category: string;
  content: string;
  file_key: string | null;
  file_name: string | null;
  file_type: string | null;
  file_size: number | null;
  agent_access: string[];
  is_active: boolean;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const CATEGORY_LABELS: Record<string, string> = {
  marca: "Marca",
  processo: "Processo",
  referencia: "Referência",
  geral: "Geral",
};

const CATEGORY_COLORS: Record<string, string> = {
  marca: "bg-purple-100 text-purple-700",
  processo: "bg-blue-100 text-blue-700",
  referencia: "bg-amber-100 text-amber-700",
  geral: "bg-gray-100 text-gray-700",
};

const AGENT_LABELS: Record<string, string> = {
  briefing_analyzer: "Analisador de Briefing",
  schedule_generator: "Gerador de Cronograma",
  summary_generator: "Gerador de Resumo",
  content_reviewer: "Revisor de Conteúdo",
};

const AGENT_NAMES = Object.keys(AGENT_LABELS);

const CATEGORIES = Object.keys(CATEGORY_LABELS);

const ACCEPTED_FILE_TYPES =
  ".pdf,.docx,.xlsx,.pptx,.txt,.md";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function getFileIcon(fileType: string | null) {
  if (!fileType) return FileText;
  return File;
}

// ---------------------------------------------------------------------------
// Sidebar Item
// ---------------------------------------------------------------------------

interface SidebarDocItemProps {
  doc: KnowledgeDocument;
  isSelected: boolean;
  onClick: () => void;
}

function SidebarDocItem({ doc, isSelected, onClick }: SidebarDocItemProps) {
  const Icon = doc.file_name ? getFileIcon(doc.file_type) : FileText;
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "w-full text-left px-3 py-2 text-sm rounded-md transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring flex items-center gap-2",
        isSelected
          ? "bg-primary text-primary-foreground"
          : "hover:bg-accent text-foreground"
      )}
    >
      <Icon
        className={cn(
          "size-3.5 shrink-0",
          isSelected ? "text-primary-foreground/70" : "text-muted-foreground"
        )}
        aria-hidden="true"
      />
      <span className="truncate flex-1">{doc.title}</span>
      {!doc.is_active && (
        <span
          className={cn(
            "size-1.5 shrink-0 rounded-full",
            isSelected ? "bg-primary-foreground/40" : "bg-muted-foreground/40"
          )}
          aria-label="Documento inativo"
        />
      )}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Agent Checkboxes
// ---------------------------------------------------------------------------

interface AgentCheckboxGroupProps {
  selected: string[];
  onChange: (agents: string[]) => void;
  disabled?: boolean;
}

function AgentCheckboxGroup({
  selected,
  onChange,
  disabled,
}: AgentCheckboxGroupProps) {
  return (
    <div className="space-y-2">
      <Label className="text-sm font-medium">Acesso dos Agentes</Label>
      <div className="grid grid-cols-2 gap-2">
        {AGENT_NAMES.map((agent) => (
          <label
            key={agent}
            className={cn(
              "flex items-center gap-2 text-sm cursor-pointer",
              disabled && "opacity-50 cursor-not-allowed"
            )}
          >
            <Checkbox
              checked={selected.includes(agent)}
              onCheckedChange={(checked) => {
                if (disabled) return;
                if (checked) {
                  onChange([...selected, agent]);
                } else {
                  onChange(selected.filter((a) => a !== agent));
                }
              }}
              disabled={disabled}
            />
            <span>{AGENT_LABELS[agent]}</span>
          </label>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Category Select
// ---------------------------------------------------------------------------

interface CategorySelectProps {
  value: string;
  onValueChange: (value: string) => void;
  disabled?: boolean;
}

function CategorySelect({
  value,
  onValueChange,
  disabled,
}: CategorySelectProps) {
  return (
    <div className="space-y-2">
      <Label className="text-sm font-medium">Categoria</Label>
      <Select value={value} onValueChange={onValueChange} disabled={disabled}>
        <SelectTrigger className="w-full">
          <SelectValue placeholder="Selecione uma categoria" />
        </SelectTrigger>
        <SelectContent>
          {CATEGORIES.map((cat) => (
            <SelectItem key={cat} value={cat}>
              {CATEGORY_LABELS[cat]}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Upload Dialog
// ---------------------------------------------------------------------------

interface UploadDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function UploadDialog({ open, onOpenChange }: UploadDialogProps) {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState("geral");
  const [agentAccess, setAgentAccess] = useState<string[]>([]);

  const uploadMutation = useMutation({
    mutationFn: async () => {
      if (!file) throw new Error("Nenhum arquivo selecionado");
      const formData = new FormData();
      formData.append("file", file);
      formData.append("title", title);
      formData.append("category", category);
      formData.append("agent_access", JSON.stringify(agentAccess));
      return api.upload<KnowledgeDocument>("/knowledge/upload", formData);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["knowledge"] });
      toast.success("Arquivo enviado com sucesso.");
      resetAndClose();
    },
    onError: (err: Error) => {
      toast.error(`Erro ao enviar arquivo: ${err.message}`);
    },
  });

  function resetAndClose() {
    setFile(null);
    setTitle("");
    setCategory("geral");
    setAgentAccess([]);
    onOpenChange(false);
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const selected = e.target.files?.[0];
    if (selected) {
      setFile(selected);
      if (!title) {
        const nameWithoutExt = selected.name.replace(/\.[^/.]+$/, "");
        setTitle(nameWithoutExt);
      }
    }
  }

  const canSubmit = file && title.trim().length > 0 && category;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Upload de Arquivo</DialogTitle>
          <DialogDescription>
            Envie um arquivo para a base de conhecimento. Formatos aceitos: PDF,
            DOCX, XLSX, PPTX, TXT, MD.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {/* File input */}
          <div className="space-y-2">
            <Label className="text-sm font-medium">Arquivo</Label>
            <div
              className={cn(
                "border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors",
                "hover:border-primary/50 hover:bg-accent/50",
                file ? "border-primary/30 bg-primary/5" : "border-muted-foreground/25"
              )}
              onClick={() => fileInputRef.current?.click()}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  fileInputRef.current?.click();
                }
              }}
              role="button"
              tabIndex={0}
              aria-label="Selecionar arquivo para upload"
            >
              <input
                ref={fileInputRef}
                type="file"
                accept={ACCEPTED_FILE_TYPES}
                onChange={handleFileChange}
                className="hidden"
              />
              {file ? (
                <div className="flex items-center justify-center gap-2">
                  <File className="size-5 text-primary" aria-hidden="true" />
                  <span className="text-sm font-medium">{file.name}</span>
                  <Badge variant="secondary" className="text-xs">
                    {formatFileSize(file.size)}
                  </Badge>
                </div>
              ) : (
                <div className="space-y-1">
                  <Upload
                    className="size-8 mx-auto text-muted-foreground"
                    aria-hidden="true"
                  />
                  <p className="text-sm text-muted-foreground">
                    Clique para selecionar um arquivo
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Title */}
          <div className="space-y-2">
            <Label htmlFor="upload-title" className="text-sm font-medium">
              Título
            </Label>
            <Input
              id="upload-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Título do documento"
            />
          </div>

          {/* Category */}
          <CategorySelect value={category} onValueChange={setCategory} />

          {/* Agent Access */}
          <AgentCheckboxGroup
            selected={agentAccess}
            onChange={setAgentAccess}
          />
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={resetAndClose}>
            Cancelar
          </Button>
          <Button
            onClick={() => uploadMutation.mutate()}
            disabled={!canSubmit || uploadMutation.isPending}
          >
            <Upload className="size-4" aria-hidden="true" />
            {uploadMutation.isPending ? "Enviando..." : "Enviar"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Create Text Document Dialog
// ---------------------------------------------------------------------------

interface CreateDocDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function CreateDocDialog({ open, onOpenChange }: CreateDocDialogProps) {
  const queryClient = useQueryClient();
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState("geral");
  const [content, setContent] = useState("");
  const [agentAccess, setAgentAccess] = useState<string[]>([]);

  const createMutation = useMutation({
    mutationFn: () =>
      api.post<KnowledgeDocument>("/knowledge", {
        title,
        category,
        content,
        agent_access: agentAccess,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["knowledge"] });
      toast.success("Documento criado com sucesso.");
      resetAndClose();
    },
    onError: (err: Error) => {
      toast.error(`Erro ao criar documento: ${err.message}`);
    },
  });

  function resetAndClose() {
    setTitle("");
    setCategory("geral");
    setContent("");
    setAgentAccess([]);
    onOpenChange(false);
  }

  const canSubmit = title.trim().length > 0 && category;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Criar Documento</DialogTitle>
          <DialogDescription>
            Crie um documento de texto para a base de conhecimento.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {/* Title */}
          <div className="space-y-2">
            <Label htmlFor="create-title" className="text-sm font-medium">
              Título
            </Label>
            <Input
              id="create-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Título do documento"
            />
          </div>

          {/* Category */}
          <CategorySelect value={category} onValueChange={setCategory} />

          {/* Agent Access */}
          <AgentCheckboxGroup
            selected={agentAccess}
            onChange={setAgentAccess}
          />

          {/* Content */}
          <div className="space-y-2">
            <Label htmlFor="create-content" className="text-sm font-medium">
              Conteúdo
            </Label>
            <Textarea
              id="create-content"
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="Conteúdo do documento em texto ou Markdown..."
              rows={10}
              className="font-mono text-sm"
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={resetAndClose}>
            Cancelar
          </Button>
          <Button
            onClick={() => createMutation.mutate()}
            disabled={!canSubmit || createMutation.isPending}
          >
            <Plus className="size-4" aria-hidden="true" />
            {createMutation.isPending ? "Criando..." : "Criar"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Loading Skeleton
// ---------------------------------------------------------------------------

function KnowledgeLoadingSkeleton() {
  return (
    <div className="flex gap-6 h-[calc(100vh-14rem)]">
      <div className="w-[280px] shrink-0 space-y-2 border-r pr-4">
        <Skeleton className="h-9 w-full mb-3" />
        <Skeleton className="h-4 w-20 mb-2" />
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-9 w-full" />
        ))}
        <Skeleton className="h-4 w-20 mt-4 mb-2" />
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-9 w-full" />
        ))}
      </div>
      <div className="flex-1 space-y-4">
        <Skeleton className="h-9 w-64" />
        <Skeleton className="h-9 w-48" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-[300px] w-full" />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Empty State
// ---------------------------------------------------------------------------

interface EmptyStateProps {
  onUpload: () => void;
  onCreateText: () => void;
}

function EmptyState({ onUpload, onCreateText }: EmptyStateProps) {
  return (
    <div className="flex flex-1 items-center justify-center h-[calc(100vh-14rem)]">
      <div className="text-center space-y-4">
        <div className="flex size-16 items-center justify-center rounded-full bg-muted mx-auto">
          <BookOpen
            className="size-8 text-muted-foreground"
            aria-hidden="true"
          />
        </div>
        <div className="space-y-1">
          <h3 className="text-lg font-semibold">
            Nenhum documento na base de conhecimento
          </h3>
          <p className="text-sm text-muted-foreground max-w-md">
            Faça upload de um arquivo ou crie um documento de texto para
            começar. Os documentos são injetados no contexto dos agentes de IA.
          </p>
        </div>
        <div className="flex items-center justify-center gap-3">
          <Button variant="outline" onClick={onUpload}>
            <Upload className="size-4" aria-hidden="true" />
            Upload Arquivo
          </Button>
          <Button onClick={onCreateText}>
            <Plus className="size-4" aria-hidden="true" />
            Criar Documento
          </Button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Detail Panel - No Selection
// ---------------------------------------------------------------------------

function DetailPanelEmpty() {
  return (
    <div className="flex-1 flex items-center justify-center">
      <div className="text-center space-y-2">
        <FileText
          className="size-10 mx-auto text-muted-foreground/50"
          aria-hidden="true"
        />
        <p className="text-sm text-muted-foreground">
          Selecione um documento na lista para visualizar e editar.
        </p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Detail Panel
// ---------------------------------------------------------------------------

interface DetailPanelProps {
  doc: KnowledgeDocument;
  canUpdate?: boolean;
  canDelete?: boolean;
}

function DetailPanel({ doc, canUpdate: canUpdateProp, canDelete: canDeleteProp }: DetailPanelProps) {
  const queryClient = useQueryClient();
  const [editTitle, setEditTitle] = useState(doc.title);
  const [editCategory, setEditCategory] = useState(doc.category);
  const [editAgentAccess, setEditAgentAccess] = useState<string[]>(
    doc.agent_access
  );
  const [editIsActive, setEditIsActive] = useState(doc.is_active);
  const [editedContent, setEditedContent] = useState(doc.content);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);

  // Track initialization to detect external doc changes
  const initializedDocId = useRef(doc.id);
  if (initializedDocId.current !== doc.id) {
    initializedDocId.current = doc.id;
    setEditTitle(doc.title);
    setEditCategory(doc.category);
    setEditAgentAccess(doc.agent_access);
    setEditIsActive(doc.is_active);
    setEditedContent(doc.content);
  }

  const isDirty =
    editTitle !== doc.title ||
    editCategory !== doc.category ||
    editedContent !== doc.content ||
    editIsActive !== doc.is_active ||
    JSON.stringify(editAgentAccess.slice().sort()) !==
      JSON.stringify(doc.agent_access.slice().sort());

  const updateMutation = useMutation({
    mutationFn: () =>
      api.put<KnowledgeDocument>(`/knowledge/${doc.id}`, {
        title: editTitle,
        category: editCategory,
        content: editedContent,
        agent_access: editAgentAccess,
        is_active: editIsActive,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["knowledge"] });
      toast.success("Documento atualizado com sucesso.");
    },
    onError: (err: Error) => {
      toast.error(`Erro ao atualizar documento: ${err.message}`);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => api.delete<void>(`/knowledge/${doc.id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["knowledge"] });
      toast.success("Documento excluído com sucesso.");
    },
    onError: (err: Error) => {
      toast.error(`Erro ao excluir documento: ${err.message}`);
    },
  });

  const handleEditorChange = useCallback((md: string) => {
    setEditedContent(md);
  }, []);

  return (
    <div className="flex-1 flex flex-col min-w-0">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 mb-4">
        <div className="flex-1 min-w-0 space-y-3">
          {/* Title */}
          <div className="space-y-1">
            <Label htmlFor="detail-title" className="text-xs text-muted-foreground">
              Título
            </Label>
            <Input
              id="detail-title"
              value={editTitle}
              onChange={(e) => setEditTitle(e.target.value)}
              className="text-lg font-semibold h-auto py-1.5"
            />
          </div>

          {/* Category + File Info + Active */}
          <div className="flex items-center gap-3 flex-wrap">
            <Select
              value={editCategory}
              onValueChange={setEditCategory}
            >
              <SelectTrigger className="w-auto" size="sm">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {CATEGORIES.map((cat) => (
                  <SelectItem key={cat} value={cat}>
                    {CATEGORY_LABELS[cat]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            {doc.file_name && (
              <Badge variant="secondary" className="gap-1 text-xs">
                <File className="size-3" aria-hidden="true" />
                {doc.file_name}
                {doc.file_size != null && (
                  <span className="text-muted-foreground ml-1">
                    ({formatFileSize(doc.file_size)})
                  </span>
                )}
              </Badge>
            )}

            <label className="flex items-center gap-2 text-sm cursor-pointer ml-auto">
              <Checkbox
                checked={editIsActive}
                onCheckedChange={(checked) =>
                  setEditIsActive(checked === true)
                }
              />
              <span>Ativo</span>
            </label>
          </div>
        </div>
      </div>

      <Separator className="mb-4" />

      {/* Agent Access */}
      <div className="mb-4">
        <AgentCheckboxGroup
          selected={editAgentAccess}
          onChange={setEditAgentAccess}
        />
      </div>

      <Separator className="mb-4" />

      {/* Content Editor */}
      <div className="flex-1 min-h-0 space-y-2">
        <Label className="text-sm font-medium">Conteúdo</Label>
        <div className="flex-1 min-h-0 rounded-md border overflow-auto h-[calc(100%-6rem)]">
          <BlockEditor
            key={`doc-${doc.id}`}
            initialMarkdown={doc.content}
            onChange={handleEditorChange}
          />
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center justify-between pt-4">
        {canDeleteProp && (
          <Button
            variant="destructive"
            size="sm"
            onClick={() => setShowDeleteDialog(true)}
            disabled={deleteMutation.isPending}
          >
            <Trash2 className="size-4" aria-hidden="true" />
            {deleteMutation.isPending ? "Excluindo..." : "Excluir"}
          </Button>
        )}
        {!canDeleteProp && <div />}

        {canUpdateProp && (
          <div className="flex items-center gap-2">
            {isDirty && (
              <Badge
                variant="outline"
                className="text-[10px] text-amber-600 border-amber-300"
              >
                Alterações não salvas
              </Badge>
            )}
            <Button
              size="sm"
              onClick={() => updateMutation.mutate()}
              disabled={!isDirty || updateMutation.isPending}
            >
              <Save className="size-4" aria-hidden="true" />
              {updateMutation.isPending ? "Salvando..." : "Salvar"}
            </Button>
          </div>
        )}
      </div>

      {/* Delete Confirmation */}
      <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Excluir documento</AlertDialogTitle>
            <AlertDialogDescription>
              Tem certeza que deseja excluir &quot;{doc.title}&quot;? Esta ação
              não pode ser desfeita.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              onClick={() => deleteMutation.mutate()}
            >
              Excluir
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Knowledge Page
// ---------------------------------------------------------------------------

export function KnowledgePage() {
  const canCreate = usePermission("knowledge", "create");
  const canUpdate = usePermission("knowledge", "update");
  const canDelete = usePermission("knowledge", "delete");
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);

  // ---- Queries ----
  const {
    data: documents,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["knowledge"],
    queryFn: () => api.get<KnowledgeDocument[]>("/knowledge"),
  });

  // ---- Derived data ----
  const filteredDocs = useMemo(() => {
    if (!documents) return [];
    if (!searchQuery.trim()) return documents;
    const q = searchQuery.toLowerCase();
    return documents.filter((doc) => doc.title.toLowerCase().includes(q));
  }, [documents, searchQuery]);

  const groupedDocs = useMemo(() => {
    const groups: Record<string, KnowledgeDocument[]> = {};
    for (const cat of CATEGORIES) {
      groups[cat] = [];
    }
    for (const doc of filteredDocs) {
      const cat = doc.category in CATEGORY_LABELS ? doc.category : "geral";
      groups[cat].push(doc);
    }
    // Remove empty groups
    const result: Record<string, KnowledgeDocument[]> = {};
    for (const [cat, docs] of Object.entries(groups)) {
      if (docs.length > 0) {
        result[cat] = docs;
      }
    }
    return result;
  }, [filteredDocs]);

  const selectedDoc = useMemo(
    () => documents?.find((d) => d.id === selectedDocId) ?? null,
    [documents, selectedDocId]
  );

  // If the selected doc was deleted, clear selection
  if (selectedDocId && documents && !selectedDoc) {
    setSelectedDocId(null);
  }

  const totalDocs = documents?.length ?? 0;
  const categoryCount = useMemo(() => {
    if (!documents) return 0;
    const cats = new Set(documents.map((d) => d.category));
    return cats.size;
  }, [documents]);

  // ---- Render ----
  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">
          Base de Conhecimento
        </h1>
        <p className="mt-1 text-muted-foreground">
          Gerencie os documentos injetados no contexto dos agentes de IA.
        </p>

        {/* Stats bar + actions */}
        <div className="flex items-center justify-between mt-4">
          <div className="flex items-center gap-3">
            <Badge variant="secondary" className="gap-1">
              <FileText className="size-3" aria-hidden="true" />
              {totalDocs} {totalDocs === 1 ? "documento" : "documentos"}
            </Badge>
            <Badge variant="secondary" className="gap-1">
              <BookOpen className="size-3" aria-hidden="true" />
              {categoryCount}{" "}
              {categoryCount === 1 ? "categoria" : "categorias"}
            </Badge>
          </div>
          {canCreate && (
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setUploadDialogOpen(true)}
              >
                <Upload className="size-4" aria-hidden="true" />
                Upload Arquivo
              </Button>
              <Button size="sm" onClick={() => setCreateDialogOpen(true)}>
                <Plus className="size-4" aria-hidden="true" />
                Criar Documento
              </Button>
            </div>
          )}
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
            : "Erro ao carregar documentos."}
        </div>
      )}

      {/* Loading */}
      {isLoading && <KnowledgeLoadingSkeleton />}

      {/* Empty state */}
      {!isLoading && !error && documents && documents.length === 0 && (
        <EmptyState
          onUpload={() => setUploadDialogOpen(true)}
          onCreateText={() => setCreateDialogOpen(true)}
        />
      )}

      {/* Main content */}
      {!isLoading && !error && documents && documents.length > 0 && (
        <div className="flex gap-6 h-[calc(100vh-14rem)]">
          {/* Left sidebar - document list */}
          <div className="w-[280px] shrink-0 border-r pr-4 flex flex-col">
            {/* Search */}
            <div className="relative mb-3">
              <Search
                className="absolute left-2.5 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground"
                aria-hidden="true"
              />
              <Input
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Buscar documentos..."
                className="pl-8 h-8 text-sm"
                aria-label="Buscar documentos por título"
              />
            </div>

            <ScrollArea className="flex-1">
              <div className="space-y-4 pr-2">
                {Object.entries(groupedDocs).map(([category, docs]) => (
                  <div key={category}>
                    {/* Category header */}
                    <div className="flex items-center gap-2 mb-1.5">
                      <Badge
                        className={cn(
                          "text-[10px] px-1.5 py-0 font-medium border-0",
                          CATEGORY_COLORS[category] ?? CATEGORY_COLORS.geral
                        )}
                      >
                        {CATEGORY_LABELS[category] ?? category}
                      </Badge>
                      <span className="text-[10px] text-muted-foreground">
                        {docs.length}
                      </span>
                    </div>
                    {/* Document items */}
                    <div className="space-y-0.5">
                      {docs.map((doc) => (
                        <SidebarDocItem
                          key={doc.id}
                          doc={doc}
                          isSelected={doc.id === selectedDocId}
                          onClick={() => setSelectedDocId(doc.id)}
                        />
                      ))}
                    </div>
                  </div>
                ))}

                {filteredDocs.length === 0 && searchQuery && (
                  <p className="text-sm text-muted-foreground text-center py-4">
                    Nenhum documento encontrado.
                  </p>
                )}
              </div>
            </ScrollArea>
          </div>

          {/* Right side - detail */}
          {selectedDoc ? (
            <DetailPanel doc={selectedDoc} canUpdate={canUpdate} canDelete={canDelete} />
          ) : (
            <DetailPanelEmpty />
          )}
        </div>
      )}

      {/* Dialogs */}
      <UploadDialog
        open={uploadDialogOpen}
        onOpenChange={setUploadDialogOpen}
      />
      <CreateDocDialog
        open={createDialogOpen}
        onOpenChange={setCreateDialogOpen}
      />
    </div>
  );
}
