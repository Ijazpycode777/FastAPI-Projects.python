import { CalendarCheck, FileText, Wallet, BookOpen } from "lucide-react";
import { PageHeader, StatCard, Card, CardHeader, ErrorState, Skeleton, EmptyState } from "@/components/common";
import { useStudentDashboard } from "./queries";
import { formatCurrency } from "@/lib/utils";
import { Link } from "react-router-dom";

export function StudentDashboard() {
  const { data, isLoading, isError, refetch } = useStudentDashboard();
  if (isError) return <ErrorState message="Failed to load your dashboard." onRetry={() => refetch()} />;
  if (isLoading || !data) return <div className="space-y-4"><Skeleton className="h-8 w-64" /><div className="grid grid-cols-2 lg:grid-cols-4 gap-4">{Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-28" />)}</div></div>;

  return (
    <div>
      <PageHeader title="Student Dashboard" description="Your academic overview, attendance, results and resources." />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Attendance" value={`${data.attendance_percentage}%`} tone={data.attendance_percentage >= 75 ? "success" : "warning"} icon={CalendarCheck} />
        <StatCard label="Exams Taken" value={Number(data.stats[1]?.value ?? 0)} tone="primary" icon={FileText} />
        <StatCard label="Outstanding Fees" value={formatCurrency(Number(data.stats[2]?.value ?? 0))} tone={Number(data.stats[2]?.value ?? 0) > 0 ? "danger" : "success"} icon={Wallet} />
        <StatCard label="Materials" value={Number(data.stats[3]?.value ?? 0)} tone="primary" icon={BookOpen} />
      </div>

      <div className="grid lg:grid-cols-2 gap-4 mt-6">
        <Card>
          <CardHeader title="Subject marks" subtitle="Latest percentage per subject" />
          {data.subject_marks.length ? (
            <ul className="divide-y divide-slate-border">
              {data.subject_marks.map((m, i) => (
                <li key={i} className="px-5 py-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-navy">Subject {m.subject_id.slice(0, 8)}</span>
                    <span className="text-sm font-semibold text-indigo">{m.percentage}% {m.grade && `· ${m.grade}`}</span>
                  </div>
                  <div className="mt-1.5 h-1.5 w-full rounded-full bg-slate-bg overflow-hidden">
                    <div className="h-full bg-indigo rounded-full" style={{ width: `${Math.min(m.percentage, 100)}%` }} />
                  </div>
                </li>
              ))}
            </ul>
          ) : <EmptyState icon={FileText} title="No marks recorded yet" />}
        </Card>

        <Card>
          <CardHeader title="Fee summary" action={<Link to="/student/fees" className="text-xs text-indigo font-medium">Details</Link>} />
          <div className="p-5 grid grid-cols-3 gap-4 text-center">
            <div><p className="text-xs text-slate-muted">Invoiced</p><p className="text-lg font-bold text-navy mt-1">{formatCurrency(data.fee_summary.total_invoiced)}</p></div>
            <div><p className="text-xs text-slate-muted">Paid</p><p className="text-lg font-bold text-teal mt-1">{formatCurrency(data.fee_summary.total_paid)}</p></div>
            <div><p className="text-xs text-slate-muted">Outstanding</p><p className="text-lg font-bold text-rose mt-1">{formatCurrency(data.fee_summary.total_outstanding)}</p></div>
          </div>
          <div className="px-5 pb-5">
            <div className="h-2 w-full rounded-full bg-slate-bg overflow-hidden">
              <div className="h-full bg-teal rounded-full" style={{ width: `${data.fee_summary.total_invoiced ? (data.fee_summary.total_paid / data.fee_summary.total_invoiced) * 100 : 0}%` }} />
            </div>
          </div>
        </Card>
      </div>

      <Card className="mt-4">
        <CardHeader title="Recent study materials" action={<Link to="/materials" className="text-xs text-indigo font-medium">View all</Link>} />
        {data.recent_materials.length ? (
          <ul className="divide-y divide-slate-border">
            {data.recent_materials.map((m) => (
              <li key={m.id} className="px-5 py-3 flex items-center gap-3">
                <BookOpen size={16} className="text-indigo" />
                <span className="text-sm font-medium text-navy truncate">{m.title}</span>
              </li>
            ))}
          </ul>
        ) : <EmptyState icon={BookOpen} title="No materials available yet" />}
      </Card>
    </div>
  );
}
