import { createContext, useContext } from "react";

import type { ApiTokenProvider } from "../../shared/api/client";
import type { FirebaseRequiredEnvironmentVariable } from "./firebase-client";

export type AuthenticationStatus =
  "unconfigured" | "loading" | "unauthenticated" | "authenticated" | "development_token";

export interface AuthenticatedUser {
  uid: string;
  displayName: string | null;
  email: string | null;
  photoURL: string | null;
}

export interface AuthContextValue {
  status: AuthenticationStatus;
  user: AuthenticatedUser | null;
  missingConfiguration: FirebaseRequiredEnvironmentVariable[];
  canAccessProtectedApi: boolean;
  isSigningIn: boolean;
  error: string | null;
  getIdToken: ApiTokenProvider;
  signIn: () => Promise<void>;
  signOut: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside FirebaseAuthProvider.");
  }

  return context;
}

/** Hook for UI integrations that need the same current Firebase ID-token provider as the API client. */
export function useApiTokenProvider(): ApiTokenProvider {
  return useAuth().getIdToken;
}
