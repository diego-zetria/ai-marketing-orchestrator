"use client";

import { useState } from "react";
import type { CommentResponse } from "@/lib/types";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { MessageSquare, Send, User, Users } from "lucide-react";

interface CommentSectionProps {
  comments: CommentResponse[];
  assetId: string;
  onCommentAdded: (comment: CommentResponse) => void;
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

function AuthorIcon({ authorType }: { authorType: string }) {
  if (authorType === "team") {
    return <Users className="h-4 w-4" aria-hidden="true" />;
  }
  return <User className="h-4 w-4" aria-hidden="true" />;
}

export function CommentSection({
  comments,
  assetId,
  onCommentAdded,
}: CommentSectionProps) {
  const [content, setContent] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    const trimmed = content.trim();
    if (!trimmed) return;

    setSubmitting(true);
    setError(null);

    try {
      const comment = await api.addComment(assetId, trimmed);
      onCommentAdded(comment);
      setContent("");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Erro ao enviar comentário. Tente novamente.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="rounded-lg border bg-background p-4">
      <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-foreground">
        <MessageSquare className="h-4 w-4" aria-hidden="true" />
        Comentários ({comments.length})
      </h2>

      {/* Comment list */}
      {comments.length > 0 ? (
        <div
          className="mb-4 max-h-64 space-y-3 overflow-y-auto"
          role="list"
          aria-label="Lista de comentários"
        >
          {comments.map((comment) => (
            <div
              key={comment.id}
              role="listitem"
              className="rounded-md bg-muted/30 p-3"
            >
              <div className="mb-1 flex items-center gap-2 text-xs text-muted-foreground">
                <AuthorIcon authorType={comment.author_type} />
                <span className="font-medium text-foreground">
                  {comment.author_name}
                </span>
                <span>{formatDate(comment.created_at)}</span>
              </div>
              <p className="text-sm text-foreground whitespace-pre-wrap">
                {comment.content}
              </p>
            </div>
          ))}
        </div>
      ) : (
        <p className="mb-4 text-sm text-muted-foreground">
          Nenhum comentário ainda.
        </p>
      )}

      {/* New comment form */}
      <form onSubmit={handleSubmit} className="space-y-2">
        <Textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder="Escreva um comentário..."
          disabled={submitting}
          aria-label="Novo comentário"
          rows={3}
        />
        {error && (
          <p className="text-xs text-destructive" role="alert">
            {error}
          </p>
        )}
        <div className="flex justify-end">
          <Button
            type="submit"
            size="sm"
            disabled={submitting || !content.trim()}
          >
            <Send className="mr-2 h-3 w-3" aria-hidden="true" />
            {submitting ? "Enviando..." : "Enviar"}
          </Button>
        </div>
      </form>
    </div>
  );
}
