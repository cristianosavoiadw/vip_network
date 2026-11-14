import { lazy, Suspense } from "react";
import type { ComponentType, LazyExoticComponent } from "react";
import { createBrowserRouter, Navigate } from "react-router-dom";
import { PublicLayout } from "@/app/layouts/PublicLayout";
import { AppLayout } from "@/app/layouts/AppLayout";
import { AdminLayout } from "@/app/layouts/AdminLayout";
import { Spinner } from "@/components/ui/bits";
import { RouteError } from "@/components/RouteError";

const L = (load: () => Promise<{ default: ComponentType }>) => {
  const C: LazyExoticComponent<ComponentType> = lazy(load);
  return (
    <Suspense fallback={<Spinner />}>
      <C />
    </Suspense>
  );
};

export const router = createBrowserRouter([
  {
    element: <PublicLayout />,
    errorElement: <RouteError />,
    children: [
      { path: "/", element: L(() => import("@/features/home/HomePage")) },
      { path: "/termos", element: L(() => import("@/features/legal/TermsPage")) },
      { path: "/privacidade", element: L(() => import("@/features/legal/PrivacyPage")) },
      { path: "/contato", element: L(() => import("@/features/legal/ContactPage")) },
    ],
  },
  // full-screen flows (own minimal header)
  { path: "/entrar", element: L(() => import("@/features/auth/LoginPage")) },
  { path: "/esqueci-senha", element: L(() => import("@/features/auth/ForgotPage")) },
  { path: "/redefinir-senha/:token", element: L(() => import("@/features/auth/ResetPage")) },
  { path: "/ativar/:token", element: L(() => import("@/features/auth/ActivatePage")) },
  { path: "/confirmar-email/:token", element: L(() => import("@/features/auth/VerifyEmailPage")) },
  { path: "/cadastro", element: L(() => import("@/features/signup/SignupPage")) },
  { path: "/convite", element: L(() => import("@/features/signup/InvitePage")) },
  { path: "/convite/:code", element: L(() => import("@/features/signup/InvitePage")) },
  { path: "/admin/entrar", element: L(() => import("@/features/auth/AdminLoginPage")) },
  {
    path: "/app",
    element: <AppLayout />,
    errorElement: <RouteError />,
    children: [
      { index: true, element: L(() => import("@/features/overview/OverviewPage")) },
      { path: "descobrir", element: L(() => import("@/features/discover/DiscoverPage")) },
      { path: "empresas/:slug", element: L(() => import("@/features/discover/CompanyPage")) },
      { path: "curtidas", element: L(() => import("@/features/likes/LikesPage")) },
      { path: "matches", element: L(() => import("@/features/matches/MatchesPage")) },
      { path: "rede", element: L(() => import("@/features/network/NetworkPage")) },
      { path: "oportunidades", element: L(() => import("@/features/opportunities/OpportunitiesPage")) },
      { path: "compras", element: L(() => import("@/features/purchases/PurchasesPage")) },
      { path: "vendas", element: L(() => import("@/features/sales/SalesPage")) },
      { path: "mensagens", element: L(() => import("@/features/messages/MessagesPage")) },
      { path: "mensagens/:id", element: L(() => import("@/features/messages/MessagesPage")) },
      { path: "eventos", element: L(() => import("@/features/events/EventsPage")) },
      { path: "inteligencia", element: L(() => import("@/features/intelligence/IntelligencePage")) },
      { path: "mentoria", element: L(() => import("@/features/mentorship/MentorshipPage")) },
      { path: "empresa", element: L(() => import("@/features/company/CompanyProfilePage")) },
      { path: "equipe", element: L(() => import("@/features/team/TeamPage")) },
      { path: "assinatura", element: L(() => import("@/features/billing/BillingPage")) },
      { path: "indicar", element: L(() => import("@/features/invites/InvitesPage")) },
      { path: "notificacoes", element: L(() => import("@/features/notifications/PreferencesPage")) },
    ],
  },
  {
    path: "/admin",
    element: <AdminLayout />,
    errorElement: <RouteError />,
    children: [
      { index: true, element: L(() => import("@/features/admin/AdminOverviewPage")) },
      { path: "assinaturas", element: L(() => import("@/features/admin/AdminSubscriptionsPage")) },
      { path: "rede", element: L(() => import("@/features/admin/AdminNetworkPage")) },
      { path: "matchmaking", element: L(() => import("@/features/admin/AdminMatchmakingPage")) },
      { path: "brilhar", element: L(() => import("@/features/admin/AdminBoostsPage")) },
      { path: "eventos", element: L(() => import("@/features/admin/AdminEventsPage")) },
      { path: "mentoria", element: L(() => import("@/features/admin/AdminMentorshipPage")) },
      { path: "acesso", element: L(() => import("@/features/admin/AdminAccessPage")) },
      { path: "emails", element: L(() => import("@/features/admin/AdminEmailsPage")) },
      { path: "agentes", element: L(() => import("@/features/admin/AdminAgentsPage")) },
      { path: "suporte", element: L(() => import("@/features/admin/AdminSupportPage")) },
      { path: "analytics", element: L(() => import("@/features/admin/AdminAnalyticsPage")) },
      { path: "equipe", element: L(() => import("@/features/admin/AdminTeamPage")) },
    ],
  },
  { path: "*", element: <Navigate to="/" replace /> },
]);
