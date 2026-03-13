import { Suspense } from "react";
import { ReviewTokenClient } from "@/components/ReviewTokenClient";

/**
 * Review page: /review?token=<magic-link-token>
 *
 * Uses query parameters instead of dynamic path segments to remain
 * compatible with Next.js static export (output: 'export').
 * The ReviewTokenClient reads the token from searchParams, validates it
 * with the API, and renders the full review UI.
 *
 * Wrapped in Suspense because useSearchParams() requires it in
 * statically rendered pages.
 */
export default function ReviewPage() {
  return (
    <Suspense>
      <ReviewTokenClient />
    </Suspense>
  );
}
