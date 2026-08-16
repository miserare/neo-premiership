import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import globals from "globals";
import tseslint from "typescript-eslint";

// package.json has carried a `lint` script since the project started, but no
// eslint and no configuration, so it has never actually run. This is that
// configuration: deliberately close to the recommended sets rather than a long
// house style, so it flags real mistakes without rewriting existing code.
export default tseslint.config(
  { ignores: ["dist", "coverage", "vite.config.js", "vite.config.d.ts", "src/data"] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],
      // An unused argument named with a leading underscore is a deliberate
      // "this parameter exists but I don't need it", not an oversight.
      "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_" }],
    },
  },
  {
    // Tests run in jsdom under vitest, so they see both browser and node
    // globals, and vitest's own globals are injected by the test config.
    files: ["src/**/*.test.{ts,tsx}", "src/test/**/*.{ts,tsx}"],
    languageOptions: {
      globals: { ...globals.browser, ...globals.node },
    },
    rules: {
      // Test helpers are never hot-reloaded, so the rule that keeps component
      // modules refresh-friendly has nothing to protect here.
      "react-refresh/only-export-components": "off",
    },
  },
);
