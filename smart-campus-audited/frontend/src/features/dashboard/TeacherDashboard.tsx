import { CalendarDays, BookOpen, Clock, FileText } from "lucide-react";
import { PageHeader, StatCard, Card, CardHeader, ErrorState, Skeleton, EmptyState } from "@/components/common";
import { useTeacherDashboard } from "./queries";
import { formatTime } from "@/lib/utils";

export function TeacherDashboard() {
  const { data, isLoading, isError, refetch } = useTeacherDashboard();
  if (isError) return <ErrorState message="Failed to load your dashboard." onRetry={() => refetch()} />;
  if (isLoading || !data) return <div className="space-y-4"><Skeleton className="h-8 w-64" /><div className="grid grid-cols-2 lg:grid-cols-4 gap-4">{Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-28" />)}</div></div>;

  return (
    <div>
      <PageHeader title="Teacher Dashboard" description="Your classes, timetable and upcoming work at a glance." />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Assigned Classes" value={Number(data.stats[0]?.value ?? 0)} tone="primary" icon={BookOpen} />
        <StatCard label="Assigned Subjects" value={Number(data.stats[1]?.value ?? 0)} tone="primary" icon={BookOpen} />
        <StatCard label="Today's Lectures" value={Number(data.stats[2]?.value ?? 0)} tone="primary" icon={Clock} />
        <StatCard label="Upcoming Exams" value={Number(data.stats[3]?.value ?? 0)} tone="warning" icon={FileText} />
      </div>

      <div className="grid lg:grid-cols-2 gap-4 mt-6">
        <Card>
          <CardHeader title="Today's timetable" subtitle="Your scheduled lectures today" />
          {data.today_timetable.length ? (
            <ul className="divide-y divide-slate-border">
              {data.today_timetable.map((t) => (
                <li key={t.id} className="px-5 py-3 flex items-center gap-3">
                  <CalendarDays size={16} className="text-indigo" />
                  <span className="text-sm font-medium text-navy">{formatTime(t.start)} – {formatTime(t.end)}</span>
                  <span className="ml-auto text-xs text-slate-muted">Class {t.class_id.slice(0, 8)}</span>
                </li>
              ))}
            </ul>
          ) : <EmptyState icon={CalendarDays} title="No lectures today" description="Enjoy the lighter schedule." />}
        </Card>

        <Card>
          <CardHeader title="Upcoming examinations" />
          {data.upcoming_examinations.length ? (
            <ul className="divide-y divide-slate-border">
              {data.upcoming_examinations.map((e) => (
                <li key={e.id} className="px-5 py-3 flex items-center gap-3">
                  <FileText size={16} className="text-amber" />
                  <span className="text-sm font-medium text-navy truncate">{e.name}</span>
                  <span className="ml-auto text-xs text-slate-muted">{e.date}</span>
                </li>
              ))}
            </ul>
          ) : <EmptyState icon={FileText} title="No upcoming exams" />}
        </Card>
      </div>
    </div>
  );
}
