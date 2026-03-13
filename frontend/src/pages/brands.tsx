import { useState, useMemo, useCallback, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Copy, Save, FileText, Building2 } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { usePermission } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import { BlockEditor } from "@/components/block-editor";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface BrandGuideline {
  id: string;
  client_id: string | null;
  content: string;
}

interface Client {
  id: string;
  name: string;
  display_name: string;
  is_active: boolean;
}

// ---------------------------------------------------------------------------
// Sidebar Item
// ---------------------------------------------------------------------------

interface SidebarItemProps {
  label: string;
  isActive: boolean;
  onClick: () => void;
  hasGuideline?: boolean;
}

function SidebarItem({ label, isActive, onClick, hasGuideline }: SidebarItemProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "w-full text-left px-3 py-2 text-sm rounded-md transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring flex items-center justify-between gap-2",
        isActive
          ? "bg-primary text-primary-foreground"
          : "hover:bg-accent text-foreground"
      )}
    >
      <span className="truncate">{label}</span>
      {hasGuideline && (
        <span
          className={cn(
            "size-1.5 shrink-0 rounded-full",
            isActive ? "bg-primary-foreground/70" : "bg-primary/50"
          )}
          aria-label="Diretriz configurada"
        />
      )}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Loading Skeleton
// ---------------------------------------------------------------------------

function BrandsLoadingSkeleton() {
  return (
    <div className="flex gap-6 h-[calc(100vh-12rem)]">
      <div className="w-[250px] shrink-0 space-y-2 border-r pr-4">
        <Skeleton className="h-4 w-20 mb-3" />
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-9 w-full" />
        ))}
      </div>
      <div className="flex-1 space-y-4">
        <Skeleton className="h-6 w-48" />
        <Skeleton className="h-[400px] w-full" />
        <Skeleton className="h-9 w-24" />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Brands Page
// ---------------------------------------------------------------------------

export function BrandsPage() {
  const queryClient = useQueryClient();
  const canUpdate = usePermission("brands", "update");
  const [selectedClientId, setSelectedClientId] = useState<string | null>(null);
  const [editorContent, setEditorContent] = useState("");
  const [editorBaseline, setEditorBaseline] = useState("");
  const [hasInitialized, setHasInitialized] = useState<string | null | undefined>(undefined);
  const isFirstChange = useRef(true);

  // ---- Queries ----
  const {
    data: brands,
    isLoading: brandsLoading,
    error: brandsError,
  } = useQuery({
    queryKey: ["brands"],
    queryFn: () => api.get<BrandGuideline[]>("/brands"),
  });

  const {
    data: clients,
    isLoading: clientsLoading,
    error: clientsError,
  } = useQuery({
    queryKey: ["clients"],
    queryFn: () =>
      api.get<{ items: Client[]; total: number }>("/clients?per_page=200").then((r) => r.items),
  });

  // ---- Derived data ----
  const activeClients = useMemo(
    () => (clients ?? []).filter((c) => c.is_active),
    [clients]
  );

  const brandMap = useMemo(() => {
    const map = new Map<string | null, BrandGuideline>();
    if (brands) {
      for (const b of brands) {
        map.set(b.client_id, b);
      }
    }
    return map;
  }, [brands]);

  const savedContent = useMemo(() => {
    const guideline = brandMap.get(selectedClientId);
    return guideline?.content ?? "";
  }, [brandMap, selectedClientId]);

  const defaultContent = useMemo(() => {
    const guideline = brandMap.get(null);
    return guideline?.content ?? "";
  }, [brandMap]);

  // Initialize editor content when selection changes or data loads
  const initializeEditor = useCallback(
    (clientId: string | null) => {
      const guideline = brandMap.get(clientId);
      const content = guideline?.content ?? "";
      setEditorContent(content);
      setEditorBaseline(content);
      isFirstChange.current = true;
      setHasInitialized(clientId);
    },
    [brandMap]
  );

  // Sync editor when selection changes
  if (hasInitialized !== selectedClientId && !brandsLoading) {
    initializeEditor(selectedClientId);
  }

  const isDirty = editorContent !== editorBaseline;

  // Key for BlockEditor to force remount on client change
  const editorKey = `editor-${selectedClientId ?? "default"}-${hasInitialized}`;

  // ---- Mutations ----
  const saveMutation = useMutation({
    mutationFn: (content: string) => {
      if (selectedClientId === null) {
        return api.put<BrandGuideline>("/brands/default", { content });
      }
      return api.put<BrandGuideline>(`/brands/${selectedClientId}`, {
        content,
      });
    },
    onSuccess: () => {
      setEditorBaseline(editorContent);
      queryClient.invalidateQueries({ queryKey: ["brands"] });
      toast.success("Diretriz salva com sucesso.");
    },
    onError: (err: Error) => {
      toast.error(`Erro ao salvar diretriz: ${err.message}`);
    },
  });

  // ---- Handlers ----
  function handleSelectClient(clientId: string | null) {
    setSelectedClientId(clientId);
    setHasInitialized(undefined); // force re-init
  }

  function handleSave() {
    saveMutation.mutate(editorContent);
  }

  const handleEditorChange = useCallback((md: string) => {
    if (isFirstChange.current) {
      isFirstChange.current = false;
      setEditorBaseline(md);
    }
    setEditorContent(md);
  }, []);

  function handleCopyFromDefault() {
    setEditorContent(defaultContent);
    // Force BlockEditor remount with new content
    setHasInitialized(undefined);
    setTimeout(() => setHasInitialized(selectedClientId), 0);
    toast.success("Conteúdo do padrão copiado para o editor.");
  }

  const isLoading = brandsLoading || clientsLoading;
  const error = brandsError || clientsError;

  const selectedLabel =
    selectedClientId === null
      ? "Padrão (Default)"
      : activeClients.find((c) => c.id === selectedClientId)?.display_name ??
        "Cliente";

  const hasContent = editorContent.trim().length > 0 || savedContent.trim().length > 0;

  // Count clients with guidelines
  const clientsWithGuidelines = useMemo(() => {
    const set = new Set<string | null>();
    if (brands) {
      for (const b of brands) {
        if (b.content.trim().length > 0) {
          set.add(b.client_id);
        }
      }
    }
    return set;
  }, [brands]);

  // ---- Render ----
  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">
          Diretrizes de Marca
        </h1>
        <p className="mt-1 text-muted-foreground">
          Defina as diretrizes de cada marca para orientar a revisão de conteúdo feita pela IA.
        </p>
      </div>

      {/* Error state */}
      {error && (
        <div
          role="alert"
          className="rounded-lg border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm text-destructive"
        >
          {error instanceof Error
            ? error.message
            : "Erro ao carregar dados."}
        </div>
      )}

      {/* Loading */}
      {isLoading && <BrandsLoadingSkeleton />}

      {/* Main content */}
      {!isLoading && !error && (
        <div className="flex gap-6 h-[calc(100vh-12rem)]">
          {/* Left sidebar - client list */}
          <div className="w-[250px] shrink-0 border-r pr-4">
            <div className="flex items-center gap-2 mb-3">
              <Building2 className="size-3.5 text-muted-foreground" aria-hidden="true" />
              <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Clientes
              </p>
              <Badge variant="secondary" className="text-[10px] px-1.5 py-0 ml-auto">
                {activeClients.length}
              </Badge>
            </div>
            <ScrollArea className="h-[calc(100%-2rem)]">
              <div className="space-y-1 pr-2">
                <SidebarItem
                  label="Padrão (Default)"
                  isActive={selectedClientId === null}
                  onClick={() => handleSelectClient(null)}
                  hasGuideline={clientsWithGuidelines.has(null)}
                />
                {activeClients.map((client) => (
                  <SidebarItem
                    key={client.id}
                    label={client.display_name}
                    isActive={selectedClientId === client.id}
                    onClick={() => handleSelectClient(client.id)}
                    hasGuideline={clientsWithGuidelines.has(client.id)}
                  />
                ))}
              </div>
            </ScrollArea>
          </div>

          {/* Right side - editor */}
          <div className="flex-1 flex flex-col min-w-0">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <FileText
                  className="size-5 text-muted-foreground"
                  aria-hidden="true"
                />
                <h2 className="text-lg font-semibold">{selectedLabel}</h2>
                {isDirty && (
                  <Badge variant="outline" className="text-[10px] text-amber-600 border-amber-300">
                    Alterações não salvas
                  </Badge>
                )}
              </div>
              {canUpdate && (
                <div className="flex items-center gap-2">
                  {selectedClientId !== null && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleCopyFromDefault}
                      disabled={!defaultContent}
                    >
                      <Copy className="size-4" aria-hidden="true" />
                      Copiar do Default
                    </Button>
                  )}
                  <Button
                    size="sm"
                    onClick={handleSave}
                    disabled={!isDirty || saveMutation.isPending}
                  >
                    <Save className="size-4" aria-hidden="true" />
                    {saveMutation.isPending ? "Salvando..." : "Salvar"}
                  </Button>
                </div>
              )}
            </div>

            {/* Empty state for clients without guideline */}
            {selectedClientId !== null && !hasContent && (
              <div className="flex-1 flex items-center justify-center">
                <div className="text-center space-y-3">
                  <div className="flex size-12 items-center justify-center rounded-full bg-muted mx-auto">
                    <FileText className="size-6 text-muted-foreground" aria-hidden="true" />
                  </div>
                  <p className="text-muted-foreground">
                    Nenhuma diretriz definida para este cliente.
                  </p>
                  <p className="text-sm text-muted-foreground">
                    Clique em <strong>Copiar do Default</strong> para iniciar com as diretrizes padrão.
                  </p>
                </div>
              </div>
            )}

            {/* BlockNote Editor */}
            {(selectedClientId === null || hasContent) && (
              <div className="flex-1 min-h-0 rounded-md border overflow-auto">
                <BlockEditor
                  key={editorKey}
                  initialMarkdown={savedContent}
                  onChange={handleEditorChange}
                />
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
