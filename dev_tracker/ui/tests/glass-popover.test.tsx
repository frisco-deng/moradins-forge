import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { GlassPopover } from "../src/components/GlassPopover";

describe("GlassPopover", () => {
  it("opens on click, closes on outside click, and supports Escape", async () => {
    const user = userEvent.setup();

    render(
      <div>
        <GlassPopover ariaLabel="Open help popover" trigger={<span>Open</span>}>
          <p>Popover copy</p>
        </GlassPopover>
        <button type="button">Outside</button>
      </div>,
    );

    await user.click(screen.getByRole("button", { name: "Open help popover" }));
    expect(screen.getByText("Popover copy")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Outside" }));
    await waitFor(() => {
      expect(screen.queryByText("Popover copy")).not.toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: "Open help popover" }));
    expect(screen.getByText("Popover copy")).toBeInTheDocument();

    await user.keyboard("{Escape}");
    await waitFor(() => {
      expect(screen.queryByText("Popover copy")).not.toBeInTheDocument();
    });
  });
});
