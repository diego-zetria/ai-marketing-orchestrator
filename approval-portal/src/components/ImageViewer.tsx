"use client";

import { TransformWrapper, TransformComponent } from "react-zoom-pan-pinch";
import { ZoomIn, ZoomOut, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";

interface ImageViewerProps {
  src: string;
  alt: string;
}

export function ImageViewer({ src, alt }: ImageViewerProps) {
  return (
    <TransformWrapper
      initialScale={1}
      minScale={0.5}
      maxScale={4}
      centerOnInit
    >
      {({ zoomIn, zoomOut, resetTransform }) => (
        <div className="relative flex flex-col">
          {/* Zoom controls */}
          <div className="absolute top-3 right-3 z-10 flex gap-1">
            <Button
              variant="secondary"
              size="icon"
              onClick={() => zoomIn()}
              aria-label="Aumentar zoom"
              className="h-8 w-8 bg-background/80 backdrop-blur-sm shadow-sm"
            >
              <ZoomIn className="h-4 w-4" />
            </Button>
            <Button
              variant="secondary"
              size="icon"
              onClick={() => zoomOut()}
              aria-label="Diminuir zoom"
              className="h-8 w-8 bg-background/80 backdrop-blur-sm shadow-sm"
            >
              <ZoomOut className="h-4 w-4" />
            </Button>
            <Button
              variant="secondary"
              size="icon"
              onClick={() => resetTransform()}
              aria-label="Resetar zoom"
              className="h-8 w-8 bg-background/80 backdrop-blur-sm shadow-sm"
            >
              <RotateCcw className="h-4 w-4" />
            </Button>
          </div>

          {/* Zoomable image */}
          <div className="overflow-hidden rounded-lg border bg-muted/30">
            <TransformComponent
              wrapperStyle={{ width: "100%", maxHeight: "70vh" }}
              contentStyle={{ width: "100%", display: "flex", justifyContent: "center" }}
            >
              <img
                src={src}
                alt={alt}
                className="max-h-[70vh] w-auto object-contain"
              />
            </TransformComponent>
          </div>
        </div>
      )}
    </TransformWrapper>
  );
}
