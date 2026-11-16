import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { renderWithLang } from "@/test/utils";
import { Sheet } from "./Sheet";

afterEach(() => {
  vi.useRealTimers();
  document.documentElement.style.overflow = "";
});

function Harness({ onClose = () => {} }: { onClose?: () => void }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button onClick={() => setOpen(true)}>open it</button>
      <Sheet
        open={open}
        title="Edit lead"
        onClose={() => {
          onClose();
          setOpen(false);
        }}
        footer={<button>save</button>}
      >
        <input aria-label="first" />
        <input aria-label="second" />
      </Sheet>
    </>
  );
}

describe("Sheet", () => {
  it("renders nothing when closed", () => {
    renderWithLang(<Sheet open={false} title="T" onClose={() => {}}>body</Sheet>);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("is a labelled modal dialog in a portal", () => {
    renderWithLang(<Sheet open title="Edit lead" onClose={() => {}}>body</Sheet>);
    const dialog = screen.getByRole("dialog", { name: "Edit lead" });
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(dialog.closest("body")).toBe(document.body);
    expect(screen.getByRole("heading", { name: "Edit lead" })).toBeInTheDocument();
  });

  it("becomes an alertdialog for destructive confirmations", () => {
    renderWithLang(<Sheet open alert title="Delete?" onClose={() => {}}>sure</Sheet>);
    expect(screen.getByRole("alertdialog", { name: "Delete?" })).toBeInTheDocument();
  });

  it("moves focus inside on open and locks page scroll, then restores both on close", async () => {
    const user = userEvent.setup();
    renderWithLang(<Harness />);
    const trigger = screen.getByRole("button", { name: "open it" });
    await user.click(trigger);
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toContainElement(document.activeElement as HTMLElement);
    expect(document.documentElement.style.overflow).toBe("hidden");
    await user.keyboard("{Escape}");
    expect(document.documentElement.style.overflow).toBe("");
    expect(trigger).toHaveFocus();
  });

  it("closes on Escape", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    renderWithLang(<Harness onClose={onClose} />);
    await user.click(screen.getByRole("button", { name: "open it" }));
    await screen.findByRole("dialog");
    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("closes when the backdrop is clicked, not when the panel is", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    renderWithLang(<Sheet open title="T" onClose={onClose}><p>inside</p></Sheet>);
    await user.click(screen.getByText("inside"));
    expect(onClose).not.toHaveBeenCalled();
    const backdrop = document.querySelector(".sheet-backdrop") as HTMLElement;
    await user.click(backdrop);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("closes with the close button (named for assistive tech)", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    renderWithLang(<Sheet open title="T" onClose={onClose}>x</Sheet>);
    const buttons = screen.getAllByRole("button", { name: "Close" });
    expect(buttons.length).toBeGreaterThan(0);
    await user.click(buttons[buttons.length - 1]);
    expect(onClose).toHaveBeenCalled();
  });

  it("omits the desktop close button with hideClose", () => {
    renderWithLang(<Sheet open hideClose title="T" onClose={() => {}}>x</Sheet>);
    // only the mobile grabber remains
    expect(screen.getAllByRole("button", { name: "Close" })).toHaveLength(1);
  });

  it("traps Tab: from the last focusable it wraps to the first, and Shift+Tab goes back", async () => {
    const user = userEvent.setup();
    renderWithLang(
      <Sheet open title="T" onClose={() => {}} footer={<button>save</button>}>
        <input aria-label="first" />
        <input aria-label="second" />
      </Sheet>,
    );
    const dialog = screen.getByRole("dialog");
    const focusables = Array.from(dialog.querySelectorAll<HTMLElement>("button, input"));
    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    act(() => last.focus());
    await user.tab();
    expect(first).toHaveFocus();
    await user.tab({ shift: true });
    expect(last).toHaveFocus();
  });

  it("focuses the data-autofocus element when present", () => {
    renderWithLang(
      <Sheet open title="T" onClose={() => {}}>
        <input aria-label="a" />
        <input aria-label="b" data-autofocus />
      </Sheet>,
    );
    expect(screen.getByLabelText("b")).toHaveFocus();
  });

  it("stays mounted for the exit animation, then unmounts", () => {
    vi.useFakeTimers();
    const { rerender } = render(<Sheet open title="T" onClose={() => {}}>x</Sheet>, { wrapper: Wrapper });
    rerender(<Sheet open={false} title="T" onClose={() => {}}>x</Sheet>);
    expect(screen.queryByRole("dialog")).toBeInTheDocument();
    expect(document.querySelector("[data-closing]")).not.toBeNull();
    act(() => {
      vi.advanceTimersByTime(300);
    });
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("renders its title in Arabic under an RTL page", () => {
    renderWithLang(<Sheet open title="تعديل" onClose={() => {}}>x</Sheet>, "ar");
    expect(document.documentElement.dir).toBe("rtl");
    expect(screen.getByRole("dialog", { name: "تعديل" })).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "إغلاق" }).length).toBeGreaterThan(0);
  });
});

import { LanguageProvider } from "@/lib/i18n";
function Wrapper({ children }: { children: React.ReactNode }) {
  return <LanguageProvider initialLang="en">{children}</LanguageProvider>;
}
