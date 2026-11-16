import { act, renderHook, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { Input } from "@/components/ui/Field";
import { renderWithLang } from "@/test/utils";
import { isEmail, useForm } from "./useForm";

const validate = (v: Record<string, string>) => ({
  ...(!v.name.trim() ? { name: "v.fullName" } : {}),
  ...(!isEmail(v.email) ? { email: "v.emailFormat" } : {}),
});

function Demo() {
  const form = useForm({ name: "", email: "" }, validate);
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        form.check();
      }}
      noValidate
    >
      <Input label="Name" {...form.field("name")} />
      <Input label="Email" type="email" {...form.field("email")} />
      <button type="submit">go</button>
    </form>
  );
}

describe("isEmail", () => {
  it.each([
    ["a@b.co", true],
    ["name@company.com", true],
    ["a@b", false],
    ["a b@c.com", false],
    ["", false],
    ["@x.com", false],
  ])("%s -> %s", (v, ok) => {
    expect(isEmail(v)).toBe(ok);
  });
});

describe("useForm (hook)", () => {
  it("starts clean and updates values through field().onChange", () => {
    const { result } = renderHook(() => useForm({ name: "", email: "" }, validate));
    expect(result.current.errors).toEqual({});
    act(() => result.current.field("name").onChange({ target: { value: "Dee" } }));
    expect(result.current.values.name).toBe("Dee");
  });

  it("validates only the blurred field", () => {
    const { result } = renderHook(() => useForm({ name: "", email: "" }, validate));
    act(() => result.current.field("name").onBlur());
    expect(result.current.errors).toEqual({ name: "v.fullName" });
  });

  it("does not flag a blurred field that is valid", () => {
    const { result } = renderHook(() => useForm({ name: "Dee", email: "" }, validate));
    act(() => result.current.field("name").onBlur());
    expect(result.current.errors).toEqual({});
  });

  it("clears a field error on input, on focus and via setValue", () => {
    const { result } = renderHook(() => useForm({ name: "", email: "" }, validate));
    act(() => result.current.field("name").onBlur());
    act(() => result.current.field("name").onFocus());
    expect(result.current.errors.name).toBeUndefined();
    act(() => result.current.field("email").onBlur());
    expect(result.current.errors.email).toBe("v.emailFormat");
    act(() => result.current.field("email").onChange({ target: { value: "a" } }));
    expect(result.current.errors.email).toBeUndefined();
    act(() => result.current.field("name").onBlur());
    act(() => result.current.setValue("name", "x"));
    expect(result.current.errors.name).toBeUndefined();
  });

  it("check() returns false and fills every error when invalid, true when fine", () => {
    const { result } = renderHook(() => useForm({ name: "", email: "" }, validate));
    let ok = true;
    act(() => {
      ok = result.current.check();
    });
    expect(ok).toBe(false);
    expect(Object.keys(result.current.errors).sort()).toEqual(["email", "name"]);
    act(() => result.current.setValue("name", "A"));
    act(() => result.current.setValue("email", "a@b.co"));
    act(() => {
      ok = result.current.check();
    });
    expect(ok).toBe(true);
    expect(result.current.errors).toEqual({});
  });
});

describe("useForm (in a form)", () => {
  it("shows no error while typing, an error after blur, and removes it when the person returns", async () => {
    const user = userEvent.setup();
    renderWithLang(<Demo />);
    const name = screen.getByLabelText("Name");
    await user.click(name);
    await user.type(name, "x");
    await user.clear(name);
    expect(screen.queryByRole("alert")).toBeNull();
    await user.tab();
    expect(await screen.findByRole("alert")).toHaveTextContent("Enter the person's full name.");
    expect(name).toHaveAttribute("aria-invalid", "true");
    await user.click(name);
    expect(document.getElementById("error-name")).toBeNull();
    expect(name).not.toHaveAttribute("aria-invalid");
  });

  it("on submit shows every error and focuses the first invalid field, keeping its error visible", async () => {
    const user = userEvent.setup();
    renderWithLang(<Demo />);
    await user.click(screen.getByRole("button", { name: "go" }));
    expect(screen.getAllByRole("alert")).toHaveLength(2);
    expect(screen.getByLabelText("Name")).toHaveFocus();
    expect(screen.getByLabelText("Name")).toHaveAttribute("aria-invalid", "true");
  });

  it("never disables the submit button for invalid data", () => {
    renderWithLang(<Demo />);
    expect(screen.getByRole("button", { name: "go" })).toBeEnabled();
  });
});
