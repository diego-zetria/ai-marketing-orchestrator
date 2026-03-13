import { useState, type FormEvent } from "react";
import { useNavigate } from "@tanstack/react-router";
import { ArrowLeft } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export function ChangePasswordPage() {
  const navigate = useNavigate();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (newPassword !== confirmPassword) {
      toast.error("As senhas não coincidem.");
      return;
    }
    if (newPassword.length < 6) {
      toast.error("A nova senha deve ter pelo menos 6 caracteres.");
      return;
    }
    setLoading(true);
    try {
      await api.post("/auth/change-password", {
        current_password: currentPassword,
        new_password: newPassword,
      });
      toast.success("Senha alterada com sucesso.");
      void navigate({ to: "/" });
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Erro ao alterar senha."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-md space-y-6">
      <Button
        variant="ghost"
        size="sm"
        onClick={() => navigate({ to: "/" })}
        className="gap-1"
      >
        <ArrowLeft className="h-4 w-4" />
        Voltar
      </Button>

      <Card>
        <CardHeader>
          <CardTitle>Alterar Senha</CardTitle>
          <CardDescription>
            Informe sua senha atual e escolha uma nova senha.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="current">Senha atual</Label>
              <Input
                id="current"
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                required
                disabled={loading}
                autoComplete="current-password"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="new">Nova senha</Label>
              <Input
                id="new"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                disabled={loading}
                autoComplete="new-password"
                minLength={6}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirm">Confirmar nova senha</Label>
              <Input
                id="confirm"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                disabled={loading}
                autoComplete="new-password"
              />
            </div>
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? "Salvando..." : "Alterar Senha"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
