import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { renderWithLang } from "@/test/utils";
import { PasswordChecklist } from "./PasswordChecklist";

const rule = (name: RegExp) => screen.getByText(name).closest("li") as HTMLElement;
const strength = () => screen.getByText(/^Strength:/).textContent;

describe("PasswordChecklist", () => {
  it("starts with nothing met and strength 'Not set'", () => {
    renderWithLang(<PasswordChecklist password="" confirm="" sameAsTemporary={false} />);
    expect(strength()).toBe("Strength: Not set");
    for (const r of [/At least 12 characters/, /Different from your temporary/, /Matches the confirmation/]) {
      expect(within(rule(r)).getByText("Not met yet")).toBeInTheDocument();
    }
  });

  it("marks the length rule only from 12 characters", () => {
    const { rerender } = renderWithLang(<PasswordChecklist password="abcdefghijk" confirm="" />);
    expect(within(rule(/At least 12/)).getByText("Not met yet")).toBeInTheDocument();
    rerender(<PasswordChecklist password="abcdefghijkl" confirm="" />);
    expect(within(rule(/At least 12/)).getByText("Met")).toBeInTheDocument();
  });

  it("the match rule needs a non-empty equal confirmation", () => {
    const { rerender } = renderWithLang(<PasswordChecklist password="" confirm="" />);
    expect(within(rule(/Matches/)).getByText("Not met yet")).toBeInTheDocument();
    rerender(<PasswordChecklist password="abc" confirm="abd" />);
    expect(within(rule(/Matches/)).getByText("Not met yet")).toBeInTheDocument();
    rerender(<PasswordChecklist password="abc" confirm="abc" />);
    expect(within(rule(/Matches/)).getByText("Met")).toBeInTheDocument();
  });

  it("the different-from-temporary rule fails when it is the same password, passes when different", () => {
    const { rerender } = renderWithLang(<PasswordChecklist password="same-password-1" confirm="" sameAsTemporary />);
    expect(within(rule(/Different from/)).getByText("Not met yet")).toBeInTheDocument();
    rerender(<PasswordChecklist password="other-password-1" confirm="" sameAsTemporary={false} />);
    expect(within(rule(/Different from/)).getByText("Met")).toBeInTheDocument();
  });

  it("does not claim the different-rule is met when the temporary password is unknown", () => {
    renderWithLang(<PasswordChecklist password="whatever-long-password" confirm="" />);
    expect(within(rule(/Different from/)).getByText("Not met yet")).toBeInTheDocument();
  });

  it("scales strength with length, mixed case plus digits, and symbols", () => {
    const { rerender } = renderWithLang(<PasswordChecklist password="short" confirm="" />);
    expect(strength()).toBe("Strength: Not set");
    rerender(<PasswordChecklist password="abcdefghijkl" confirm="" />);
    expect(strength()).toBe("Strength: Weak");
    rerender(<PasswordChecklist password="abcdefghijklmnop" confirm="" />);
    expect(strength()).toBe("Strength: Fair");
    rerender(<PasswordChecklist password="Abcdefghijklmn12" confirm="" />);
    expect(strength()).toBe("Strength: Good");
    rerender(<PasswordChecklist password="Abcdefghijklmn12!" confirm="" />);
    expect(strength()).toBe("Strength: Strong");
  });

  it("is announced politely and renders in Arabic", () => {
    renderWithLang(<PasswordChecklist password="x" confirm="" />, "ar");
    expect(document.querySelector("[aria-live=polite]")).not.toBeNull();
    expect(screen.queryByText(/At least 12 characters/)).toBeNull();
  });
});
