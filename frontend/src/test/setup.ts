import "@testing-library/jest-dom/vitest";

import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

// Document title is global state that outlives a render, so a test asserting on
// it would otherwise be able to pass on a title an earlier test set.
const INITIAL_TITLE = document.title;

afterEach(() => {
  cleanup();
  document.title = INITIAL_TITLE;
});
