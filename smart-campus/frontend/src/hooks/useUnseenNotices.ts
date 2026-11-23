/**
 * useUnseenNotices — powers the Topbar bell badge.
 *
 * - Reuses the shared ["notices"] query cache (same key as NoticesPage), so the
 *   bell and the notices view never disagree.
 * - "Ongoing" notice = no expiry, or expiry still in the future (the backend
 *   returns every visible notice regardless of expiry, so we filter client-side).
 * - "Seen" IDs are persisted per-user in localStorage; the red dot shows only
 *   while at least one ongoing notice is unseen, and clears the moment the user
 *   opens the notices view (bell click or direct navigation).
 */
import { useCallback } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { http } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import type { Notice } from "@/types";

const STORAGE_PREFIX = "smartcampus:notices:seen:";

function seenKey(userId: string): string {
  return STORAGE_PREFIX + userId;
}

function readSeen(userId: string): Set<string> {
  try {
    const raw = localStorage.getItem(seenKey(userId));
    if (!raw) return new Set();
    const arr: unknown = JSON.parse(raw);
    return Array.isArray(arr)
      ? new Set(arr.filter((x): x is string => typeof x === "string"))
      : new Set();
  } catch {
    return new Set();
  }
}

function writeSeen(userId: string, ids: string[]): void {
  try {
    localStorage.setItem(seenKey(userId), JSON.stringify(ids));
  } catch {
    /* storage unavailable (private mode / quota) — degrade silently */
  }
}

/** A notice is ongoing when it has no expiry or its expiry is still in the future. */
function isOngoing(n: Notice, now: Date): boolean {
  if (!n.expires_at) return true;
  const t = new Date(n.expires_at).getTime();
  return Number.isNaN(t) || t > now.getTime();
}

export function useUnseenNotices() {
  const { profile } = useAuth();
  const qc = useQueryClient();
  // Fall back to "anon" so the hook is safe before login; the query is disabled
  // until a profile exists, so no fetch happens for the anon bucket.
  const userId = profile?.user.id ?? "anon";

  const { data } = useQuery<Notice[]>({
    queryKey: ["notices"],
    queryFn: () => http.get<Notice[]>("/notices"),
    enabled: !!profile,
    staleTime: 30_000,
  });

  const now = new Date();
  const seen = readSeen(userId);
  const ongoing = (data ?? []).filter((n) => isOngoing(n, now));
  const unseen = ongoing.filter((n) => !seen.has(n.id));

  // Stable callback: reads the freshest cached notices at call time (not the
  // render-time closure) so it stays referentially stable across renders —
  // letting NoticesPage depend on it without re-firing every render.
  const markAllSeen = useCallback(() => {
    const notices = qc.getQueryData<Notice[]>(["notices"]) ?? [];
    const ids = notices.filter((n) => isOngoing(n, new Date())).map((n) => n.id);
    if (ids.length === 0) return;
    const seenNow = readSeen(userId);
    let changed = false;
    for (const id of ids) {
      if (!seenNow.has(id)) {
        seenNow.add(id);
        changed = true;
      }
    }
    if (changed) {
      writeSeen(userId, Array.from(seenNow));
      // Invalidate so subscribers (the bell dot) recompute against the fresh
      // seen set. The shared cache means NoticesPage stays in sync too.
      qc.invalidateQueries({ queryKey: ["notices"] });
    }
  }, [userId, qc]);

  return { unseenCount: unseen.length, hasUnseen: unseen.length > 0, markAllSeen };
}
