import { cleanup, fireEvent, render, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { CardExpandGrid, type CardExpandItem } from "../src/components/ui";

const items: CardExpandItem[] = [
  { id: "a", title: "Card A", subtitle: "01 A", description: "A detail" },
  { id: "b", title: "Card B", subtitle: "02 B", description: "B detail" },
  { id: "c", title: "Card C", subtitle: "03 C", description: "C detail" },
  { id: "d", title: "Card D", subtitle: "04 D", description: "D detail" },
];

describe("CardExpandGrid", () => {
  afterEach(() => {
    cleanup();
  });

  it("opens on click, switches active card, and collapses same card on second click", async () => {
    const user = userEvent.setup();
    const view = render(
      <CardExpandGrid
        items={items}
        columns={{ base: 2 }}
        renderExpanded={(item) => <p>{`expanded-${item.id}`}</p>}
      />,
    );

    const cardA = view.getByRole("button", { name: /card a/i });
    const cardC = view.getByRole("button", { name: /card c/i });

    expect(cardA).toHaveAttribute("aria-expanded", "false");
    await user.click(cardA);
    expect(cardA).toHaveAttribute("aria-expanded", "true");
    expect(view.getByText("expanded-a")).toBeInTheDocument();

    await user.click(cardC);
    expect(cardA).toHaveAttribute("aria-expanded", "false");
    expect(cardC).toHaveAttribute("aria-expanded", "true");
    expect(view.getByText("expanded-c")).toBeInTheDocument();

    await user.click(cardC);
    await waitFor(() => {
      expect(view.queryByText("expanded-c")).not.toBeInTheDocument();
    });
    expect(cardC).toHaveAttribute("aria-expanded", "false");
  });

  it("supports keyboard toggle with Enter and Space", async () => {
    const view = render(
      <CardExpandGrid items={items} columns={{ base: 2 }} renderExpanded={(item) => <p>{`expanded-${item.id}`}</p>} />,
    );

    const cardB = view.getByRole("button", { name: /card b/i });
    cardB.focus();
    fireEvent.keyDown(cardB, { key: "Enter", code: "Enter" });
    fireEvent.keyUp(cardB, { key: "Enter", code: "Enter" });

    await waitFor(() => {
      expect(view.getByText("expanded-b")).toBeInTheDocument();
    });

    fireEvent.keyDown(cardB, { key: " ", code: "Space" });
    fireEvent.keyUp(cardB, { key: " ", code: "Space" });
    await waitFor(() => {
      expect(view.queryByText("expanded-b")).not.toBeInTheDocument();
    });
  });

  it("inserts expanded panel after computed row end index", async () => {
    const user = userEvent.setup();
    const view = render(
      <CardExpandGrid
        items={items}
        columns={{ base: 2 }}
        renderExpanded={(item) => <p>{`expanded-${item.id}`}</p>}
      />,
    );

    await user.click(view.getByRole("button", { name: /card c/i }));
    const panelSlot = view.container.querySelector(".card-expand-panel-slot");
    expect(panelSlot).toBeTruthy();
    expect(panelSlot?.getAttribute("style") ?? "").toContain("--ceg-bridge-left: 0px");
    expect(panelSlot?.getAttribute("style") ?? "").toContain("--ceg-bridge-width: 0px");

    const previousElement = panelSlot?.previousElementSibling as HTMLElement | null;
    expect(previousElement?.textContent?.toLowerCase()).toContain("card d");
  });

  it(
    "closes instantly when reducedMotion is enabled",
    async () => {
      const user = userEvent.setup();
      const view = render(
        <CardExpandGrid
          items={items}
          columns={{ base: 2 }}
          reducedMotion
          renderExpanded={(item) => <p>{`expanded-${item.id}`}</p>}
        />,
      );

      const cardA = view.getByRole("button", { name: /card a/i });
      await user.click(cardA);
      expect(view.getByText("expanded-a")).toBeInTheDocument();

      await user.click(cardA);
      await waitFor(() => {
        expect(view.queryByText("expanded-a")).not.toBeInTheDocument();
      });
    },
    10_000,
  );
});
