// Layout for the (dashboard) route group: every page under app/(dashboard)/
// requires a session. Route groups don't affect URLs, so this only adds the
// guard — public routes (/login, /register, /forgot-password) are untouched.

import type { ReactNode } from "react";
import ProtectedRoute from "../../components/ProtectedRoute";

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return <ProtectedRoute>{children}</ProtectedRoute>;
}
