"use client";

import { useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import type { AssetDetailResponse } from "@/lib/types";
import { api, ApiError } from "@/lib/api";
import { setToken } from "@/lib/auth";
import { ReviewPage } from "@/components/ReviewPage";
import { Skeleton } from "@/components/ui/skeleton";

type PageState =
  | { kind: "loading" }
  | { kind: "ready"; data: AssetDetailResponse }
  | { kind: "error"; message: string };

export function ReviewTokenClient() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [state, setState] = useState<PageState>({ kind: "loading" });

  useEffect(() => {
    const token = searchParams.get("token");
    if (!token) {
      router.replace("/expired");
      return;
    }

    let cancelled = false;

    async function validate() {
      try {
        const response = await api.validateToken(token!);
        if (cancelled) return;

        // Store JWT for subsequent API calls
        setToken(response.jwt);

        setState({ kind: "ready", data: response.asset });
      } catch (err) {
        if (cancelled) return;

        if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
          router.replace("/expired");
          return;
        }

        setState({
          kind: "error",
          message:
            err instanceof Error
              ? err.message
              : "Erro ao carregar conteúdo. Tente novamente.",
        });
      }
    }

    validate();

    return () => {
      cancelled = true;
    };
  }, [searchParams, router]);

  if (state.kind === "loading") {
    return <LoadingSkeleton />;
  }

  if (state.kind === "error") {
    return (
      <div className="flex min-h-screen items-center justify-center px-4">
        <div className="text-center">
          <h1 className="mb-2 text-lg font-semibold text-foreground">
            Erro ao Carregar
          </h1>
          <p className="text-sm text-muted-foreground">{state.message}</p>
        </div>
      </div>
    );
  }

  return <ReviewPage data={state.data} />;
}

function LoadingSkeleton() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-6 md:px-6 lg:px-8">
      {/* Header skeleton */}
      <div className="rounded-lg bg-secondary/50 p-4 md:p-6">
        <div className="flex items-start gap-4">
          <Skeleton className="h-12 w-12 rounded-full" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-4 w-32" />
            <Skeleton className="h-6 w-64" />
          </div>
          <div className="flex flex-col items-end gap-2">
            <Skeleton className="h-5 w-12 rounded-full" />
            <Skeleton className="h-5 w-32 rounded-full" />
          </div>
        </div>
      </div>

      {/* Content skeleton */}
      <div className="mt-6 grid grid-cols-1 gap-6 md:grid-cols-5">
        {/* Media area */}
        <div className="md:col-span-3">
          <Skeleton className="h-96 w-full rounded-lg" />
        </div>

        {/* Side panel */}
        <div className="space-y-4 md:col-span-2">
          <Skeleton className="h-40 w-full rounded-lg" />
          <Skeleton className="h-24 w-full rounded-lg" />
          <Skeleton className="h-48 w-full rounded-lg" />
        </div>
      </div>
    </div>
  );
}
