import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
    ".next-e2e/**",
    "playwright-report/**",
    "test-results/**",
  ]),
  // Playwright fixtures call a callback named `use`, which is not a React hook.
  { files: ["e2e/**"], rules: { "react-hooks/rules-of-hooks": "off" } },
]);

export default eslintConfig;
