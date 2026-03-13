import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Shield, Pencil, Trash2, UserPlus } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { usePermission } from "@/lib/auth";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
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

interface User {
  id: string;
  email: string;
  name: string;
  role_id: string;
  role_name: string;
  is_active: boolean;
  last_login: string | null;
  created_at: string;
}

interface Role {
  id: string;
  name: string;
  description: string | null;
  permissions: Record<string, string[]>;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const ROLE_COLORS: Record<string, string> = {
  admin: "bg-red-500/10 text-red-600 border-red-200",
  manager: "bg-blue-500/10 text-blue-600 border-blue-200",
  viewer: "bg-gray-500/10 text-gray-600 border-gray-200",
};

function formatDate(iso: string): string {
  if (!iso) return "-";
  return new Date(iso).toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

// ---------------------------------------------------------------------------
// Users Page
// ---------------------------------------------------------------------------

export function UsersPage() {
  const queryClient = useQueryClient();
  const canCreate = usePermission("users", "create");
  const canUpdate = usePermission("users", "update");
  const canDelete = usePermission("users", "delete");

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [deleteUser, setDeleteUser] = useState<User | null>(null);

  // Form state
  const [formName, setFormName] = useState("");
  const [formEmail, setFormEmail] = useState("");
  const [formPassword, setFormPassword] = useState("");
  const [formRoleId, setFormRoleId] = useState("");
  const [formIsActive, setFormIsActive] = useState(true);

  // Queries
  const { data: users = [], isLoading } = useQuery({
    queryKey: ["users"],
    queryFn: () => api.get<User[]>("/users"),
  });

  const { data: roles = [] } = useQuery({
    queryKey: ["roles"],
    queryFn: () => api.get<Role[]>("/roles"),
  });

  // Mutations
  const createMutation = useMutation({
    mutationFn: (data: { email: string; name: string; password: string; role_id: string }) =>
      api.post("/users", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      toast.success("Usuário criado com sucesso.");
      closeDialog();
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, ...data }: { id: string; [key: string]: unknown }) =>
      api.put(`/users/${id}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      toast.success("Usuário atualizado.");
      closeDialog();
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/users/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      toast.success("Usuário removido.");
      setDeleteUser(null);
    },
    onError: (err: Error) => toast.error(err.message),
  });

  function openCreate() {
    setEditingUser(null);
    setFormName("");
    setFormEmail("");
    setFormPassword("");
    setFormRoleId(roles[0]?.id ?? "");
    setFormIsActive(true);
    setDialogOpen(true);
  }

  function openEdit(user: User) {
    setEditingUser(user);
    setFormName(user.name);
    setFormEmail(user.email);
    setFormPassword("");
    setFormRoleId(user.role_id);
    setFormIsActive(user.is_active);
    setDialogOpen(true);
  }

  function closeDialog() {
    setDialogOpen(false);
    setEditingUser(null);
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (editingUser) {
      const data: Record<string, unknown> = {
        id: editingUser.id,
        name: formName,
        email: formEmail,
        role_id: formRoleId,
        is_active: formIsActive,
      };
      if (formPassword) data.password = formPassword;
      updateMutation.mutate(data as { id: string; [key: string]: unknown });
    } else {
      createMutation.mutate({
        name: formName,
        email: formEmail,
        password: formPassword,
        role_id: formRoleId,
      });
    }
  }

  const isPending = createMutation.isPending || updateMutation.isPending;

  // Stats
  const stats = useMemo(() => {
    const active = users.filter((u) => u.is_active).length;
    const byRole: Record<string, number> = {};
    for (const u of users) {
      byRole[u.role_name] = (byRole[u.role_name] ?? 0) + 1;
    }
    return { total: users.length, active, byRole };
  }, [users]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Usuários</h1>
          <p className="mt-1 text-muted-foreground">
            Gerencie os usuários e permissões do backoffice.
          </p>
        </div>
        {canCreate && (
          <Button onClick={openCreate}>
            <UserPlus className="mr-2 h-4 w-4" />
            Novo Usuário
          </Button>
        )}
      </div>

      {/* KPI Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Total</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.total}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Ativos</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-emerald-600">{stats.active}</div>
          </CardContent>
        </Card>
        {Object.entries(stats.byRole).map(([role, count]) => (
          <Card key={role}>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground capitalize">
                {role}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{count}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Table */}
      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Nome</TableHead>
                <TableHead>Email</TableHead>
                <TableHead>Role</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Último login</TableHead>
                <TableHead className="w-[100px]" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading && (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                    Carregando...
                  </TableCell>
                </TableRow>
              )}
              {!isLoading && users.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                    Nenhum usuário cadastrado.
                  </TableCell>
                </TableRow>
              )}
              {users.map((user) => (
                <TableRow key={user.id}>
                  <TableCell className="font-medium">{user.name}</TableCell>
                  <TableCell className="text-muted-foreground">{user.email}</TableCell>
                  <TableCell>
                    <Badge
                      variant="outline"
                      className={ROLE_COLORS[user.role_name] ?? ""}
                    >
                      <Shield className="mr-1 h-3 w-3" />
                      {user.role_name}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    {user.is_active ? (
                      <Badge className="bg-emerald-600 hover:bg-emerald-600 text-white">
                        Ativo
                      </Badge>
                    ) : (
                      <Badge variant="secondary">Inativo</Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-muted-foreground text-sm">
                    {user.last_login ? formatDate(user.last_login) : "Nunca"}
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1">
                      {canUpdate && (
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          onClick={() => openEdit(user)}
                          aria-label={`Editar ${user.name}`}
                        >
                          <Pencil className="h-3.5 w-3.5" />
                        </Button>
                      )}
                      {canDelete && (
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 text-muted-foreground hover:text-destructive"
                          onClick={() => setDeleteUser(user)}
                          aria-label={`Remover ${user.name}`}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Roles info */}
      <div>
        <h2 className="text-lg font-semibold mb-3">Roles disponíveis</h2>
        <div className="grid gap-3 sm:grid-cols-3">
          {roles.map((role) => {
            const permCount = Object.values(role.permissions)
              .flat()
              .length;
            return (
              <Card key={role.id}>
                <CardHeader className="pb-2">
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Badge
                      variant="outline"
                      className={ROLE_COLORS[role.name] ?? ""}
                    >
                      {role.name}
                    </Badge>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">
                    {role.description}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {permCount} permissões
                  </p>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>

      {/* Create/Edit dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {editingUser ? "Editar Usuário" : "Novo Usuário"}
            </DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="user-name">Nome</Label>
              <Input
                id="user-name"
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                required
                disabled={isPending}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="user-email">Email</Label>
              <Input
                id="user-email"
                type="email"
                value={formEmail}
                onChange={(e) => setFormEmail(e.target.value)}
                required
                disabled={isPending}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="user-password">
                {editingUser ? "Nova senha (deixe vazio para manter)" : "Senha"}
              </Label>
              <Input
                id="user-password"
                type="password"
                value={formPassword}
                onChange={(e) => setFormPassword(e.target.value)}
                required={!editingUser}
                disabled={isPending}
                minLength={6}
              />
            </div>
            <div className="space-y-2">
              <Label>Role</Label>
              <Select value={formRoleId} onValueChange={setFormRoleId}>
                <SelectTrigger>
                  <SelectValue placeholder="Selecione uma role" />
                </SelectTrigger>
                <SelectContent>
                  {roles.map((r) => (
                    <SelectItem key={r.id} value={r.id}>
                      {r.name} — {r.description}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {editingUser && (
              <div className="flex items-center gap-3">
                <Switch
                  id="user-active"
                  checked={formIsActive}
                  onCheckedChange={setFormIsActive}
                  disabled={isPending}
                />
                <Label htmlFor="user-active">Ativo</Label>
              </div>
            )}
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={closeDialog}
                disabled={isPending}
              >
                Cancelar
              </Button>
              <Button type="submit" disabled={isPending}>
                {isPending ? "Salvando..." : editingUser ? "Salvar" : "Criar"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Delete confirmation */}
      <AlertDialog open={!!deleteUser} onOpenChange={() => setDeleteUser(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remover usuário</AlertDialogTitle>
            <AlertDialogDescription>
              Tem certeza que deseja remover <strong>{deleteUser?.name}</strong>?
              Esta ação não pode ser desfeita.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleteMutation.isPending}>
              Cancelar
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={() => deleteUser && deleteMutation.mutate(deleteUser.id)}
              disabled={deleteMutation.isPending}
              className="bg-destructive hover:bg-destructive/90"
            >
              {deleteMutation.isPending ? "Removendo..." : "Remover"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
