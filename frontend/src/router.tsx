import {
  createRouter,
  createRoute,
  createRootRoute,
  redirect,
  Outlet,
} from "@tanstack/react-router";
import { Layout } from "@/components/layout";
import { LoginPage } from "@/pages/login";
import { DashboardPage } from "@/pages/dashboard";
import { TeamPage } from "@/pages/team";
import { ClientsPage } from "@/pages/clients";
import { RulesPage } from "@/pages/rules";
import { NotificationsPage } from "@/pages/notifications";
import { AgentsPage } from "@/pages/agents";
import { ToolsPage } from "@/pages/tools";
import { BrandsPage } from "@/pages/brands";
import { KnowledgePage } from "@/pages/knowledge";
import { ModelsPage } from "@/pages/models";
import { SystemPage } from "@/pages/system";
import { ActivityPage } from "@/pages/activity";
import { ApprovalsPage } from "@/pages/approvals";
import { ApprovalDetailPage } from "@/pages/approval-detail";
import { WorkflowsPage } from "@/pages/workflows";
import { AutomationsPage } from "@/pages/automations";
import { WebhooksPage } from "@/pages/webhooks";
import { MediaPage } from "@/pages/media";
import { HealthPage } from "@/pages/health";
import { UsersPage } from "@/pages/users";
import { ChangePasswordPage } from "@/pages/change-password";

function isAuthenticated() {
  return !!localStorage.getItem("admin_token");
}

// Root route
const rootRoute = createRootRoute({
  component: Outlet,
});

// Login route (no layout)
const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/login",
  component: LoginPage,
});

// Layout route for authenticated pages
const layoutRoute = createRoute({
  getParentRoute: () => rootRoute,
  id: "layout",
  beforeLoad: () => {
    if (!isAuthenticated()) {
      throw redirect({ to: "/login" });
    }
  },
  component: () => (
    <Layout>
      <Outlet />
    </Layout>
  ),
});

// Dashboard
const dashboardRoute = createRoute({
  getParentRoute: () => layoutRoute,
  path: "/",
  component: DashboardPage,
});

// Team
const teamRoute = createRoute({
  getParentRoute: () => layoutRoute,
  path: "/team",
  component: TeamPage,
});

// Clients
const clientsRoute = createRoute({
  getParentRoute: () => layoutRoute,
  path: "/clients",
  component: ClientsPage,
});

// Rules
const rulesRoute = createRoute({
  getParentRoute: () => layoutRoute,
  path: "/rules",
  component: RulesPage,
});

// Notifications
const notificationsRoute = createRoute({
  getParentRoute: () => layoutRoute,
  path: "/notifications",
  component: NotificationsPage,
});

// Agents
const agentsRoute = createRoute({
  getParentRoute: () => layoutRoute,
  path: "/agents",
  component: AgentsPage,
});

// Tools
const toolsRoute = createRoute({
  getParentRoute: () => layoutRoute,
  path: "/tools",
  component: ToolsPage,
});

// Brands
const brandsRoute = createRoute({
  getParentRoute: () => layoutRoute,
  path: "/brands",
  component: BrandsPage,
});

// Models
const modelsRoute = createRoute({
  getParentRoute: () => layoutRoute,
  path: "/models",
  component: ModelsPage,
});

// Knowledge
const knowledgeRoute = createRoute({
  getParentRoute: () => layoutRoute,
  path: "/knowledge",
  component: KnowledgePage,
});

// System
const systemRoute = createRoute({
  getParentRoute: () => layoutRoute,
  path: "/system",
  component: SystemPage,
});

// Approvals
const approvalsRoute = createRoute({
  getParentRoute: () => layoutRoute,
  path: "/approvals",
  component: ApprovalsPage,
});

const approvalDetailRoute = createRoute({
  getParentRoute: () => layoutRoute,
  path: "/approvals/$assetId",
  component: ApprovalDetailPage,
});

// Workflows
const workflowsRoute = createRoute({
  getParentRoute: () => layoutRoute,
  path: "/admin/workflows",
  component: WorkflowsPage,
});

// Automations
const automationsRoute = createRoute({
  getParentRoute: () => layoutRoute,
  path: "/admin/automations",
  component: AutomationsPage,
});

// Media Library
const mediaRoute = createRoute({
  getParentRoute: () => layoutRoute,
  path: "/media",
  component: MediaPage,
});

// Health
const healthRoute = createRoute({
  getParentRoute: () => layoutRoute,
  path: "/health",
  component: HealthPage,
});

// Webhooks
const webhooksRoute = createRoute({
  getParentRoute: () => layoutRoute,
  path: "/webhooks",
  component: WebhooksPage,
});

// Activity
const activityRoute = createRoute({
  getParentRoute: () => layoutRoute,
  path: "/activity",
  component: ActivityPage,
});

// Users
const usersRoute = createRoute({
  getParentRoute: () => layoutRoute,
  path: "/users",
  component: UsersPage,
});

// Change Password
const changePasswordRoute = createRoute({
  getParentRoute: () => layoutRoute,
  path: "/change-password",
  component: ChangePasswordPage,
});

// Build route tree
const routeTree = rootRoute.addChildren([
  loginRoute,
  layoutRoute.addChildren([
    dashboardRoute,
    teamRoute,
    clientsRoute,
    rulesRoute,
    notificationsRoute,
    agentsRoute,
    toolsRoute,
    brandsRoute,
    modelsRoute,
    knowledgeRoute,
    systemRoute,
    approvalsRoute,
    approvalDetailRoute,
    workflowsRoute,
    automationsRoute,
    mediaRoute,
    healthRoute,
    webhooksRoute,
    activityRoute,
    usersRoute,
    changePasswordRoute,
  ]),
]);

// Create router
export const router = createRouter({
  routeTree,
  basepath: "/",
  defaultPreload: "intent",
});

// Type-safe router declaration
declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
