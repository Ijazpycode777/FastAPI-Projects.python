import { Users, GraduationCap, Wallet, TrendingUp, Megaphone } from "lucide-react";
import { PageHeader, StatCard, Card, CardHeader, ErrorState, Skeleton } from "@/components/common";
import { TrendAreaChart, CategoryBarChart, DistributionDonut } from "@/components/charts";
import { useAdminDashboard } from "./queries";
import { formatCurrency, formatDateTime } from "@/lib/utils";
import { Link } from "react-router-dom";

export function AdminDashboard() {
  const { data, isLoading, isError, refetch } = useAdminDashboard();

  if (isError) return <ErrorState message="Failed to load dashboard data." onRetry={() => refetch()} />;
  if (isLoading || !data) return <DashboardSkeleton />;

  return (
    <div>
      <PageHeader title="Administrator Dashboard" description="College-wide overview across academics, attendance and finance." />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Active Students" value={Number(data.stats[0]?.value ?? 0)} tone="primary" icon={Users} />
        <StatCard label="Active Teachers" value={Number(data.stats[1]?.value ?? 0)} tone="primary" icon={GraduationCap} />
        <StatCard label="Total Collected" value={formatCurrency(Number(data.stats[2]?.value ?? 0))} tone="success" icon={Wallet} />
        <StatCard label="Outstanding" value={formatCurrency(Number(data.stats[3]?.value ?? 0))} tone="danger" icon={TrendingUp} />
      </div>

      <div className="grid lg:grid-cols-3 gap-4 mt-6">
        <Card className="lg:col-span-2">
          <CardHeader title="Attendance trend" subtitle="Last 7 working days — average %" />
          <div className="p-4">
            {data.attendance_trend.length ? <TrendAreaChart data={data.attendance_trend} /> : <p className="text-sm text-slate-muted py-10 text-center">No attendance recorded yet.</p>}
          </div>
        </Card>
        <Card>
          <CardHeader title="Program distribution" subtitle="Active students by program" />
          <div className="p-4">
            {data.program_distribution.length ? <DistributionDonut data={data.program_distribution} /> : <p className="text-sm text-slate-muted py-10 text-center">No data.</p>}
          </div>
        </Card>
      </div>

      <div className="grid lg:grid-cols-3 gap-4 mt-4">
        <Card className="lg:col-span-2">
          <CardHeader title="Examination performance" subtitle="Average score by exam type" />
          <div className="p-4">
            {data.examination_performance.length ? <CategoryBarChart data={data.examination_performance} /> : <p className="text-sm text-slate-muted py-10 text-center">No finalized exams yet.</p>}
          </div>
        </Card>
        <Card>
          <CardHeader title="Recent notices" action={<Link to="/notices" className="text-xs text-indigo font-medium">View all</Link>} />
          <ul className="divide-y divide-slate-border">
            {data.recent_notices.length ? data.recent_notices.map((n) => (
              <li key={n.id} className="px-5 py-3 flex items-start gap-3">
                <Megaphone size={16} className="text-indigo mt-0.5 shrink-0" />
                <div className="min-w-0">
                  <p className="text-sm font-medium text-navy truncate">{n.title}</p>
                  <p className="text-[11px] text-slate-muted">{formatDateTime(n.published_at)}</p>
                </div>
              </li>
            )) : <li className="px-5 py-8 text-center text-sm text-slate-muted">No notices published.</li>}
          </ul>
        </Card>
      </div>
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <div>
      <PageHeader title="Administrator Dashboard" />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-28" />)}
      </div>
      <div className="grid lg:grid-cols-3 gap-4 mt-6">
        <Skeleton className="lg:col-span-2 h-72" />
        <Skeleton className="h-72" />
      </div>
    </div>
  );
}
