import { create } from "zustand";
import type { Payload, User } from "./types";
export const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
export const useFleet = create<{
  user: User | null;
  live: Payload | null;
  connection: string;
  setUser: (user: User | null) => void;
  setLive: (live: Payload) => void;
  setConnection: (connection: string) => void;
}>((set) => ({
  user: null,
  live: null,
  connection: "offline",
  setUser: (user) => set({ user }),
  setLive: (live) => set({ live }),
  setConnection: (connection) => set({ connection }),
}));
export async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${API}/api/v1${path}`, {
    credentials: "include",
    method: body === undefined ? "GET" : "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": useFleet.getState().user?.csrf || "",
      "Idempotency-Key": crypto.randomUUID(),
    },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  if (!response.ok) {
    const text = await response.text();
    let detail = text;
    try {
      detail = JSON.parse(text).detail;
    } catch {}
    throw new Error(
      typeof detail === "string" ? detail : JSON.stringify(detail),
    );
  }
  return response.json() as Promise<T>;
}
