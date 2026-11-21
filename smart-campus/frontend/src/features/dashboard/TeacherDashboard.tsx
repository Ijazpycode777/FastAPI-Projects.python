import { BookOpen, Clock, CalendarDays, FileText, Users } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { StatCard, Card, CardHeader, ErrorState, Skeleton, EmptyState, HeroBanner } from "@/components/common";
import { HorizontalBarChart, CategoryBarChart, CHART_COLORS } from "@/components/charts";
import { useTeacherDashboard } from "./queries";
import { useAuth } from "@/hooks/useAuth";
import { formatTime } from "@/lib/utils";

const DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"];
const DAY_LABEL: Record<string, string> = { monday: "Mon", tuesday: "Tue", wednesday: "Wed", thursday: "Thu", friday: "Fri", saturday: "Sat", sunday: "Sun" };

function subjectColor(name: string): string {
  let h = 0;
  for (const c of name) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return CHART_COLORS[h % CHART_COLORS.length];
}

export function TeacherDashboard() {
  const { data, isLoading, isError, refetch } = useTeacherDashboard();
  const { profile } = useAuth();
  const navigate = useNavigate();
  if (isError) return <ErrorState message="Failed to load your dashboard." onRetry={() => refetch()} />;
  if (isLoading || !data) return (
    <div className="space-y-4">
      <Skeleton className="h-8 w-64" />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">{Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-28" />)}</div>
      <Skeleton className="h-72" />
    </div>
  );

  const stat = (i: number) => Number(data.stats[i]?.value ?? 0);
  const firstName = profile?.user.full_name.split(" ")[0] ?? "Teacher";
  const byDay = DAYS
    .map((d) => ({ day: d, lectures: data.weekly_timetable.filter((e) => e.day === d) }))
    .filter((g) => g.lectures.length);

  return (
    <div>
      <HeroBanner emoji="📖" title="Your Teaching Overview" subtitle={`Welcome back, ${firstName}`}>
        <span className="opacity-90">{stat(0)} assigned classes · {stat(1)} lectures today · {stat(3)} students across classes</span>
      </HeroBanner>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Assigned Classes" value={stat(0)} tone="primary" icon={BookOpen} />
        <StatCard label="Today's Lectures" value={stat(1)} tone="primary" icon={Clock} />
        <StatCard label="Weekly Lectures" value={stat(2)} tone="primary" icon={CalendarDays} />
        <StatCard label="Students in Classes" value={stat(3)} tone="primary" icon={Users} />
      </div>

      <div className="grid lg:grid-cols-3 gap-4 mt-6">
        <Card className="lg:col-span-2 card-hover">
          <CardHeader title="Weekly timetable" subtitle="Your scheduled lectures · click a lecture to open"
            action={<Link to="/timetable" className="text-xs text-indigo font-medium">Full timetable</Link>} />
          {byDay.length ? (
            <div className="p-4 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
              {byDay.map((g) => (
                <div key={g.day} className="rounded-lg border border-slate-border bg-slate-bg/40 p-2">
                  <p className="text-xs font-semibold text-ink mb-2">{DAY_LABEL[g.day]}</p>
                  <div className="space-y-2">
                    {g.lectures.map((e) => (
                      <button key={e.id} onClick={() => navigate("/timetable")}
                        className="block w-full text-left rounded-md p-2 text-white"
                        style={{ backgroundColor: subjectColor(e.subject_name) }}>
                        <p className="text-[11px] font-semibold leading-tight">{e.subject_name}</p>
                        <p className="text-[10px] opacity-90">{formatTime(e.start)}–{formatTime(e.end)}</p>
                        <p className="text-[10px] opacity-90">{e.class_name}{e.section_name ? ` · ${e.section_name}` : ""}</p>
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          ) : <EmptyState icon={CalendarDays} title="No lectures scheduled" description="Your timetable is empty." />}
        </Card>

        <Card className="card-hover">
          <CardHeader title="Class distribution" subtitle="Students per assigned class · click to view" />
          <div className="p-4 cursor-pointer" onClick={() => navigate("/timetable")} role="button" aria-label="Open timetable">
            {data.class_distribution.length
              ? <HorizontalBarChart data={data.class_distribution} height={260} />
              : <p className="text-sm text-slate-muted py-10 text-center">No assigned classes.</p>}
          </div>
        </Card>
      </div>

      <div className="grid lg:grid-cols-2 gap-4 mt-4">
        <Card className="card-hover">
          <CardHeader title="Student performance" subtitle="Average mark % per subject · click to view"
            action={<Link to="/results" className="text-xs text-indigo font-medium">View</Link>} />
          <div className="p-4 cursor-pointer" onClick={() => navigate("/results")} role="button" aria-label="Open results">
            {data.student_performance.length
              ? <CategoryBarChart data={data.student_performance} height={240} />
              : <p className="text-sm text-slate-muted py-10 text-center">No marks recorded yet.</p>}
          </div>
        </Card>

        <Card>
          <CardHeader title="Upcoming examinations" />
          {data.upcoming_examinations.length ? (
            <ul className="divide-y divide-slate-border">
              {data.upcoming_examinations.map((e) => (
                <li key={e.id} className="px-5 py-3 flex items-center gap-3">
                  <FileText size={16} className="text-amber" />
                  <span className="text-sm font-medium text-ink truncate">{e.name}</span>
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
