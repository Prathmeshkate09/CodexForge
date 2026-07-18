import { getApp, getApps, initializeApp } from "firebase/app";
import type { FirebaseOptions } from "firebase/app";
import { getAuth } from "firebase/auth";
import type { Auth } from "firebase/auth";

export const firebaseRequiredEnvironmentVariables = [
  "VITE_FIREBASE_API_KEY",
  "VITE_FIREBASE_AUTH_DOMAIN",
  "VITE_FIREBASE_PROJECT_ID",
  "VITE_FIREBASE_APP_ID",
] as const;

export type FirebaseRequiredEnvironmentVariable =
  (typeof firebaseRequiredEnvironmentVariables)[number];

export type FirebaseEnvironment = Partial<
  Record<
    | FirebaseRequiredEnvironmentVariable
    | "VITE_FIREBASE_MESSAGING_SENDER_ID"
    | "VITE_FIREBASE_STORAGE_BUCKET",
    string | undefined
  >
>;

export type FirebaseClientConfiguration =
  | {
      configured: true;
      missingVariables: [];
      options: FirebaseOptions;
    }
  | {
      configured: false;
      missingVariables: FirebaseRequiredEnvironmentVariable[];
      options: null;
    };

function readValue(
  environment: FirebaseEnvironment,
  key: keyof FirebaseEnvironment,
): string | undefined {
  const value = environment[key]?.trim();
  return value || undefined;
}

/** Pure and testable: no Firebase app is initialized while configuration is incomplete. */
export function resolveFirebaseClientConfiguration(
  environment: FirebaseEnvironment,
): FirebaseClientConfiguration {
  const missingVariables = firebaseRequiredEnvironmentVariables.filter(
    (key) => !readValue(environment, key),
  );

  if (missingVariables.length > 0) {
    return {
      configured: false,
      missingVariables,
      options: null,
    };
  }

  return {
    configured: true,
    missingVariables: [],
    options: {
      apiKey: readValue(environment, "VITE_FIREBASE_API_KEY"),
      authDomain: readValue(environment, "VITE_FIREBASE_AUTH_DOMAIN"),
      projectId: readValue(environment, "VITE_FIREBASE_PROJECT_ID"),
      appId: readValue(environment, "VITE_FIREBASE_APP_ID"),
      messagingSenderId: readValue(environment, "VITE_FIREBASE_MESSAGING_SENDER_ID"),
      storageBucket: readValue(environment, "VITE_FIREBASE_STORAGE_BUCKET"),
    },
  };
}

export const firebaseClientConfiguration = resolveFirebaseClientConfiguration(import.meta.env);

/**
 * A local-only escape hatch for development and browser tests. This accepts a
 * short-lived user bearer token; it must never be used in a production build.
 */
export function getDevelopmentBearerToken(
  environment: Pick<ImportMetaEnv, "DEV" | "VITE_DEV_BEARER_TOKEN"> = import.meta.env,
): string | undefined {
  if (!environment.DEV) {
    return undefined;
  }

  return environment.VITE_DEV_BEARER_TOKEN?.trim() || undefined;
}

let firebaseAuth: Auth | undefined;

export function getFirebaseAuthClient(): Auth {
  if (!firebaseClientConfiguration.configured) {
    throw new Error("Firebase Auth cannot initialize until its client configuration is complete.");
  }

  if (!firebaseAuth) {
    const app =
      getApps().length > 0 ? getApp() : initializeApp(firebaseClientConfiguration.options);
    firebaseAuth = getAuth(app);
  }

  return firebaseAuth;
}
