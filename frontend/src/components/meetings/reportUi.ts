import type { MeetingReport } from "@/lib/api";

export const reportTone = (status: MeetingReport["status"]) => (status === "approved" ? "success" : status === "signed" ? "primary" : status === "returned" ? "warning" : "neutral") as "success" | "primary" | "warning" | "neutral";
