import { describe, expect, it } from "vitest";
import { resolvePreviewLineLeft } from "../components/widget/SnapGuides";

describe("resolvePreviewLineLeft", () => {
  it("anchors right-edge highlights to the effective workspace width", () => {
    expect(resolvePreviewLineLeft("right", 1000)).toBe(650);
  });

  it("falls back to the left edge when preview targets the left dock", () => {
    expect(resolvePreviewLineLeft("left", 1000)).toBe(0);
  });

  it("clamps to zero for narrow workspaces", () => {
    expect(resolvePreviewLineLeft("right", 200)).toBe(0);
  });
});
