import { FileText, Wallet, BookOpen, Clock } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { StatCard, Card, CardHeader, ErrorState, Skeleton, EmptyState, HeroBanner } from "@/components/common";
import { AttendanceDonut, CategoryBarChart } from "@/components/charts";
import { useStudentDashboard } from "./queries";
import { useAuth } from "@/hooks/useAuth";
import { formatCurrency, formatTime } from "@/lib/utils";

export function StudentDashboard() {
  const { data, isLoading, isError, refetch } = useStudentDashboard();
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

  const brk = data.attendance_breakdown;
  const stat = (i: number) => Number(data.stats[i]?.value ?? 0);
  const firstName = profile?.user.full_name.split(" ")[0] ?? "Student";

  return (
    <div>
      <HeroBanner emoji="📚" title="Your Academic Snapshot" subtitle={`Welcome back, ${firstName}`}>
        <span className="opacity-90">Attendance {data.attendance_percentage}% · {stat(1)} exams taken · {data.recent_materials.length} study materials</span>
      </HeroBanner>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
        <StatCard label="Exams Taken" value={stat(1)} tone="primary" icon={FileText} />
        <StatCard label="Outstanding Fees" value={formatCurrency(stat(2))} tone={stat(2) > 0 ? "danger" : "success"} icon={Wallet} />
        <StatCard label="Materials" value={stat(3)} tone="primary" icon={BookOpen} />
      </div>

      <div className="grid lg:grid-cols-3 gap-4 mt-6">
        <Card className="card-hover">
          <CardHeader title="Attendance" subtitle="Present · Absent · Leave — click to view history" />
          <div className="p-5 flex justify-center">
            <AttendanceDonut
              present={brk.present} absent={brk.absent} leave={brk.leave}
              percentage={brk.percentage} size={240}
              onSegmentClick={() => navigate("/attendance")}
              onCentreClick={() => navigate("/attendance")}
            />
          </div>
        </Card>

        <Card>
          <CardHeader title="Today's lectures"
            action={<Link to="/timetable" className="text-xs text-indigo font-medium">Timetable</Link>} />
          {data.lecture_overview.length ? (
            <ul className="divide-y divide-slate-border">
              {data.lecture_overview.map((l) => (
                <li key={l.id} className="px-5 py-3 flex items-center gap-3">
                  <Clock size={16} className="text-indigo" />
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-ink truncate">{l.subject_name}</p>
                    <p className="text-[11px] text-slate-muted">{l.teacher_name}</p>
                  </div>
                  <span className="ml-auto text-xs text-slate-muted">{formatTime(l.start)}–{formatTime(l.end)}</span>
                </li>
              ))}
            </ul>
          ) : <EmptyState icon={Clock} title="No lectures today" />}
        </Card>

        <Card className="card-hover">
          <CardHeader title="Fee summary" subtitle="Paid vs total payable · click to view"
            action={<Link to="/student/fees" className="text-xs text-indigo font-medium">Details</Link>} />
          <div className="p-5 space-y-3">
            <Row label="Total payable" value={formatCurrency(data.fee_summary.total_invoiced)} />
            <Row label="Paid" value={formatCurrency(data.fee_summary.total_paid)} tone="text-teal" />
            <Row label="Outstanding" value={formatCurrency(data.fee_summary.total_outstanding)} tone="text-rose" />
            <div
              className="h-2.5 w-full rounded-full bg-slate-bg overflow-hidden mt-1 cursor-pointer transition-all hover:h-3"
              onClick={() => navigate("/student/fees")}
              role="button"
              aria-label="Open fee details"
              title="Click to view fee details"
            >
              <div className="h-full bg-gradient-to-r from-teal to-teal-soft rounded-full"
                style={{ width: `${data.fee_summary.total_invoiced ? (data.fee_summary.total_paid / data.fee_summary.total_invoiced) * 100 : 0}%` }} />
            </div>
          </div>
        </Card>
      </div>

      <div className="grid lg:grid-cols-3 gap-4 mt-4">
        <Card className="lg:col-span-2 card-hover">
          <CardHeader title="Academic performance" subtitle="Percentage per subject · click to view"
            action={<Link to="/results" className="text-xs text-indigo font-medium">Results</Link>} />
          <div className="p-4 cursor-pointer" onClick={() => navigate("/results")} role="button" aria-label="Open results">
            {data.subject_marks.length
              ? <CategoryBarChart data={data.subject_marks.map((m) => ({ label: m.subject_name ?? m.subject_id.slice(0, 8), value: m.percentage }))} height={240} />
              : <p className="text-sm text-slate-muted py-10 text-center">No marks recorded yet.</p>}
          </div>
        </Card>

        <Card>
          <CardHeader title="Study materials"
            action={<Link to="/materials" className="text-xs text-indigo font-medium">View all</Link>} />
          {data.recent_materials.length ? (
            <ul className="divide-y divide-slate-border">
              {data.recent_materials.map((m) => (
                <li key={m.id} className="px-5 py-3 flex items-center gap-3">
                  <BookOpen size={16} className="text-indigo" />
                  <span className="text-sm font-medium text-ink truncate">{m.title}</span>
                </li>
              ))}
            </ul>
          ) : <EmptyState icon={BookOpen} title="No materials available" />}
        </Card>
      </div>
    </div>
  );
}

function Row({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-sm text-slate-muted">{label}</span>
      <span className={`text-sm font-semibold ${tone ?? "text-ink"}`}>{value}</span>
    </div>
  );
}
