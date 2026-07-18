import { describe, expect, it } from "vitest";

import { getDevelopmentBearerToken, resolveFirebaseClientConfiguration } from "./firebase-client";

describe("resolveFirebaseClientConfiguration", () => {
  it("does not initialize an incomplete Firebase configuration", () => {
    const configuration = resolveFirebaseClientConfiguration({
      VITE_FIREBASE_PROJECT_ID: "codexforge-dev",
    });

    expect(configuration).toEqual({
      configured: false,
      missingVariables: [
        "VITE_FIREBASE_API_KEY",
        "VITE_FIREBASE_AUTH_DOMAIN",
        "VITE_FIREBASE_APP_ID",
      ],
      options: null,
    });
  });

  it("accepts only a complete public Firebase web configuration", () => {
    const configuration = resolveFirebaseClientConfiguration({
      VITE_FIREBASE_API_KEY: "public-web-api-key",
      VITE_FIREBASE_AUTH_DOMAIN: "codexforge-dev.firebaseapp.com",
      VITE_FIREBASE_PROJECT_ID: "codexforge-dev",
      VITE_FIREBASE_APP_ID: "1:123456789:web:abc",
      VITE_FIREBASE_MESSAGING_SENDER_ID: "123456789",
    });

    expect(configuration.configured).toBe(true);
    if (configuration.configured) {
      expect(configuration.options.projectId).toBe("codexforge-dev");
      expect(configuration.options.apiKey).toBe("public-web-api-key");
    }
  });
});

describe("getDevelopmentBearerToken", () => {
  it("refuses a development token in a production environment", () => {
    expect(
      getDevelopmentBearerToken({
        DEV: false,
        VITE_DEV_BEARER_TOKEN: "must-not-be-used-in-production",
      }),
    ).toBeUndefined();
  });
});
