"use client";

import { useState, useCallback } from "react";
import type {
  AssetDetailResponse,
  AssetResponse,
  CommentResponse,
} from "@/lib/types";
import { ClientHeader } from "@/components/ClientHeader";
import { MediaViewer } from "@/components/MediaViewer";
import { VersionHistory } from "@/components/VersionHistory";
import { DecisionPanel } from "@/components/DecisionPanel";
import { CommentSection } from "@/components/CommentSection";

interface ReviewPageProps {
  data: AssetDetailResponse;
}

export function ReviewPage({ data }: ReviewPageProps) {
  const [asset, setAsset] = useState<AssetResponse>(data.asset);
  const [comments, setComments] = useState<CommentResponse[]>(data.comments);

  const handleDecisionMade = useCallback((updatedAsset: AssetResponse) => {
    setAsset(updatedAsset);
  }, []);

  const handleCommentAdded = useCallback((comment: CommentResponse) => {
    setComments((prev) => [...prev, comment]);
  }, []);

  const currentVersion = data.current_version;
  const showDecisionPanel = asset.status === "pending_review" || asset.status === "pending";

  return (
    <main className="min-h-screen bg-background">
      <div className="mx-auto max-w-7xl px-4 py-6 md:px-6 lg:px-8">
        {/* Client header - full width */}
        <ClientHeader client={data.client} asset={asset} />

        {/* Two-column layout on desktop, stacked on mobile */}
        <div className="mt-6 grid grid-cols-1 gap-6 md:grid-cols-5">
          {/* Left column: Media (3/5 on desktop) */}
          <div className="md:col-span-3">
            {currentVersion ? (
              <MediaViewer
                fileType={currentVersion.file_type}
                mediaUrl={currentVersion.media_url ?? ""}
                thumbnailUrl={currentVersion.thumbnail_url ?? undefined}
                alt={asset.title}
              />
            ) : (
              <div className="flex items-center justify-center rounded-lg border border-dashed bg-muted/30 py-16">
                <p className="text-sm text-muted-foreground">
                  Nenhuma versão de mídia disponível.
                </p>
              </div>
            )}
          </div>

          {/* Right column: Info panel (2/5 on desktop) */}
          <div className="space-y-4 md:col-span-2">
            {/* Version history */}
            <VersionHistory
              versions={data.versions}
              currentVersion={asset.current_version}
            />

            {/* Decision panel - only for pending review */}
            {showDecisionPanel && (
              <DecisionPanel
                assetId={asset.id}
                onDecisionMade={handleDecisionMade}
              />
            )}

            {/* Status banner when decided */}
            {asset.status === "approved" && (
              <div
                className="rounded-lg border border-success/30 bg-success/10 p-4 text-center"
                role="status"
              >
                <p className="text-sm font-medium text-success">
                  Este conteúdo foi aprovado.
                </p>
              </div>
            )}
            {asset.status === "changes_requested" && (
              <div
                className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-center"
                role="status"
              >
                <p className="text-sm font-medium text-destructive">
                  Alterações foram solicitadas para este conteúdo.
                </p>
              </div>
            )}

            {/* Comments */}
            <CommentSection
              comments={comments}
              assetId={asset.id}
              onCommentAdded={handleCommentAdded}
            />
          </div>
        </div>
      </div>
    </main>
  );
}
