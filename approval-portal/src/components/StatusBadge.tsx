"use client";

import type { AssetStatus } from "@/lib/types";
import { Badge } from "@/components/ui/badge";

interface StatusBadgeProps {
  status: AssetStatus;
}

const STATUS_CONFIG: Record<
  string,
  { label: string; variant: "warning" | "success" | "destructive" }
> = {
  pending: {
    label: "Aguardando Revisão",
    variant: "warning",
  },
  pending_review: {
    label: "Aguardando Revisão",
    variant: "warning",
  },
  approved: {
    label: "Aprovado",
    variant: "success",
  },
  changes_requested: {
    label: "Alterações Solicitadas",
    variant: "destructive",
  },
};

const DEFAULT_CONFIG = { label: "Pendente", variant: "warning" as const };

export function StatusBadge({ status }: StatusBadgeProps) {
  const config = STATUS_CONFIG[status] ?? DEFAULT_CONFIG;

  return (
    <Badge variant={config.variant} aria-label={`Status: ${config.label}`}>
      {config.label}
    </Badge>
  );
}
