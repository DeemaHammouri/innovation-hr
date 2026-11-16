import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { renderWithLang } from "@/test/utils";
import { Input, SearchField, Select, Textarea } from "./Field";

describe("Input", () => {
  it("links the label to the control", () => {
    renderWithLang(<Input name="full_name" label="Full name" />);
    expect(screen.getByLabelText("Full name")).toHaveAttribute("id", "field-full_name");
  });

  it("marks required fields visibly and natively", () => {
    renderWithLang(<Input name="n" label="Name" required />);
    expect(screen.getByLabelText(/Name/)).toBeRequired();
    expect(screen.getByText("(required)")).toBeInTheDocument();
  });

  it("with an error: aria-invalid, aria-describedby pointing at an alert with the translated message", () => {
    renderWithLang(<Input name="email" label="Email" error="v.emailFormat" hint="We never share it" />);
    const input = screen.getByLabelText("Email");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAttribute("aria-describedby", "error-email");
    const alert = screen.getByRole("alert");
    expect(alert).toHaveAttribute("id", "error-email");
    expect(alert).toHaveTextContent("Enter an email like name@company.com.");
    // the error replaces the hint
    expect(screen.queryByText("We never share it")).toBeNull();
  });

  it("shows the hint, wired by aria-describedby, when there is no error", () => {
    renderWithLang(<Input name="email" label="Email" hint="We never share it" />);
    const input = screen.getByLabelText("Email");
    expect(input).not.toHaveAttribute("aria-invalid");
    expect(input).toHaveAttribute("aria-describedby", "hint-email");
    expect(document.getElementById("hint-email")).toHaveTextContent("We never share it");
  });

  it("has no describedby when there is neither hint nor error", () => {
    renderWithLang(<Input name="x" label="X" />);
    expect(screen.getByLabelText("X")).not.toHaveAttribute("aria-describedby");
  });

  it("translates an Arabic error message when the page is Arabic", () => {
    renderWithLang(<Input name="x" label="X" error="v.fullName" />, "ar");
    expect(screen.getByRole("alert")).not.toHaveTextContent("Enter the person's full name.");
    expect(screen.getByRole("alert").textContent).toMatch(/[؀-ۿ]/);
  });

  it.each(["email", "tel", "password", "url"])("forces ltr for type=%s", (type) => {
    renderWithLang(<Input name="f" label="F" type={type} />, "ar");
    expect(screen.getByLabelText("F")).toHaveAttribute("dir", "ltr");
  });

  it("leaves text fields to follow the page direction", () => {
    renderWithLang(<Input name="f" label="F" />, "ar");
    expect(screen.getByLabelText("F")).not.toHaveAttribute("dir");
  });

  it("password: toggles visibility with a labelled, pressed button", async () => {
    const user = userEvent.setup();
    renderWithLang(<Input name="pw" label="Password" type="password" />);
    const input = screen.getByLabelText("Password");
    expect(input).toHaveAttribute("type", "password");
    const toggle = screen.getByRole("button", { name: "Show password" });
    expect(toggle).toHaveAttribute("aria-pressed", "false");
    await user.click(toggle);
    expect(input).toHaveAttribute("type", "text");
    expect(screen.getByRole("button", { name: "Hide password" })).toHaveAttribute("aria-pressed", "true");
    await user.click(screen.getByRole("button", { name: "Hide password" }));
    expect(input).toHaveAttribute("type", "password");
  });

  it("passes value and change events through", async () => {
    const onChange = vi.fn();
    renderWithLang(<Input name="n" label="N" value="" onChange={onChange} />);
    await userEvent.type(screen.getByLabelText("N"), "ab");
    expect(onChange).toHaveBeenCalledTimes(2);
  });
});

describe("Select", () => {
  it("renders options with a placeholder and wires aria for errors", () => {
    renderWithLang(
      <Select name="department" label="Department" placeholder="Choose" error="v.chooseDept" options={[{ value: "1", label: "HR" }, { value: "2", label: "Operation" }]} />,
    );
    const sel = screen.getByLabelText("Department");
    expect(sel).toHaveAttribute("aria-invalid", "true");
    expect(sel).toHaveAttribute("aria-describedby", "error-department");
    expect(screen.getAllByRole("option").map((o) => o.textContent)).toEqual(["Choose", "HR", "Operation"]);
    expect(screen.getByRole("alert")).toHaveTextContent("Choose a department.");
  });

  it("lets the user pick an option", async () => {
    const onChange = vi.fn();
    renderWithLang(<Select name="s" label="S" onChange={onChange} options={[{ value: "a", label: "A" }, { value: "b", label: "B" }]} />);
    await userEvent.selectOptions(screen.getByLabelText("S"), "b");
    expect(onChange).toHaveBeenCalled();
    expect(screen.getByLabelText("S")).toHaveValue("b");
  });
});

describe("Textarea", () => {
  it("is labelled and marks invalid", () => {
    renderWithLang(<Textarea name="notes" label="Notes" error="err.required" />);
    const ta = screen.getByLabelText("Notes");
    expect(ta.tagName).toBe("TEXTAREA");
    expect(ta).toHaveAttribute("aria-invalid", "true");
    expect(ta).toHaveAttribute("aria-describedby", "error-notes");
  });
});

describe("SearchField", () => {
  it("has an accessible label, and a clear button only when there is text", async () => {
    const onChange = vi.fn();
    const { rerender } = renderWithLang(<SearchField label="Search clients" value="" onChange={onChange} placeholder="Search" />);
    expect(screen.getByLabelText("Search clients")).toHaveAttribute("type", "search");
    expect(screen.queryByRole("button", { name: "Clear search" })).toBeNull();
    rerender(<SearchField label="Search clients" value="acme" onChange={onChange} placeholder="Search" />);
    await userEvent.click(screen.getByRole("button", { name: "Clear search" }));
    expect(onChange).toHaveBeenCalledWith("");
  });
});
