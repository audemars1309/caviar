/**
 * Route table (Phase 9A). Every page is lazy-loaded (route-level code
 * splitting); layouts wrap route groups; guards enforce auth. Pages are
 * layout placeholders only - feature logic arrives in Phases 9B/9C.
 */
import { lazy, Suspense, type ReactNode } from "react";
import { createBrowserRouter } from "react-router";

import { LoadingScreen } from "@/components/common/LoadingScreen";
import { AuthLayout } from "@/layouts/AuthLayout";
import { DashboardLayout } from "@/layouts/DashboardLayout";
import { PublicLayout } from "@/layouts/PublicLayout";
import { ProtectedRoute } from "@/routes/ProtectedRoute";
import { PublicOnlyRoute } from "@/routes/PublicOnlyRoute";
import { PATHS } from "@/routes/paths";

const LandingPage = lazy(() => import("@/pages/LandingPage"));
const LoginPage = lazy(() => import("@/pages/LoginPage"));
const SignupPage = lazy(() => import("@/pages/SignupPage"));
const DashboardPage = lazy(() => import("@/pages/DashboardPage"));
const ResumePage = lazy(() => import("@/pages/ResumePage"));
const ResumeBuilderPage = lazy(() => import("@/pages/ResumeBuilderPage"));
const InterviewPage = lazy(() => import("@/pages/InterviewPage"));
const SettingsPage = lazy(() => import("@/pages/SettingsPage"));
const ProfilePage = lazy(() => import("@/pages/ProfilePage"));
const NotFoundPage = lazy(() => import("@/pages/NotFoundPage"));

function suspended(node: ReactNode): ReactNode {
  return <Suspense fallback={<LoadingScreen />}>{node}</Suspense>;
}

export const router = createBrowserRouter([
  {
    element: <PublicLayout />,
    children: [{ path: PATHS.landing, element: suspended(<LandingPage />) }],
  },
  {
    element: <PublicOnlyRoute />,
    children: [
      {
        element: <AuthLayout />,
        children: [
          { path: PATHS.login, element: suspended(<LoginPage />) },
          { path: PATHS.signup, element: suspended(<SignupPage />) },
        ],
      },
    ],
  },
  {
    element: <ProtectedRoute />,
    children: [
      {
        element: <DashboardLayout />,
        children: [
          { path: PATHS.dashboard, element: suspended(<DashboardPage />) },
          { path: PATHS.resume, element: suspended(<ResumePage />) },
          { path: PATHS.resumeBuilder, element: suspended(<ResumeBuilderPage />) },
          { path: PATHS.interview, element: suspended(<InterviewPage />) },
          { path: PATHS.settings, element: suspended(<SettingsPage />) },
          { path: PATHS.profile, element: suspended(<ProfilePage />) },
        ],
      },
    ],
  },
  { path: "*", element: suspended(<NotFoundPage />) },
]);
