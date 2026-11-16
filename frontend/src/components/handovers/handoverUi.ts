import type { HandoverStatus } from "@/lib/api";

export const handoverTone = (status: HandoverStatus) =>
  (status === "accepted" ? "success" : status === "submitted" ? "primary" : status === "returned" || status === "escalated" ? "warning" : "neutral") as "success" | "primary" | "warning" | "neutral";
