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

const MIN_CHARS = 10;

interface ChangeRequestModalProps {
  open: boolean;
  onConfirm: (comment: string) => void;
  onCancel: () => void;
  loading?: boolean;
}

export function ChangeRequestModal({
  open,
  onConfirm,
  onCancel,
  loading = false,
}: ChangeRequestModalProps) {
  const [comment, setComment] = useState("");

  const trimmed = comment.trim();
  const charCount = trimmed.length;
  const isValid = charCount >= MIN_CHARS;

  function handleConfirm() {
    if (!isValid) return;
    onConfirm(trimmed);
  }

  function handleCancel() {
    setComment("");
    onCancel();
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && handleCancel()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Solicitar Alterações</DialogTitle>
          <DialogDescription>
            Descreva detalhadamente as alterações necessárias para que a equipe
            possa ajustar o conteúdo.
          </DialogDescription>
        </DialogHeader>

        <div className="py-4">
          <label
            htmlFor="change-comment"
            className="mb-2 block text-sm font-medium text-foreground"
          >
            Descrição das alterações *
          </label>
          <Textarea
            id="change-comment"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Descreva as alterações que você precisa..."
            disabled={loading}
            rows={4}
            aria-describedby="char-count"
            aria-required="true"
          />
          <p
            id="char-count"
            className={`mt-1 text-xs ${
              charCount > 0 && !isValid
                ? "text-destructive"
                : "text-muted-foreground"
            }`}
          >
            {charCount}/{MIN_CHARS} caracteres mínimos
          </p>
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
            variant="destructive"
            onClick={handleConfirm}
            disabled={loading || !isValid}
          >
            {loading ? "Enviando..." : "Enviar Solicitação"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
