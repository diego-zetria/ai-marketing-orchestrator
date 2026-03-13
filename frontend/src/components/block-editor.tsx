import { useEffect, useRef, useCallback } from "react";
import { pt } from "@blocknote/core/locales";
import "@blocknote/core/fonts/inter.css";
import { useCreateBlockNote } from "@blocknote/react";
import { BlockNoteView } from "@blocknote/shadcn";
import "@blocknote/shadcn/style.css";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface BlockEditorProps {
  /** Markdown content to initialize the editor with */
  initialMarkdown?: string;
  /** Called with the current markdown whenever the editor content changes */
  onChange?: (markdown: string) => void;
  /** Whether the editor is read-only */
  editable?: boolean;
  /** Placeholder text shown when editor is empty */
  placeholder?: string;
  /** Additional CSS class for the wrapper */
  className?: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function BlockEditor({
  initialMarkdown = "",
  onChange,
  editable = true,
  className,
}: BlockEditorProps) {
  const editor = useCreateBlockNote({
    dictionary: pt,
  });
  const initializedRef = useRef(false);
  const lastExternalMarkdown = useRef(initialMarkdown);

  // Load initial markdown on mount
  useEffect(() => {
    if (initializedRef.current) return;
    initializedRef.current = true;

    if (!initialMarkdown) return;

    async function load() {
      const blocks = await editor.tryParseMarkdownToBlocks(initialMarkdown);
      editor.replaceBlocks(editor.document, blocks);
    }
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editor]);

  // Reset editor when initialMarkdown changes externally (e.g. switching clients)
  useEffect(() => {
    if (lastExternalMarkdown.current === initialMarkdown) return;
    lastExternalMarkdown.current = initialMarkdown;
    initializedRef.current = true;

    async function reload() {
      const blocks = await editor.tryParseMarkdownToBlocks(initialMarkdown);
      editor.replaceBlocks(editor.document, blocks);
    }
    reload();
  }, [editor, initialMarkdown]);

  // Handle content changes — convert blocks back to markdown
  const handleChange = useCallback(async () => {
    if (!onChange) return;
    const md = await editor.blocksToMarkdownLossy(editor.document);
    onChange(md);
  }, [editor, onChange]);

  return (
    <div className={className}>
      <BlockNoteView
        editor={editor}
        editable={editable}
        onChange={handleChange}
        theme="light"
      />
    </div>
  );
}
