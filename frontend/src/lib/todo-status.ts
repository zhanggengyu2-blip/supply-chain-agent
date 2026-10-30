import type { TodoItem } from "./types";

export function todoStatus(value: unknown): TodoItem["status"] {
  if (value === "complete" || value === "completed") return "completed";
  if (value === "in_progress" || value === "cancelled") return value;
  return "pending";
}
