import { describe, it, expect } from "vitest";
import { formatDate } from "../src/lib/format-date.js";

describe("formatDate", () => {
  it("pads month and day", () => {
    expect(formatDate("2026-01-05T00:00:00Z")).toBe("2026-01-05");
  });
});
