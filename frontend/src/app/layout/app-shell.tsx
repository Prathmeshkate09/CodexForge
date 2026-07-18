import { Link, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "../../features/auth/auth-context";

export function AppShell() {
  const location = useLocation();
  const auth = useAuth();
  const isDashboard = location.pathname === "/";
  const accountLabel = auth.user?.displayName ?? auth.user?.email ?? "Signed in";

  return (
    <div className="min-h-screen bg-slate-50 text-slate-950">
      <a href="#main-content" className="skip-link">
        Skip to main content
      </a>
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-5 py-4 sm:px-8">
          <Link to="/" className="group flex items-center gap-3" aria-label="CodexForge dashboard">
            <span className="grid h-9 w-9 place-items-center rounded-xl bg-indigo-600 text-sm font-bold text-white shadow-sm">
              CF
            </span>
            <span>
              <span className="block text-sm font-bold tracking-tight text-slate-950">
                CodexForge
              </span>
              <span className="block text-xs text-slate-500">
                Approval-first developer workflow
              </span>
            </span>
          </Link>
          <div className="flex items-center gap-2">
            <nav aria-label="Primary navigation" className="flex items-center gap-1">
              <Link className={isDashboard ? "nav-link nav-link-active" : "nav-link"} to="/">
                Workspace
              </Link>
            </nav>
            {auth.status === "authenticated" ? (
              <div className="hidden items-center gap-2 border-l border-slate-200 pl-3 sm:flex">
                <span className="max-w-36 truncate text-xs text-slate-600" title={accountLabel}>
                  {accountLabel}
                </span>
                <button type="button" className="nav-link" onClick={() => void auth.signOut()}>
                  Sign out
                </button>
              </div>
            ) : null}
            {auth.status === "development_token" ? (
              <span className="hidden rounded-full bg-amber-100 px-2.5 py-1 text-xs font-semibold text-amber-900 sm:inline-flex">
                Local development token
              </span>
            ) : null}
          </div>
        </div>
      </header>
      <main id="main-content" className="mx-auto max-w-7xl px-5 py-8 sm:px-8 sm:py-10">
        <Outlet />
      </main>
    </div>
  );
}
