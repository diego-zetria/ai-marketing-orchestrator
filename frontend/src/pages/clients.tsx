import { useState, useMemo, useCallback, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Pencil, Trash2, Plus, Mail, Phone, Hash, X, ImageIcon, Download } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { usePermission } from "@/lib/auth";
import { exportToCsv, csvFilename } from "@/lib/export";
import { DataTable, type ColumnDef, type SortingState } from "@/components/data-table";
import { DataTableFilters, type ActiveFilters, type FilterDefinition } from "@/components/data-table-filters";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
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

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Client {
  id: string;
  name: string;
  display_name: string;
  slug: string | null;
  clickup_list_id: string | null;
  designer_id: string | null;
  account_id: string | null;
  workflow_id: string | null;
  email: string | null;
  whatsapp_phone: string | null;
  logo_url: string | null;
  is_active: boolean;
}

interface ClientCreate {
  name: string;
  display_name: string;
  slug?: string | null;
  clickup_list_id?: string | null;
  designer_id?: string | null;
  account_id?: string | null;
  workflow_id?: string | null;
  email?: string | null;
  whatsapp_phone?: string | null;
  logo_url?: string | null;
}

interface ClientUpdate {
  display_name?: string | null;
  slug?: string | null;
  clickup_list_id?: string | null;
  designer_id?: string | null;
  account_id?: string | null;
  workflow_id?: string | null;
  email?: string | null;
  whatsapp_phone?: string | null;
  logo_url?: string | null;
  is_active?: boolean | null;
}

interface PaginatedClients {
  items: Client[];
  total: number;
  page: number;
  per_page: number;
}

interface TeamMember {
  id: string;
  clickup_user_id: string | null;
  name: string;
  role: string | null;
  telegram_chat_id: number;
  active: boolean;
}

interface Workflow {
  id: string;
  name: string;
  display_name: string;
  is_default: boolean;
  is_active: boolean;
}

// ---------------------------------------------------------------------------
// Constants & Validation
// ---------------------------------------------------------------------------

const NONE_SENTINEL = "__none__";

function toSlug(text: string): string {
  return text
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function stripNonDigits(value: string): string {
  return value.replace(/\D/g, "");
}

function formatPhonePreview(ddi: string, number: string): string {
  if (!number) return "";
  if (number.length < 3) return `+${ddi} ${number}`;
  const dd = number.slice(0, 2);
  const rest = number.slice(2);
  if (rest.length <= 5) return `+${ddi} (${dd}) ${rest}`;
  return `+${ddi} (${dd}) ${rest.slice(0, 5)}-${rest.slice(5)}`;
}

type FieldErrors = Record<string, string | undefined>;

function validateEmail(value: string): string | undefined {
  if (!value) return undefined;
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) return "E-mail invalido";
  return undefined;
}

function validateDdi(value: string): string | undefined {
  if (!value) return "DDI obrigatorio";
  if (value.length < 1 || value.length > 4) return "DDI invalido";
  return undefined;
}

function validatePhoneNumber(value: string, ddi: string): string | undefined {
  if (!value) return undefined;
  if (ddi === "55") {
    if (value.length < 10 || value.length > 11) return "DDD + numero: 10-11 digitos (ex: 41999887766)";
  } else {
    if (value.length < 6 || value.length > 15) return "Numero invalido (6-15 digitos)";
  }
  return undefined;
}

function FieldError({ message }: { message?: string }) {
  if (!message) return null;
  return <p className="text-xs text-destructive">{message}</p>;
}

// ---------------------------------------------------------------------------
// Client Form Dialog
// ---------------------------------------------------------------------------

interface ClientFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  client: Client | null;
  designers: TeamMember[];
  accounts: TeamMember[];
  workflows: Workflow[];
  onSubmit: (data: ClientCreate | ClientUpdate) => void;
  onLogoChanged: () => void;
  isPending: boolean;
}

function ClientFormDialog({
  open,
  onOpenChange,
  client,
  designers,
  accounts,
  workflows,
  onSubmit,
  onLogoChanged,
  isPending,
}: ClientFormDialogProps) {
  const isEditing = client !== null;
  const [name, setName] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [slug, setSlug] = useState("");
  const [slugTouched, setSlugTouched] = useState(false);
  const [clickupListId, setClickupListId] = useState("");
  const [designerId, setDesignerId] = useState<string>(NONE_SENTINEL);
  const [accountId, setAccountId] = useState<string>(NONE_SENTINEL);
  const [workflowId, setWorkflowId] = useState<string>(NONE_SENTINEL);
  const [email, setEmail] = useState("");
  const [whatsappDdi, setWhatsappDdi] = useState("55");
  const [whatsappNumber, setWhatsappNumber] = useState("");
  const [errors, setErrors] = useState<FieldErrors>({});
  const [touched, setTouched] = useState<Record<string, boolean>>({});

  const markTouched = useCallback((field: string) => {
    setTouched((prev) => ({ ...prev, [field]: true }));
  }, []);

  function validateAll(): FieldErrors {
    return {
      email: validateEmail(email),
      whatsappDdi: whatsappNumber ? validateDdi(whatsappDdi) : undefined,
      whatsappNumber: validatePhoneNumber(whatsappNumber, whatsappDdi),
    };
  }

  function handleNameChange(value: string) {
    setName(value);
    if (!slugTouched && !isEditing) {
      setSlug(toSlug(value));
    }
  }

  function handleSlugChange(value: string) {
    setSlugTouched(true);
    setSlug(toSlug(value));
  }

  function handleDdiChange(value: string) {
    const digits = stripNonDigits(value).slice(0, 4);
    setWhatsappDdi(digits);
    if (touched.whatsappNumber) {
      setErrors((prev) => ({ ...prev, whatsappDdi: validateDdi(digits) }));
    }
  }

  function handlePhoneNumberChange(value: string) {
    const digits = stripNonDigits(value).slice(0, 11);
    setWhatsappNumber(digits);
    if (touched.whatsappNumber) {
      setErrors((prev) => ({ ...prev, whatsappNumber: validatePhoneNumber(digits, whatsappDdi) }));
    }
  }

  function handleEmailChange(value: string) {
    setEmail(value);
    if (touched.email) {
      setErrors((prev) => ({ ...prev, email: validateEmail(value) }));
    }
  }

  function handleOpenChange(next: boolean) {
    if (next && client) {
      setName(client.name);
      setDisplayName(client.display_name);
      setSlug(client.slug ?? "");
      setSlugTouched(true);
      setClickupListId(client.clickup_list_id ?? "");
      setDesignerId(client.designer_id ?? NONE_SENTINEL);
      setAccountId(client.account_id ?? NONE_SENTINEL);
      setWorkflowId(client.workflow_id ?? NONE_SENTINEL);
      setEmail(client.email ?? "");
      if (client.whatsapp_phone) {
        // Split stored E.164 (e.g. "5541999887766") into DDI + local number
        // Try common DDI lengths: 1-3 digits. Default to 55 (Brazil) for 12-13 digit numbers.
        const ph = client.whatsapp_phone;
        if (ph.startsWith("55") && ph.length >= 12) {
          setWhatsappDdi("55");
          setWhatsappNumber(ph.slice(2));
        } else {
          // Fallback: first 2 digits as DDI
          setWhatsappDdi(ph.slice(0, 2));
          setWhatsappNumber(ph.slice(2));
        }
      } else {
        setWhatsappDdi("55");
        setWhatsappNumber("");
      }
    } else if (next) {
      setName("");
      setDisplayName("");
      setSlug("");
      setSlugTouched(false);
      setClickupListId("");
      setDesignerId(NONE_SENTINEL);
      setAccountId(NONE_SENTINEL);
      setWorkflowId(NONE_SENTINEL);
      setEmail("");
      setWhatsappDdi("55");
      setWhatsappNumber("");
    }
    setErrors({});
    setTouched({});
    onOpenChange(next);
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    const errs = validateAll();
    setErrors(errs);
    const hasErrors = Object.values(errs).some(Boolean);
    if (hasErrors) {
      setTouched({ email: true, whatsappNumber: true });
      return;
    }

    const designerValue = designerId === NONE_SENTINEL ? null : designerId;
    const accountValue = accountId === NONE_SENTINEL ? null : accountId;
    const workflowValue = workflowId === NONE_SENTINEL ? null : workflowId;
    const fullPhone = whatsappNumber ? `${whatsappDdi}${whatsappNumber}` : null;

    if (isEditing) {
      const update: ClientUpdate = {
        display_name: displayName || null,
        slug: slug || null,
        clickup_list_id: clickupListId || null,
        designer_id: designerValue,
        account_id: accountValue,
        workflow_id: workflowValue,
        email: email || null,
        whatsapp_phone: fullPhone,
        logo_url: undefined,
      };
      onSubmit(update);
    } else {
      const create: ClientCreate = {
        name,
        display_name: displayName,
        slug: slug || null,
        clickup_list_id: clickupListId || null,
        designer_id: designerValue,
        account_id: accountValue,
        workflow_id: workflowValue,
        email: email || null,
        whatsapp_phone: fullPhone,
        logo_url: undefined,
      };
      onSubmit(create);
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>
            {isEditing ? "Editar Cliente" : "Adicionar Cliente"}
          </DialogTitle>
          <DialogDescription>
            {isEditing
              ? "Atualize as informações do cliente."
              : "Preencha os dados para adicionar um novo cliente."}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-5">
          {/* --- Identificação --- */}
          <fieldset className="space-y-3">
            <legend className="text-sm font-medium text-muted-foreground">
              Identificação
            </legend>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label htmlFor="client-name">Nome *</Label>
                <Input
                  id="client-name"
                  value={name}
                  onChange={(e) => handleNameChange(e.target.value)}
                  placeholder="client_alpha"
                  required
                  disabled={isEditing}
                  autoFocus={!isEditing}
                  aria-describedby={isEditing ? "client-name-hint" : undefined}
                />
                {isEditing && (
                  <p id="client-name-hint" className="text-xs text-muted-foreground">
                    Não editável.
                  </p>
                )}
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="client-display-name">Display Name *</Label>
                <Input
                  id="client-display-name"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  placeholder="ClientAlpha"
                  required
                  autoFocus={isEditing}
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="client-slug">Slug</Label>
              <div className="relative">
                <Hash className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  id="client-slug"
                  className="pl-8"
                  value={slug}
                  onChange={(e) => handleSlugChange(e.target.value)}
                  placeholder="auto-gerado do nome"
                />
              </div>
              <p className="text-xs text-muted-foreground">
                Usado em URLs e paths S3. Gerado automaticamente do nome.
              </p>
            </div>
          </fieldset>

          <Separator />

          {/* --- Contato --- */}
          <fieldset className="space-y-3">
            <legend className="text-sm font-medium text-muted-foreground">
              Contato
            </legend>

            <div className="space-y-1.5">
              <Label htmlFor="client-email">E-mail</Label>
              <div className="relative">
                <Mail className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  id="client-email"
                  type="email"
                  className={`pl-8 ${errors.email && touched.email ? "border-destructive" : ""}`}
                  value={email}
                  onChange={(e) => handleEmailChange(e.target.value)}
                  onBlur={() => { markTouched("email"); setErrors((p) => ({ ...p, email: validateEmail(email) })); }}
                  placeholder="cliente@empresa.com"
                />
              </div>
              <FieldError message={touched.email ? errors.email : undefined} />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="client-whatsapp-number">WhatsApp</Label>
              <div className="flex gap-2">
                <div className="relative w-20 shrink-0">
                  <span className="absolute left-2.5 top-2.5 text-sm text-muted-foreground select-none">+</span>
                  <Input
                    id="client-whatsapp-ddi"
                    className={`pl-6 font-mono text-center ${errors.whatsappDdi && touched.whatsappNumber ? "border-destructive" : ""}`}
                    value={whatsappDdi}
                    onChange={(e) => handleDdiChange(e.target.value)}
                    placeholder="55"
                    inputMode="numeric"
                    aria-label="DDI"
                  />
                </div>
                <div className="relative flex-1">
                  <Phone className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    id="client-whatsapp-number"
                    className={`pl-8 font-mono ${errors.whatsappNumber && touched.whatsappNumber ? "border-destructive" : ""}`}
                    value={whatsappNumber}
                    onChange={(e) => handlePhoneNumberChange(e.target.value)}
                    onBlur={() => { markTouched("whatsappNumber"); setErrors((p) => ({ ...p, whatsappNumber: validatePhoneNumber(whatsappNumber, whatsappDdi), whatsappDdi: whatsappNumber ? validateDdi(whatsappDdi) : undefined })); }}
                    placeholder="41999887766"
                    inputMode="numeric"
                  />
                </div>
              </div>
              {whatsappNumber && !errors.whatsappNumber && (
                <p className="text-xs text-muted-foreground">
                  {formatPhonePreview(whatsappDdi, whatsappNumber)}
                </p>
              )}
              <FieldError message={touched.whatsappNumber ? (errors.whatsappDdi || errors.whatsappNumber) : undefined} />
            </div>
          </fieldset>

          <Separator />

          {/* --- Equipe --- */}
          <fieldset className="space-y-3">
            <legend className="text-sm font-medium text-muted-foreground">
              Equipe
            </legend>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label htmlFor="client-designer">Designer</Label>
                <Select value={designerId} onValueChange={setDesignerId}>
                  <SelectTrigger id="client-designer" className="w-full">
                    <SelectValue placeholder="Selecione" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={NONE_SENTINEL}>Nenhum</SelectItem>
                    {designers.map((d) => (
                      <SelectItem key={d.id} value={d.id}>
                        {d.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="client-account">Atendimento</Label>
                <Select value={accountId} onValueChange={setAccountId}>
                  <SelectTrigger id="client-account" className="w-full">
                    <SelectValue placeholder="Selecione" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={NONE_SENTINEL}>Nenhum</SelectItem>
                    {accounts.map((a) => (
                      <SelectItem key={a.id} value={a.id}>
                        {a.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </fieldset>

          <Separator />

          {/* --- Integrações --- */}
          <fieldset className="space-y-3">
            <legend className="text-sm font-medium text-muted-foreground">
              Integrações
            </legend>

            <div className="space-y-1.5">
              <Label htmlFor="client-clickup-list-id">ClickUp List ID</Label>
              <Input
                id="client-clickup-list-id"
                value={clickupListId}
                onChange={(e) => setClickupListId(e.target.value)}
                placeholder="901702813254"
                inputMode="numeric"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="client-workflow">Workflow</Label>
              <Select value={workflowId} onValueChange={setWorkflowId}>
                <SelectTrigger id="client-workflow" className="w-full">
                  <SelectValue placeholder="Selecione" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={NONE_SENTINEL}>Padrao</SelectItem>
                  {workflows.map((w) => (
                    <SelectItem key={w.id} value={w.id}>
                      {w.display_name}{w.is_default ? " (Padrao)" : ""}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                Fluxo de status usado para este cliente. Quando vazio, usa o fluxo padrao.
              </p>
            </div>
          </fieldset>

          {isEditing && client && (
            <>
              <Separator />
              <LogoUpload
                clientId={client.id}
                hasLogo={!!client.logo_url}
                onUploaded={onLogoChanged}
              />
            </>
          )}

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={isPending}
            >
              Cancelar
            </Button>
            <Button type="submit" disabled={isPending}>
              {isPending ? "Salvando..." : isEditing ? "Salvar" : "Adicionar"}
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
  clientName: string;
  onConfirm: () => void;
  isPending: boolean;
}

function DeleteClientDialog({
  open,
  onOpenChange,
  clientName,
  onConfirm,
  isPending,
}: DeleteDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Remover Cliente</DialogTitle>
          <DialogDescription>
            Tem certeza que deseja remover <strong>{clientName}</strong>? Essa
            ação não pode ser desfeita.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={isPending}
          >
            Cancelar
          </Button>
          <Button
            variant="destructive"
            onClick={onConfirm}
            disabled={isPending}
          >
            {isPending ? "Removendo..." : "Remover"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Logo Thumbnail (table inline)
// ---------------------------------------------------------------------------

function ClientLogoThumb({ clientId, hasLogo }: { clientId: string; hasLogo: boolean }) {
  const { data } = useQuery({
    queryKey: ["client-logo", clientId],
    queryFn: () => api.get<{ url: string }>(`/clients/${clientId}/logo-url?size=thumb`),
    enabled: hasLogo,
    staleTime: 5 * 60 * 1000,
  });

  const src = hasLogo ? data?.url ?? null : null;

  if (!src) {
    return (
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-muted">
        <ImageIcon className="h-3.5 w-3.5 text-muted-foreground" />
      </div>
    );
  }

  return (
    <img
      src={src}
      alt="Logo"
      className="h-8 w-8 shrink-0 rounded-md object-contain bg-muted"
    />
  );
}

// ---------------------------------------------------------------------------
// Logo Upload Component
// ---------------------------------------------------------------------------

const LOGO_MAX_SIZE = 5 * 1024 * 1024;
const LOGO_ACCEPTED = "image/jpeg,image/png,image/webp,image/gif";

interface LogoUploadProps {
  clientId: string;
  hasLogo: boolean;
  onUploaded: () => void;
}

function LogoUpload({ clientId, hasLogo, onUploaded }: LogoUploadProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [localPreview, setLocalPreview] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const { data: logoData } = useQuery({
    queryKey: ["client-logo", clientId, "edit"],
    queryFn: () => api.get<{ url: string }>(`/clients/${clientId}/logo-url?size=original`),
    enabled: hasLogo,
    staleTime: 5 * 60 * 1000,
  });

  const preview = localPreview ?? (hasLogo ? logoData?.url ?? null : null);

  function validateFile(file: File): string | null {
    if (!file.type.startsWith("image/")) return "Selecione uma imagem.";
    if (!LOGO_ACCEPTED.includes(file.type)) return "Use JPEG, PNG, WebP ou GIF.";
    if (file.size > LOGO_MAX_SIZE) return `Maximo ${LOGO_MAX_SIZE / (1024 * 1024)}MB. Arquivo: ${(file.size / (1024 * 1024)).toFixed(1)}MB.`;
    return null;
  }

  async function handleFile(file: File) {
    const err = validateFile(file);
    if (err) { toast.error(err); return; }

    // Show instant local preview
    const localUrl = URL.createObjectURL(file);
    setLocalPreview(localUrl);

    setUploading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      await api.upload<Client>(`/clients/${clientId}/logo`, form);
      toast.success("Logo atualizada.");
      onUploaded();
    } catch (e) {
      toast.error(`Erro no upload: ${e instanceof Error ? e.message : "erro desconhecido"}`);
      setLocalPreview(null);
    } finally {
      setUploading(false);
      URL.revokeObjectURL(localUrl);
    }
  }

  async function handleDelete() {
    setDeleting(true);
    try {
      await api.delete(`/clients/${clientId}/logo`);
      setLocalPreview(null);
      toast.success("Logo removida.");
      onUploaded();
    } catch (e) {
      toast.error(`Erro ao remover: ${e instanceof Error ? e.message : "erro desconhecido"}`);
    } finally {
      setDeleting(false);
    }
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }

  function onDragOver(e: React.DragEvent) {
    e.preventDefault();
    setDragging(true);
  }

  return (
    <div className="space-y-2">
      <Label>Logo</Label>
      <div
        role="button"
        tabIndex={0}
        className={`relative flex items-center gap-4 rounded-lg border-2 border-dashed p-4 transition-colors cursor-pointer
          ${dragging ? "border-primary bg-primary/5" : "border-muted-foreground/25 hover:border-muted-foreground/50"}
          ${uploading ? "pointer-events-none opacity-60" : ""}`}
        onClick={() => fileInputRef.current?.click()}
        onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") fileInputRef.current?.click(); }}
        onDrop={onDrop}
        onDragOver={onDragOver}
        onDragLeave={() => setDragging(false)}
      >
        {preview ? (
          <img
            src={preview}
            alt="Logo preview"
            className="h-14 w-14 rounded-md object-contain bg-muted"
          />
        ) : (
          <div className="flex h-14 w-14 items-center justify-center rounded-md bg-muted">
            <ImageIcon className="h-6 w-6 text-muted-foreground" />
          </div>
        )}

        <div className="flex-1 min-w-0">
          {uploading ? (
            <p className="text-sm text-muted-foreground">Enviando...</p>
          ) : (
            <>
              <p className="text-sm font-medium">
                {preview ? "Trocar logo" : "Adicionar logo"}
              </p>
              <p className="text-xs text-muted-foreground">
                Arraste ou clique. JPEG, PNG, WebP, GIF. Max 5MB.
              </p>
            </>
          )}
        </div>

        {preview && !uploading && (
          <Button
            type="button"
            variant="ghost"
            size="icon-xs"
            className="shrink-0"
            disabled={deleting}
            onClick={(e) => { e.stopPropagation(); handleDelete(); }}
            aria-label="Remover logo"
          >
            <X className="h-4 w-4 text-destructive" />
          </Button>
        )}

        <input
          ref={fileInputRef}
          type="file"
          accept={LOGO_ACCEPTED}
          className="hidden"
          onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); e.target.value = ""; }}
        />

        {uploading && (
          <div className="absolute inset-x-0 bottom-0 h-1 overflow-hidden rounded-b-lg">
            <div className="h-full w-full animate-pulse bg-primary/40" />
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Clients Page
// ---------------------------------------------------------------------------

export function ClientsPage() {
  const queryClient = useQueryClient();
  const canCreate = usePermission("clients", "create");
  const canUpdate = usePermission("clients", "update");
  const canDelete = usePermission("clients", "delete");
  const [formOpen, setFormOpen] = useState(false);
  const [editingClient, setEditingClient] = useState<Client | null>(null);
  const [deletingClient, setDeletingClient] = useState<Client | null>(null);

  // ---- Server-side table state ----
  const [pageIndex, setPageIndex] = useState(0);
  const [pageSize, setPageSize] = useState(10);
  const [sorting, setSorting] = useState<SortingState>([]);
  const [search, setSearch] = useState("");
  const [activeFilters, setActiveFilters] = useState<ActiveFilters>({});

  const sortBy = sorting[0]?.id ?? "name";
  const sortOrder = sorting[0]?.desc ? "desc" : "asc";

  // ---- Queries ----
  const {
    data: clientsData,
    isLoading: clientsLoading,
    error: clientsError,
  } = useQuery({
    queryKey: ["clients", { page: pageIndex + 1, per_page: pageSize, sort_by: sortBy, sort_order: sortOrder, search, filters: activeFilters }],
    queryFn: () => {
      const params = new URLSearchParams();
      params.set("page", String(pageIndex + 1));
      params.set("per_page", String(pageSize));
      if (sortBy) params.set("sort_by", sortBy);
      params.set("sort_order", sortOrder);
      if (search) params.set("search", search);
      // Filters
      if (activeFilters.is_active?.length) {
        params.set("is_active", activeFilters.is_active[0]);
      }
      if (activeFilters.designer_id?.length) {
        for (const v of activeFilters.designer_id) params.append("designer_id", v);
      }
      if (activeFilters.account_id?.length) {
        for (const v of activeFilters.account_id) params.append("account_id", v);
      }
      return api.get<PaginatedClients>(`/clients?${params.toString()}`);
    },
  });

  const clients = clientsData?.items ?? [];
  const totalRows = clientsData?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(totalRows / pageSize));

  const { data: teamMembers } = useQuery({
    queryKey: ["team-members", "all"],
    queryFn: () =>
      api.get<{ items: TeamMember[]; total: number }>("/team-members?per_page=200").then((r) => r.items),
  });

  const { data: workflows } = useQuery({
    queryKey: ["workflows"],
    queryFn: () => api.get<Workflow[]>("/workflows"),
  });

  // ---- Derived data ----
  const memberMap = useMemo(() => {
    const map = new Map<string, string>();
    if (teamMembers) {
      for (const m of teamMembers) {
        map.set(m.id, m.name);
      }
    }
    return map;
  }, [teamMembers]);

  const designers = useMemo(
    () =>
      (teamMembers ?? []).filter(
        (m) => m.role === "designer" && m.active
      ),
    [teamMembers]
  );

  const accounts = useMemo(
    () =>
      (teamMembers ?? []).filter(
        (m) => m.role === "account" && m.active
      ),
    [teamMembers]
  );

  // ---- Filter definitions ----
  const filterDefs = useMemo<FilterDefinition[]>(() => {
    const defs: FilterDefinition[] = [
      {
        id: "is_active",
        label: "Status",
        options: [
          { value: "true", label: "Ativo" },
          { value: "false", label: "Inativo" },
        ],
      },
    ];
    if (designers.length > 0) {
      defs.push({
        id: "designer_id",
        label: "Designer",
        options: designers.map((d) => ({ value: d.id, label: d.name })),
      });
    }
    if (accounts.length > 0) {
      defs.push({
        id: "account_id",
        label: "Atendimento",
        options: accounts.map((a) => ({ value: a.id, label: a.name })),
      });
    }
    return defs;
  }, [designers, accounts]);

  function handleFiltersChange(filters: ActiveFilters) {
    setActiveFilters(filters);
    setPageIndex(0);
  }

  function resolveMemberName(id: string | null): string {
    if (!id) return "-";
    return memberMap.get(id) ?? "-";
  }

  // ---- Columns ----
  const columns = useMemo<ColumnDef<Client, unknown>[]>(
    () => [
      {
        accessorKey: "name",
        header: "Nome",
        cell: ({ row }) => {
          const client = row.original;
          return (
            <div className="flex items-center gap-2.5">
              <ClientLogoThumb clientId={client.id} hasLogo={!!client.logo_url} />
              <div>
                <span className="font-medium">{client.display_name}</span>
                <span className="ml-2 text-xs text-muted-foreground">{client.slug ?? client.name}</span>
              </div>
            </div>
          );
        },
      },
      {
        accessorKey: "email",
        header: "E-mail",
        enableSorting: false,
        cell: ({ getValue }) => {
          const val = getValue() as string | null;
          return val ?? <span className="text-muted-foreground">-</span>;
        },
      },
      {
        accessorKey: "whatsapp_phone",
        header: "WhatsApp",
        enableSorting: false,
        cell: ({ getValue }) => {
          const val = getValue() as string | null;
          return val ? (
            <span className="font-mono text-xs">{val}</span>
          ) : (
            <span className="text-muted-foreground">-</span>
          );
        },
      },
      {
        id: "designer",
        header: "Designer",
        enableSorting: false,
        cell: ({ row }) => resolveMemberName(row.original.designer_id),
      },
      {
        id: "account",
        header: "Atendimento",
        enableSorting: false,
        cell: ({ row }) => resolveMemberName(row.original.account_id),
      },
      {
        accessorKey: "is_active",
        header: "Ativo",
        cell: ({ getValue }) => {
          const active = getValue() as boolean;
          return active ? (
            <Badge className="bg-emerald-600 hover:bg-emerald-600 text-white">Ativo</Badge>
          ) : (
            <Badge variant="destructive">Inativo</Badge>
          );
        },
      },
      ...((canUpdate || canDelete) ? [{
        id: "actions",
        header: "",
        enableSorting: false,
        size: 80,
        cell: ({ row }: { row: { original: Client } }) => {
          const client = row.original;
          return (
            <div className="flex items-center gap-1">
              {canUpdate && (
                <Button
                  variant="ghost"
                  size="icon-xs"
                  onClick={() => handleEdit(client)}
                  aria-label={`Editar ${client.display_name}`}
                >
                  <Pencil aria-hidden="true" />
                </Button>
              )}
              {canDelete && (
                <Button
                  variant="ghost"
                  size="icon-xs"
                  onClick={() => setDeletingClient(client)}
                  aria-label={`Remover ${client.display_name}`}
                >
                  <Trash2 className="text-destructive" aria-hidden="true" />
                </Button>
              )}
            </div>
          );
        },
      }] as ColumnDef<Client, unknown>[] : []),
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [memberMap, canUpdate, canDelete]
  );

  // ---- Mutations ----
  const createMutation = useMutation({
    mutationFn: (data: ClientCreate) =>
      api.post<Client>("/clients", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["clients"] });
      toast.success("Cliente adicionado com sucesso.");
      setFormOpen(false);
    },
    onError: (err: Error) => {
      toast.error(`Erro ao adicionar cliente: ${err.message}`);
    },
  });

  const updateMutation = useMutation({
    mutationFn: (data: ClientUpdate & { id: string }) => {
      const { id, ...body } = data;
      return api.put<Client>(`/clients/${id}`, body);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["clients"] });
      toast.success("Cliente atualizado com sucesso.");
      setFormOpen(false);
      setEditingClient(null);
    },
    onError: (err: Error) => {
      toast.error(`Erro ao atualizar cliente: ${err.message}`);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) =>
      api.delete<{ message: string }>(`/clients/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["clients"] });
      toast.success("Cliente removido com sucesso.");
      setDeletingClient(null);
    },
    onError: (err: Error) => {
      toast.error(`Erro ao remover cliente: ${err.message}`);
    },
  });

  // ---- Handlers ----
  function handleAdd() {
    setEditingClient(null);
    setFormOpen(true);
  }

  function handleEdit(client: Client) {
    setEditingClient(client);
    setFormOpen(true);
  }

  function handleFormSubmit(data: ClientCreate | ClientUpdate) {
    if (editingClient) {
      updateMutation.mutate({ ...data, id: editingClient.id });
    } else {
      createMutation.mutate(data as ClientCreate);
    }
  }

  function handleDeleteConfirm() {
    if (deletingClient) {
      deleteMutation.mutate(deletingClient.id);
    }
  }

  const isMutating = createMutation.isPending || updateMutation.isPending;

  // ---- Render ----
  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Clientes</h1>
          <p className="mt-1 text-muted-foreground">
            Gerenciamento dos clientes da agência.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {totalRows > 0 && (
            <Button
              variant="outline"
              onClick={() =>
                exportToCsv(
                  clients,
                  [
                    { header: "Nome", accessor: (c) => c.display_name },
                    { header: "Slug", accessor: (c) => c.slug },
                    { header: "E-mail", accessor: (c) => c.email },
                    { header: "WhatsApp", accessor: (c) => c.whatsapp_phone },
                    { header: "Designer", accessor: (c) => resolveMemberName(c.designer_id) },
                    { header: "Atendimento", accessor: (c) => resolveMemberName(c.account_id) },
                    { header: "ClickUp List ID", accessor: (c) => c.clickup_list_id },
                    { header: "Ativo", accessor: (c) => (c.is_active ? "Sim" : "Não") },
                  ],
                  csvFilename("clientes")
                )
              }
            >
              <Download aria-hidden="true" />
              Exportar CSV
            </Button>
          )}
          {canCreate && (
            <Button onClick={handleAdd}>
              <Plus aria-hidden="true" />
              Adicionar Cliente
            </Button>
          )}
        </div>
      </div>

      {/* Error state */}
      {clientsError && (
        <div
          role="alert"
          className="rounded-lg border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm text-destructive"
        >
          {clientsError instanceof Error
            ? clientsError.message
            : "Erro ao carregar clientes."}
        </div>
      )}

      {/* Filters */}
      {filterDefs.length > 0 && (
        <DataTableFilters
          filters={filterDefs}
          activeFilters={activeFilters}
          onFiltersChange={handleFiltersChange}
        />
      )}

      {/* Data table */}
      <DataTable
        columns={columns}
        data={clients}
        manualPagination
        manualSorting
        pageCount={pageCount}
        pageIndex={pageIndex}
        pageSize={pageSize}
        onPaginationChange={({ pageIndex: pi, pageSize: ps }) => {
          setPageIndex(pi);
          setPageSize(ps);
        }}
        sorting={sorting}
        onSortingChange={setSorting}
        searchValue={search}
        onSearchChange={(v) => { setSearch(v); setPageIndex(0); }}
        searchPlaceholder="Buscar clientes..."
        isLoading={clientsLoading}
        emptyMessage="Nenhum cliente encontrado."
        totalRows={totalRows}
      />

      {/* Form dialog (add / edit) */}
      <ClientFormDialog
        open={formOpen}
        onOpenChange={(open) => {
          setFormOpen(open);
          if (!open) setEditingClient(null);
        }}
        client={editingClient}
        designers={designers}
        accounts={accounts}
        workflows={(workflows ?? []).filter((w) => w.is_active)}
        onSubmit={handleFormSubmit}
        onLogoChanged={() => queryClient.invalidateQueries({ queryKey: ["clients"] })}
        isPending={isMutating}
      />

      {/* Delete confirmation */}
      <DeleteClientDialog
        open={deletingClient !== null}
        onOpenChange={(open) => {
          if (!open) setDeletingClient(null);
        }}
        clientName={deletingClient?.display_name ?? ""}
        onConfirm={handleDeleteConfirm}
        isPending={deleteMutation.isPending}
      />
    </div>
  );
}
