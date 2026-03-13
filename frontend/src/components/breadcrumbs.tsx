import { Link, useLocation, useParams } from "@tanstack/react-router";
import { ChevronRight, Home } from "lucide-react";

/**
 * Maps route segments to Portuguese labels.
 * Dynamic segments (e.g. $assetId) are resolved at render time.
 */
const ROUTE_LABELS: Record<string, string> = {
  admin: "Dashboard",
  team: "Equipe",
  clients: "Clientes",
  approvals: "Aprovações",
  rules: "Regras",
  notifications: "Notificações",
  agents: "Agentes IA",
  tools: "Ferramentas IA",
  models: "Modelos IA",
  brands: "Diretrizes",
  knowledge: "Conhecimento",
  system: "Configurações",
  activity: "Atividades",
};

interface Crumb {
  label: string;
  href: string;
}

export function Breadcrumbs() {
  const location = useLocation();
  const params = useParams({ strict: false });

  const segments = location.pathname
    .replace(/\/$/, "")
    .split("/")
    .filter(Boolean);

  // Don't show breadcrumbs on the dashboard (root page)
  if (segments.length === 0) {
    return null;
  }

  const crumbs: Crumb[] = [{ label: "Dashboard", href: "/" }];
  let path = "";

  for (const segment of segments) {
    path += `/${segment}`;

    // Check if this segment is a dynamic param (e.g. an asset ID)
    const assetId = (params as Record<string, string | undefined>).assetId;
    if (assetId && segment === assetId) {
      // Truncate long UUIDs for display
      const short =
        segment.length > 12 ? `${segment.slice(0, 8)}...` : segment;
      crumbs.push({ label: short, href: path });
      continue;
    }

    const label = ROUTE_LABELS[segment];
    if (label) {
      crumbs.push({ label, href: path });
    }
  }

  // Need at least 2 crumbs (Dashboard + current page) to be useful
  if (crumbs.length < 2) return null;

  const lastIndex = crumbs.length - 1;

  return (
    <nav
      aria-label="Breadcrumb"
      className="flex items-center gap-1.5 border-b px-4 py-2.5 text-sm lg:px-6"
    >
      <Link
        to="/"
        className="text-muted-foreground hover:text-foreground transition-colors"
        aria-label="Dashboard"
      >
        <Home className="h-3.5 w-3.5" aria-hidden="true" />
      </Link>

      {crumbs.slice(1).map((crumb, i) => {
        const isLast = i + 1 === lastIndex;
        return (
          <span key={crumb.href} className="flex items-center gap-1.5">
            <ChevronRight
              className="h-3.5 w-3.5 text-muted-foreground/50"
              aria-hidden="true"
            />
            {isLast ? (
              <span className="font-medium text-foreground" aria-current="page">
                {crumb.label}
              </span>
            ) : (
              <Link
                to={crumb.href}
                className="text-muted-foreground hover:text-foreground transition-colors"
              >
                {crumb.label}
              </Link>
            )}
          </span>
        );
      })}
    </nav>
  );
}
