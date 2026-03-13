"use client";

import type { FileType } from "@/lib/types";
import { ImageViewer } from "@/components/ImageViewer";
import { VideoPlayer } from "@/components/VideoPlayer";
import { ExternalLink, ImageOff } from "lucide-react";

interface MediaViewerProps {
  fileType: FileType;
  mediaUrl: string;
  thumbnailUrl?: string;
  alt?: string;
}

export function MediaViewer({
  fileType,
  mediaUrl,
  thumbnailUrl,
  alt,
}: MediaViewerProps) {
  if (!mediaUrl) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed bg-muted/30 py-16">
        <ImageOff className="h-10 w-10 text-muted-foreground" aria-hidden="true" />
        <p className="text-sm text-muted-foreground">Sem mídia disponível</p>
      </div>
    );
  }

  if (fileType === "link") {
    return (
      <div className="flex flex-col items-center justify-center gap-4 rounded-lg border bg-muted/10 py-16">
        <ExternalLink className="h-12 w-12 text-primary" aria-hidden="true" />
        <div className="text-center px-6">
          <p className="text-sm text-muted-foreground mb-4">
            O conteúdo está disponível no Google Drive
          </p>
          <a
            href={mediaUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 rounded-md bg-primary px-6 py-3 text-sm font-medium text-primary-foreground shadow hover:bg-primary/90 transition-colors"
          >
            <ExternalLink className="h-4 w-4" />
            Abrir no Google Drive
          </a>
        </div>
      </div>
    );
  }

  if (fileType === "video") {
    return <VideoPlayer src={mediaUrl} poster={thumbnailUrl} />;
  }

  return <ImageViewer src={mediaUrl} alt={alt ?? "Conteúdo para aprovação"} />;
}
