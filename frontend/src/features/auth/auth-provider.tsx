import { useCallback, useEffect, useMemo, useState } from "react";
import type { PropsWithChildren } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  GoogleAuthProvider,
  onIdTokenChanged,
  signInWithPopup,
  signOut as firebaseSignOut,
} from "firebase/auth";
import type { Auth, User } from "firebase/auth";

import { setApiTokenProvider } from "../../shared/api/client";
import type { ApiTokenProvider } from "../../shared/api/client";
import {
  AuthContext,
  type AuthContextValue,
  type AuthenticatedUser,
  type AuthenticationStatus,
} from "./auth-context";
import {
  firebaseClientConfiguration,
  getDevelopmentBearerToken,
  getFirebaseAuthClient,
} from "./firebase-client";

function toAuthenticatedUser(user: User): AuthenticatedUser {
  return {
    uid: user.uid,
    displayName: user.displayName,
    email: user.email,
    photoURL: user.photoURL,
  };
}

function resolveFirebaseAuth(developmentBearerToken: string | undefined): Auth | null {
  if (developmentBearerToken || !firebaseClientConfiguration.configured) {
    return null;
  }

  return getFirebaseAuthClient();
}

export function FirebaseAuthProvider({ children }: PropsWithChildren) {
  const queryClient = useQueryClient();
  const developmentBearerToken = getDevelopmentBearerToken();
  const firebaseAuth = useMemo(
    () => resolveFirebaseAuth(developmentBearerToken),
    [developmentBearerToken],
  );
  const [status, setStatus] = useState<AuthenticationStatus>(() => {
    if (developmentBearerToken) {
      return "development_token";
    }

    return firebaseClientConfiguration.configured ? "loading" : "unconfigured";
  });
  const [user, setUser] = useState<AuthenticatedUser | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSigningIn, setIsSigningIn] = useState(false);
  const [isTokenProviderReady, setIsTokenProviderReady] = useState(false);

  const getIdToken = useCallback<ApiTokenProvider>(async () => {
    if (developmentBearerToken) {
      return developmentBearerToken;
    }

    return firebaseAuth?.currentUser ? firebaseAuth.currentUser.getIdToken() : null;
  }, [developmentBearerToken, firebaseAuth]);

  useEffect(() => {
    setApiTokenProvider(getIdToken);
    setIsTokenProviderReady(true);

    return () => {
      setApiTokenProvider(null);
      setIsTokenProviderReady(false);
    };
  }, [getIdToken]);

  useEffect(() => {
    if (developmentBearerToken) {
      setStatus("development_token");
      setUser(null);
      setError(null);
      return undefined;
    }

    if (!firebaseAuth) {
      setStatus("unconfigured");
      setUser(null);
      return undefined;
    }

    setStatus("loading");
    return onIdTokenChanged(
      firebaseAuth,
      (firebaseUser) => {
        if (firebaseUser) {
          setUser(toAuthenticatedUser(firebaseUser));
          setStatus("authenticated");
          setError(null);
          return;
        }

        queryClient.clear();
        setUser(null);
        setStatus("unauthenticated");
      },
      () => {
        queryClient.clear();
        setUser(null);
        setStatus("unauthenticated");
        setError("Your sign-in session could not be restored. Please sign in again.");
      },
    );
  }, [developmentBearerToken, firebaseAuth, queryClient]);

  const signIn = useCallback(async () => {
    if (!firebaseAuth || developmentBearerToken) {
      return;
    }

    setIsSigningIn(true);
    setError(null);

    try {
      await signInWithPopup(firebaseAuth, new GoogleAuthProvider());
    } catch {
      setError("Google sign-in did not complete. Check the authorized domain and try again.");
    } finally {
      setIsSigningIn(false);
    }
  }, [developmentBearerToken, firebaseAuth]);

  const signOut = useCallback(async () => {
    if (!firebaseAuth || developmentBearerToken) {
      return;
    }

    setError(null);
    try {
      await firebaseSignOut(firebaseAuth);
    } catch {
      setError("Sign out could not be completed. Please retry.");
    }
  }, [developmentBearerToken, firebaseAuth]);

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      user,
      missingConfiguration: firebaseClientConfiguration.configured
        ? []
        : firebaseClientConfiguration.missingVariables,
      canAccessProtectedApi:
        isTokenProviderReady && (status === "authenticated" || status === "development_token"),
      isSigningIn,
      error,
      getIdToken,
      signIn,
      signOut,
    }),
    [error, getIdToken, isSigningIn, isTokenProviderReady, signIn, signOut, status, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
