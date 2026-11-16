import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { renderWithLang } from "@/test/utils";
import { Segmented } from "./Segmented";

const segs = [
  { value: "a", label: "Alpha" },
  { value: "b", label: "Beta" },
  { value: "c", label: "Gamma" },
];

describe("Segmented", () => {
  it("is a radiogroup with one checked radio and a roving tabindex", () => {
    renderWithLang(<Segmented segments={segs} value="b" onChange={() => {}} label="Pick" />);
    expect(screen.getByRole("radiogroup", { name: "Pick" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Beta" })).toBeChecked();
    expect(screen.getByRole("radio", { name: "Alpha" })).not.toBeChecked();
    expect(screen.getByRole("radio", { name: "Beta" })).toHaveAttribute("tabindex", "0");
    expect(screen.getByRole("radio", { name: "Alpha" })).toHaveAttribute("tabindex", "-1");
  });

  it("can be a tablist with aria-selected", () => {
    renderWithLang(<Segmented mode="tablist" segments={segs} value="a" onChange={() => {}} label="Views" />);
    expect(screen.getByRole("tablist", { name: "Views" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Alpha" })).toHaveAttribute("aria-selected", "true");
  });

  it("clicking selects", async () => {
    const onChange = vi.fn();
    renderWithLang(<Segmented segments={segs} value="a" onChange={onChange} label="Pick" />);
    await userEvent.click(screen.getByRole("radio", { name: "Gamma" }));
    expect(onChange).toHaveBeenCalledWith("c");
  });

  it("ArrowRight moves forward in English and wraps around", async () => {
    const onChange = vi.fn();
    renderWithLang(<Segmented segments={segs} value="c" onChange={onChange} label="Pick" />);
    screen.getByRole("radio", { name: "Gamma" }).focus();
    await userEvent.keyboard("{ArrowRight}");
    expect(onChange).toHaveBeenLastCalledWith("a");
  });

  it("ArrowRight is mirrored in RTL (moves to the previous segment)", async () => {
    const onChange = vi.fn();
    renderWithLang(<Segmented segments={segs} value="b" onChange={onChange} label="Pick" />, "ar");
    screen.getByRole("radio", { name: "Beta" }).focus();
    await userEvent.keyboard("{ArrowRight}");
    expect(onChange).toHaveBeenLastCalledWith("a");
    await userEvent.keyboard("{ArrowLeft}");
    expect(onChange).toHaveBeenLastCalledWith("c");
  });

  it("Home and End jump to the ends, Up and Down step", async () => {
    const onChange = vi.fn();
    renderWithLang(<Segmented segments={segs} value="b" onChange={onChange} label="Pick" />);
    screen.getByRole("radio", { name: "Beta" }).focus();
    await userEvent.keyboard("{End}");
    expect(onChange).toHaveBeenLastCalledWith("c");
    await userEvent.keyboard("{Home}");
    expect(onChange).toHaveBeenLastCalledWith("a");
    await userEvent.keyboard("{ArrowDown}");
    expect(onChange).toHaveBeenLastCalledWith("c");
    await userEvent.keyboard("{ArrowUp}");
    expect(onChange).toHaveBeenLastCalledWith("a");
  });

  it("ignores unrelated keys", async () => {
    const onChange = vi.fn();
    renderWithLang(<Segmented segments={segs} value="a" onChange={onChange} label="Pick" />);
    screen.getByRole("radio", { name: "Alpha" }).focus();
    await userEvent.keyboard("x");
    expect(onChange).not.toHaveBeenCalled();
  });
});
