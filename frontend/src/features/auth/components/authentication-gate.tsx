import { EmptyState, LoadingState } from "../../../shared/ui/async-state";
import { useAuth } from "../auth-context";

export function AuthenticationGate() {
  const auth = useAuth();

  if (
    auth.status === "loading" ||
    (!auth.canAccessProtectedApi &&
      (auth.status === "authenticated" || auth.status === "development_token"))
  ) {
    return <LoadingState label="Checking your secure sign-in session..." />;
  }

  if (auth.status === "unconfigured") {
    return (
      <EmptyState title="Firebase authentication is not configured">
        <p>
          CodexForge will not call protected API routes until Firebase client configuration is
          complete. Add the following values to an untracked <code>frontend/.env.local</code> file,
          then restart Vite.
        </p>
        <ul className="mt-4 list-disc space-y-1 pl-5 font-mono text-xs text-slate-700">
          {auth.missingConfiguration.map((variable) => (
            <li key={variable}>{variable}</li>
          ))}
        </ul>
        <p className="mt-4">
          Use Firebase Console to enable Google sign-in and authorize the local and deployed
          frontend domains. Do not put backend, GitHub, OpenAI, database, or cloud credentials in
          Vite environment variables.
        </p>
      </EmptyState>
    );
  }

  if (auth.status === "unauthenticated") {
    return (
      <section
        className="rounded-2xl border border-slate-200 bg-white p-7 shadow-panel"
        aria-labelledby="sign-in-title"
      >
        <p className="eyebrow">Secure access</p>
        <h1 id="sign-in-title" className="mt-1 text-2xl font-semibold text-slate-950">
          Sign in to your CodexForge workspace
        </h1>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-600">
          Google sign-in provides a Firebase ID token. CodexForge attaches it to protected API
          calls; it does not expose GitHub, OpenAI, database, or cloud credentials to the browser.
        </p>
        {auth.error ? (
          <p className="field-error mt-4" role="alert">
            {auth.error}
          </p>
        ) : null}
        <button
          type="button"
          className="button-primary mt-5"
          disabled={auth.isSigningIn}
          onClick={() => void auth.signIn()}
        >
          {auth.isSigningIn ? "Opening Google sign-in..." : "Continue with Google"}
        </button>
      </section>
    );
  }

  return null;
}
