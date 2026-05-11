import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ChangesPage } from "../src/pages/ChangesPage";

const mockUseTracker = vi.hoisted(() => vi.fn());

vi.mock("../src/lib/tracker-context", () => ({
  useTracker: () => mockUseTracker(),
}));

const longPath =
  "docs/very_long_section_name/with_a_very_very_long_filename_that_should_wrap_even_if_it_has_no_spaces_because_it_is_super_long_reference_file_name.md";

const snapshot = {
  git: {
    branch: "feature/glow-cards",
    last_commit: "1234abc | 2026-02-24 | add glow",
    dirty: true,
    markdown_changed_count: 12,
    grouped_by_section: {
      very_long_section_name: [longPath],
    },
  },
  changelog: {
    awaiting_human_review_count: 1,
    rows: [
      {
        entry_id: "CHG-001",
        cycle_id: "cycle_001",
        phase_stage: "p0-s00",
        change_type: "implementation",
        summary: "Implemented baseline patch cards and section grouping.",
        docs_updated: "Harness/artifacts/control/changelog.md;docs/11_ops/tooling_pipeline.md",
        approval_status: "approved",
      },
      {
        entry_id: "CHG-002",
        cycle_id: "cycle_002",
        phase_stage: "p0-s00",
        change_type: "tooling",
        summary: "Adjusted tracker shell styles and card rendering behavior.",
        docs_updated: "docs/00_overview/index.md",
        approval_status: "awaiting_human_review",
      },
    ],
  },
  docs: [
    {
      id: "doc-long-path",
      relative_path: longPath,
    },
  ],
} as const;

describe("changes page glowing edge cards", () => {
  beforeEach(() => {
    mockUseTracker.mockReturnValue({
      snapshot,
      settings: {
        theme: "dark",
        ambientBackground: true,
        reducedMotion: false,
      },
    });
  });

  it("renders update note cards with glowing-edge layers", () => {
    render(
      <MemoryRouter>
        <ChangesPage />
      </MemoryRouter>,
    );

    const glowNodes = document.querySelectorAll(".patch-note-gec.gec-card");
    expect(glowNodes.length).toBeGreaterThan(0);

    const firstNode = glowNodes[0] as HTMLElement;
    expect(firstNode.querySelector(".gec-border-layer")).toBeTruthy();
    expect(firstNode.querySelector(".gec-mesh-layer")).toBeTruthy();
    expect(firstNode.querySelector(".gec-halo-layer")).toBeTruthy();
    expect(firstNode.querySelector(".gec-content")).toBeTruthy();
  });

  it("updates pointer css variables on interaction", () => {
    render(
      <MemoryRouter>
        <ChangesPage />
      </MemoryRouter>,
    );

    const glowNode = document.querySelector(".patch-note-gec.gec-card") as HTMLDivElement;
    expect(glowNode).toBeTruthy();

    vi.spyOn(glowNode, "getBoundingClientRect").mockReturnValue({
      width: 320,
      height: 220,
      top: 10,
      left: 10,
      right: 330,
      bottom: 230,
      x: 10,
      y: 10,
      toJSON: () => ({}),
    } as DOMRect);

    fireEvent.pointerMove(glowNode, {
      clientX: 250,
      clientY: 160,
    });

    expect(glowNode.style.getPropertyValue("--gec-x")).not.toBe("");
    expect(glowNode.style.getPropertyValue("--gec-y")).not.toBe("");
    expect(glowNode.style.getPropertyValue("--gec-edge-x")).not.toBe("");
    expect(glowNode.style.getPropertyValue("--gec-edge-y")).not.toBe("");
    expect(glowNode.style.getPropertyValue("--gec-deg")).not.toBe("");
    expect(glowNode.style.getPropertyValue("--gec-d")).not.toBe("");

    fireEvent.pointerLeave(glowNode);
    expect(glowNode.style.getPropertyValue("--gec-d")).toBe("0");
    expect(glowNode.style.getPropertyValue("--gec-x")).toBe("50%");
    expect(glowNode.style.getPropertyValue("--gec-y")).toBe("50%");
    expect(glowNode.style.getPropertyValue("--gec-edge-x")).toBe("50%");
    expect(glowNode.style.getPropertyValue("--gec-edge-y")).toBe("50%");
  });

  it("wraps summary cards with glowing-edge wrappers without dropping card layout classes", () => {
    render(
      <MemoryRouter>
        <ChangesPage />
      </MemoryRouter>,
    );

    const summaryCards = document.querySelectorAll("section.changes-summary-gec.gec-card.card.card-pad");
    expect(summaryCards.length).toBeGreaterThanOrEqual(2);
  });

  it("keeps long by-section paths on wrap-ready classes", () => {
    render(
      <MemoryRouter>
        <ChangesPage />
      </MemoryRouter>,
    );

    const links = screen.getAllByRole("link", { name: longPath });
    expect(links.length).toBeGreaterThan(0);
    const link = links[0];
    expect(link).toHaveClass("changes-section-link");
    expect(link.parentElement).toHaveClass("changes-section-item");
    expect(screen.getAllByText("By Section").length).toBeGreaterThan(0);
  });
});
