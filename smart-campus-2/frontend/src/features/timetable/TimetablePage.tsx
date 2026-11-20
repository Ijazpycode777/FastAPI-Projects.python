import { useQuery } from "@tanstack/react-query";
import { CalendarDays } from "lucide-react";
import { PageHeader, Card, ErrorState, EmptyState, Badge } from "@/components/common";
import { http } from "@/lib/api";
import type { TimetableEntry } from "@/types";
import { formatTime } from "@/lib/utils";

const DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"];

export function TimetablePage() {
  const { data, isLoading, isError, refetch } = useQuery({ queryKey: ["my-timetable-view"], queryFn: () => http.get<TimetableEntry[]>("/timetable/me") });

  if (isError) return <ErrorState message="Could not load timetable." onRetry={() => refetch()} />;

  const byDay: Record<string, TimetableEntry[]> = {};
  for (const d of DAYS) byDay[d] = [];
  (data ?? []).forEach((e) => { (byDay[e.day_of_week] ??= []).push(e); });

  return (
    <div>
      <PageHeader title="Timetable" description="Your weekly lecture schedule." />
      {isLoading ? <div className="grid lg:grid-cols-5 gap-3">{DAYS.slice(0, 5).map((d) => <Card key={d} className="h-64 animate-pulse"><span /></Card>)}</div> :
       (data?.length ?? 0) === 0 ? <Card><EmptyState icon={CalendarDays} title="No timetable entries" description="Your schedule will appear here once lectures are scheduled." /></Card> : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-5 gap-3">
          {DAYS.slice(0, 5).map((day) => (
            <Card key={day}>
              <div className="px-4 py-3 border-b border-slate-border capitalize font-semibold text-navy text-sm">{day}</div>
              <div className="p-3 space-y-2 min-h-[120px]">
                {byDay[day].length ? byDay[day].map((e) => (
                  <div key={e.id} className="rounded-lg bg-slate-bg p-2.5 border border-slate-border">
                    <p className="text-xs font-semibold text-indigo">{formatTime(e.start_time)} – {formatTime(e.end_time)}</p>
                    <p className="text-sm text-navy mt-0.5 truncate">{e.subject_name || e.subject_id.slice(0, 8)}</p>
                    {e.classroom_number && <p className="text-[11px] text-slate-muted">Room {e.classroom_number}</p>}
                  </div>
                )) : <p className="text-xs text-slate-muted text-center py-6">No lectures</p>}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
