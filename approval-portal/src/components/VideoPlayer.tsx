"use client";

interface VideoPlayerProps {
  src: string;
  poster?: string;
}

export function VideoPlayer({ src, poster }: VideoPlayerProps) {
  return (
    <div className="overflow-hidden rounded-lg border bg-black">
      <video
        src={src}
        poster={poster}
        controls
        controlsList="nodownload"
        preload="metadata"
        className="w-full max-h-[70vh]"
        aria-label="Player de video do conteudo"
      >
        <track kind="captions" />
        Seu navegador nao suporta o elemento de video.
      </video>
    </div>
  );
}
