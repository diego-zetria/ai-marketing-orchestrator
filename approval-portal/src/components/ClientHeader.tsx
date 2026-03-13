"use client";

import type { AssetResponse, ClientResponse } from "@/lib/types";
import { StatusBadge } from "@/components/StatusBadge";
import { Badge } from "@/components/ui/badge";

interface ClientHeaderProps {
  client: ClientResponse;
  asset: AssetResponse;
}

function ClientInitials({ name }: { name: string }) {
  const initials = name
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");

  return (
    <div
      className="flex h-12 w-12 items-center justify-center rounded-full bg-primary text-primary-foreground text-lg font-bold"
      aria-hidden="true"
    >
      {initials}
    </div>
  );
}

export function ClientHeader({ client, asset }: ClientHeaderProps) {
  return (
    <header className="rounded-lg bg-secondary/50 p-4 md:p-6">
      <div className="flex items-start gap-4">
        {/* Logo or initials */}
        {client.logo_url ? (
          <img
            src={client.logo_url}
            alt={`Logo ${client.name}`}
            className="h-12 w-12 rounded-full object-cover"
          />
        ) : (
          <ClientInitials name={client.name} />
        )}

        {/* Client and asset info */}
        <div className="flex-1 min-w-0">
          <p className="text-sm text-muted-foreground">{client.name}</p>
          <h1 className="text-lg font-semibold text-foreground truncate md:text-xl">
            {asset.title}
          </h1>
          {asset.description && (
            <p className="mt-1 text-sm text-muted-foreground line-clamp-2">
              {asset.description}
            </p>
          )}
        </div>

        {/* Version and status badges */}
        <div className="flex flex-col items-end gap-2 shrink-0">
          <Badge variant="secondary">v{asset.current_version}</Badge>
          <StatusBadge status={asset.status} />
        </div>
      </div>
    </header>
  );
}
