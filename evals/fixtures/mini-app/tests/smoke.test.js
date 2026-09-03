import { describe, it } from "vitest";
import { routes } from "../src/server.js";

// Deliberately assertion-free: exercises the import but proves nothing.
describe("routes", () => {
  it("loads", () => {
    routes;
  });
});
