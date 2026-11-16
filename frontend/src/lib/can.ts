import type { User } from "./api";

/**
 * Capabilities decide what to show. The server enforces every one of them again, so this only hides what would be refused.
 * Super Admin holds every capability, which the server already puts in the list.
 */
export function can(user: Pick<User, "capabilities"> | null | undefined, ...codes: string[]): boolean {
  const have = user?.capabilities;
  return !!have && codes.every((c) => have.includes(c));
}

export function canAny(user: Pick<User, "capabilities"> | null | undefined, ...codes: string[]): boolean {
  const have = user?.capabilities;
  return !!have && codes.some((c) => have.includes(c));
}
