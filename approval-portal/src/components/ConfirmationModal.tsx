"use client";

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

interface ConfirmationModalProps {
  open: boolean;
  onConfirm: (comment?: string) => void;
  onCancel: () => void;
  loading?: boolean;
}

export function ConfirmationModal({
  open,
  onConfirm,
  onCancel,
  loading = false,
}: ConfirmationModalProps) {
  const [comment, setComment] = useState("");

  function handleConfirm() {
    onConfirm(comment.trim() || undefined);
  }

  function handleCancel() {
    setComment("");
    onCancel();
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && handleCancel()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Confirmar Aprovação</DialogTitle>
          <DialogDescription>
            Tem certeza que deseja aprovar este conteúdo?
          </DialogDescription>
        </DialogHeader>

        <div className="py-4">
          <label
            htmlFor="approval-comment"
            className="mb-2 block text-sm font-medium text-foreground"
          >
            Comentário (opcional)
          </label>
          <Textarea
            id="approval-comment"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Adicione um comentário sobre a aprovação..."
            disabled={loading}
            rows={3}
          />
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={handleCancel}
            disabled={loading}
          >
            Cancelar
          </Button>
          <Button
            variant="success"
            onClick={handleConfirm}
            disabled={loading}
          >
            {loading ? "Aprovando..." : "Aprovar"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
