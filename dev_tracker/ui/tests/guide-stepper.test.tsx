import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { GuideStepper } from "../src/components/GuideStepper";

describe("GuideStepper", () => {
  it("progresses through steps and completes once on the final action", async () => {
    const user = userEvent.setup();
    const onComplete = vi.fn();

    render(
      <GuideStepper
        steps={[
          { id: "step-1", title: "Access Mode", content: <p>Step one</p> },
          { id: "step-2", title: "Deploy Map", content: <p>Step two</p> },
        ]}
        onComplete={onComplete}
      />,
    );

    expect(screen.getByText("Step one")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /continue/i }));
    await waitFor(() => {
      expect(screen.getByText("Step two")).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: /complete guide/i }));
    expect(onComplete).toHaveBeenCalledTimes(1);
  });
});
