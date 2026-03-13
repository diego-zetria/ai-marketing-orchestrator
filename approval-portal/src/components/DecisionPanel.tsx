"use client";

import { useState } from "react";
import type { AssetResponse } from "@/lib/types";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { ConfirmationModal } from "@/components/ConfirmationModal";
import { ChangeRequestModal } from "@/components/ChangeRequestModal";
import { Check, MessageSquareWarning } from "lucide-react";

interface DecisionPanelProps {
  assetId: string;
  onDecisionMade: (asset: AssetResponse) => void;
}

export function DecisionPanel({
  assetId,
  onDecisionMade,
}: DecisionPanelProps) {
  const [approveOpen, setApproveOpen] = useState(false);
  const [changeOpen, setChangeOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleApprove(comment?: string) {
    setLoading(true);
    setError(null);

    try {
      const result = await api.approveAsset(assetId, comment);
      setApproveOpen(false);
      setSuccess("Conteúdo aprovado com sucesso!");
      onDecisionMade(result.asset);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Erro ao aprovar. Tente novamente.",
      );
    } finally {
      setLoading(false);
    }
  }

  async function handleRequestChanges(comment: string) {
    setLoading(true);
    setError(null);

    try {
      const result = await api.requestChanges(assetId, comment);
      setChangeOpen(false);
      setSuccess("Solicitação de alterações enviada!");
      onDecisionMade(result.asset);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Erro ao solicitar alterações. Tente novamente.",
      );
    } finally {
      setLoading(false);
    }
  }

  if (success) {
    return (
      <div
        className="rounded-lg border border-success/30 bg-success/10 p-4 text-center"
        role="status"
      >
        <p className="text-sm font-medium text-success">{success}</p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border bg-background p-4">
      <h2 className="mb-3 text-sm font-semibold text-foreground">
        Sua Decisão
      </h2>

      {error && (
        <p className="mb-3 text-xs text-destructive" role="alert">
          {error}
        </p>
      )}

      <div className="flex gap-3">
        <Button
          variant="success"
          className="flex-1"
          onClick={() => setApproveOpen(true)}
          disabled={loading}
        >
          <Check className="mr-2 h-4 w-4" aria-hidden="true" />
          Aprovar
        </Button>
        <Button
          variant="destructive"
          className="flex-1"
          onClick={() => setChangeOpen(true)}
          disabled={loading}
        >
          <MessageSquareWarning className="mr-2 h-4 w-4" aria-hidden="true" />
          Solicitar Alterações
        </Button>
      </div>

      <ConfirmationModal
        open={approveOpen}
        onConfirm={handleApprove}
        onCancel={() => setApproveOpen(false)}
        loading={loading}
      />

      <ChangeRequestModal
        open={changeOpen}
        onConfirm={handleRequestChanges}
        onCancel={() => setChangeOpen(false)}
        loading={loading}
      />
    </div>
  );
}
