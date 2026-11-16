import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { renderWithLang } from "@/test/utils";
import { Button, buttonClass, IconButton } from "./Button";

describe("Button", () => {
  it("is type=button by default so it never submits a form by accident", () => {
    renderWithLang(<Button>Go</Button>);
    expect(screen.getByRole("button", { name: "Go" })).toHaveAttribute("type", "button");
  });

  it("can be a submit button", () => {
    renderWithLang(<Button type="submit">Save</Button>);
    expect(screen.getByRole("button", { name: "Save" })).toHaveAttribute("type", "submit");
  });

  it("calls onClick", async () => {
    const onClick = vi.fn();
    renderWithLang(<Button onClick={onClick}>Go</Button>);
    await userEvent.click(screen.getByRole("button"));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("while loading it is disabled, marked busy, and ignores clicks (double-submit guard)", async () => {
    const onClick = vi.fn();
    renderWithLang(<Button loading onClick={onClick}>Save</Button>);
    const b = screen.getByRole("button", { name: "Save" });
    expect(b).toBeDisabled();
    expect(b).toHaveAttribute("aria-busy", "true");
    await userEvent.click(b);
    await userEvent.click(b);
    expect(onClick).not.toHaveBeenCalled();
  });

  it("is not busy and is enabled when idle", () => {
    renderWithLang(<Button>Save</Button>);
    expect(screen.getByRole("button")).toBeEnabled();
    expect(screen.getByRole("button")).not.toHaveAttribute("aria-busy");
  });

  it("respects an explicit disabled", () => {
    renderWithLang(<Button disabled>Save</Button>);
    expect(screen.getByRole("button")).toBeDisabled();
  });

  it("applies variant styling", () => {
    renderWithLang(<Button variant="danger">Delete</Button>);
    expect(screen.getByRole("button").className).toContain("bg-danger");
  });
});

describe("IconButton", () => {
  it("takes its accessible name from label and reports pressed state", () => {
    renderWithLang(<IconButton label="Bold" pressed><svg /></IconButton>);
    const b = screen.getByRole("button", { name: "Bold" });
    expect(b).toHaveAttribute("aria-pressed", "true");
  });

  it("shows the label as a tooltip", () => {
    renderWithLang(<IconButton label="Delete row"><svg /></IconButton>);
    expect(screen.getByRole("tooltip", { hidden: true })).toHaveTextContent("Delete row");
  });
});

describe("buttonClass", () => {
  it("returns variant classes for link-buttons", () => {
    expect(buttonClass("primary", "mt-6")).toContain("bg-primary-strong");
    expect(buttonClass("secondary")).toContain("border");
    expect(buttonClass("primary", "mt-6")).toContain("mt-6");
  });
});
