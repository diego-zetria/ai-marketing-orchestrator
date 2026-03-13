"use client";

import type { VersionResponse } from "@/lib/types";
import { cn } from "@/lib/utils";
import { FileImage, FileVideo, Clock } from "lucide-react";

interface VersionHistoryProps {
  versions: VersionResponse[];
  currentVersion: number;
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function FileIcon({ fileType }: { fileType: string }) {
  if (fileType === "video") {
    return <FileVideo className="h-4 w-4" aria-hidden="true" />;
  }
  return <FileImage className="h-4 w-4" aria-hidden="true" />;
}

export function VersionHistory({
  versions,
  currentVersion,
}: VersionHistoryProps) {
  const sorted = [...versions].sort(
    (a, b) => b.version_number - a.version_number,
  );

  return (
    <div className="rounded-lg border bg-background p-4">
      <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-foreground">
        <Clock className="h-4 w-4" aria-hidden="true" />
        Histórico de Versões
      </h2>

      {sorted.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          Nenhuma versão disponível.
        </p>
      ) : (
        <div className="space-y-2" role="list" aria-label="Versões do conteúdo">
          {sorted.map((version) => {
            const isCurrent = version.version_number === currentVersion;

            return (
              <div
                key={version.id}
                role="listitem"
                className={cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                  isCurrent
                    ? "bg-primary/10 border border-primary/20"
                    : "bg-muted/30 hover:bg-muted/50",
                )}
              >
                <FileIcon fileType={version.file_type} />

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">
                      v{version.version_number}
                    </span>
                    {isCurrent && (
                      <span className="text-xs text-primary font-medium">
                        (atual)
                      </span>
                    )}
                    <span className="text-xs text-muted-foreground uppercase">
                      {version.file_format}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    {version.uploaded_by && (
                      <span>{version.uploaded_by}</span>
                    )}
                    <span>{formatDate(version.created_at)}</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
