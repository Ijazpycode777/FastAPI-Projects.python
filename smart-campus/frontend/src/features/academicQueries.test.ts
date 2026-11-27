import { describe, it, expect } from "vitest";
import { computeRosterRefetchMs } from "./academicQueries";
import type { ClassRoster } from "@/types";

/** Build a minimal roster with the given server_now + today's lectures. */
function roster(serverNow: string, lectures: { start_time: string; end_time: string }[]): ClassRoster {
  return {
    class_id: "c1", class_name: "Part 1", program_name: "ICS", year: 1,
    students: [], lectures_today: lectures.map((l) => ({
      start_time: l.start_time, end_time: l.end_time,
      section_id: null, section_name: null, subject_name: null,
    })),
    server_now: serverNow, timezone: "UTC",
  };
}

describe("computeRosterRefetchMs", () => {
  it("returns 30s when there is no data yet", () => {
    expect(computeRosterRefetchMs(undefined)).toBe(30_000);
  });

  it("returns 30s when server_now is unparseable", () => {
    expect(computeRosterRefetchMs(roster("not-a-date", []))).toBe(30_000);
  });

  it("returns 60s when there are no lectures today (no upcoming transition)", () => {
    expect(computeRosterRefetchMs(roster("2026-01-05T09:30:00+00:00", []))).toBe(60_000);
  });

  it("returns 60s when all of today's lectures are already in the past", () => {
    const r = roster("2026-01-05T11:30:00+00:00", [{ start_time: "09:00", end_time: "10:00" }]);
    expect(computeRosterRefetchMs(r)).toBe(60_000);
  });

  it("caps a far-future transition to 60s", () => {
    // 09:30 now, next lecture starts at 10:00 (30 min away) -> capped at 60s.
    const r = roster("2026-01-05T09:30:00+00:00", [{ start_time: "10:00", end_time: "11:00" }]);
    expect(computeRosterRefetchMs(r)).toBe(60_000);
  });

  it("schedules a refetch just past the next end boundary (prompt transition)", () => {
    // 09:59:30 now, lecture ends at 10:00 (30s away) -> 30s + 1s grace = 31s.
    const r = roster("2026-01-05T09:59:30+00:00", [{ start_time: "09:00", end_time: "10:00" }]);
    expect(computeRosterRefetchMs(r)).toBe(31_000);
  });

  it("schedules a refetch just past the next start boundary", () => {
    // 09:59:30 now, next lecture starts at 10:00 (30s away) -> 31s.
    const r = roster("2026-01-05T09:59:30+00:00", [
      { start_time: "09:00", end_time: "09:30" },   // past
      { start_time: "10:00", end_time: "11:00" },   // upcoming start
    ]);
    expect(computeRosterRefetchMs(r)).toBe(31_000);
  });

  it("never polls tighter than 3s, even for an imminent boundary", () => {
    // 09:59:59 now, lecture ends at 10:00 (1s away) -> 1s + 1s = 2s -> clamped to 3s.
    const r = roster("2026-01-05T09:59:59+00:00", [{ start_time: "09:00", end_time: "10:00" }]);
    expect(computeRosterRefetchMs(r)).toBe(3_000);
  });

  it("respects the college timezone offset when composing lecture timestamps", () => {
    // server_now at 09:30 UTC+05:30 (= 04:00 UTC). A lecture at 10:00 local
    // (same college day) is 30 min away -> capped 60s. If the offset were
    // ignored, the lecture would be mis-composed as UTC 10:00 (5h30m away) and
    // the test would still cap to 60s, so instead assert the imminent case:
    // 09:59:30+05:30 with a 10:00 end -> 31s (proves offset is applied).
    const r = roster("2026-01-05T09:59:30+05:30", [{ start_time: "09:00", end_time: "10:00" }]);
    expect(computeRosterRefetchMs(r)).toBe(31_000);
  });
});
