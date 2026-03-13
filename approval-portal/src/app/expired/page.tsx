"use client";

import { Clock } from "lucide-react";

export default function ExpiredPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-md text-center">
        {/* Icon */}
        <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-muted">
          <Clock
            className="h-8 w-8 text-muted-foreground"
            aria-hidden="true"
          />
        </div>

        {/* Title */}
        <h1 className="mb-3 text-2xl font-bold text-foreground">
          Link Expirado
        </h1>

        {/* Description */}
        <p className="mb-8 text-sm leading-relaxed text-muted-foreground">
          Este link de aprovação não é mais válido. Solicite um novo link
          à equipe da Agência Agency.
        </p>

        {/* Branding */}
        <div className="border-t pt-6">
          <p className="text-xs text-muted-foreground">
            Agência Agency — Portal de Aprovação
          </p>
        </div>
      </div>
    </main>
  );
}
