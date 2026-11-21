import { Users, GraduationCap, Wallet, TrendingUp, Layers, Megaphone } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { PageHeader, StatCard, Card, CardHeader, ErrorState, Skeleton, HeroBanner } from "@/components/common";
import { TrendAreaChart, CategoryBarChart, DistributionDonut, HorizontalBarChart } from "@/components/charts";
import { useAdminDashboard } from "./queries";
import { useAuth } from "@/hooks/useAuth";
import { formatCurrency, formatDateTime } from "@/lib/utils";

export function AdminDashboard() {
  const { data, isLoading, isError, refetch } = useAdminDashboard();
  const { profile } = useAuth();
  const navigate = useNavigate();

  if (isError) return <ErrorState message="Failed to load dashboard data." onRetry={() => refetch()} />;
  if (isLoading || !data) return <DashboardSkeleton />;

  const stat = (i: number) => Number(data.stats[i]?.value ?? 0);
  const firstName = profile?.user.full_name.split(" ")[0] ?? "Admin";

  return (
    <div>
      <HeroBanner emoji="🎓" title="College at a Glance" subtitle={`Welcome back, ${firstName}`}>
        <span className="opacity-90">{stat(0)} students · {stat(1)} teachers · {stat(2)} active classes · {formatCurrency(stat(4))} collected</span>
      </HeroBanner>

      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        <Link to="/students"><StatCard label="Total Students" value={stat(0)} tone="primary" icon={Users} /></Link>
        <Link to="/teachers"><StatCard label="Total Teachers" value={stat(1)} tone="primary" icon={GraduationCap} /></Link>
        <Link to="/students"><StatCard label="Active Classes" value={stat(2)} tone="primary" icon={Layers} /></Link>
        <Link to="/students"><StatCard label="Total Sections" value={stat(3)} tone="primary" icon={Layers} /></Link>
        <Link to="/fees"><StatCard label="Fee Collection" value={formatCurrency(stat(4))} tone="success" icon={Wallet} /></Link>
        <Link to="/fees"><StatCard label="Outstanding Fees" value={formatCurrency(stat(5))} tone="danger" icon={TrendingUp} /></Link>
      </div>

      <div className="grid lg:grid-cols-3 gap-4 mt-6">
        <Card className="card-hover">
          <CardHeader title="Student enrolment" subtitle="Active students by program · click to view"
            action={<Link to="/students" className="text-xs text-indigo font-medium">View</Link>} />
          <div className="p-4 cursor-pointer" onClick={() => navigate("/students")} role="button" aria-label="Open student list">
            {data.program_distribution.length
              ? <DistributionDonut data={data.program_distribution} height={260} />
              : <p className="text-sm text-slate-muted py-10 text-center">No enrolled students yet.</p>}
          </div>
        </Card>
        <Card className="lg:col-span-2 card-hover">
          <CardHeader title="Fee collection" subtitle="Collected amount by month · click to view"
            action={<Link to="/fees" className="text-xs text-indigo font-medium">View</Link>} />
          <div className="p-4 cursor-pointer" onClick={() => navigate("/fees")} role="button" aria-label="Open fee management">
            {data.fee_collection_trend.length
              ? <TrendAreaChart data={data.fee_collection_trend} />
              : <p className="text-sm text-slate-muted py-10 text-center">No payments recorded yet.</p>}
          </div>
        </Card>
      </div>

      <div className="grid lg:grid-cols-3 gap-4 mt-4">
        <Card className="lg:col-span-2 card-hover">
          <CardHeader title="Class & section comparison" subtitle="Enrolled students per class · section · click to view"
            action={<Link to="/students" className="text-xs text-indigo font-medium">View</Link>} />
          <div className="p-4 cursor-pointer" onClick={() => navigate("/students")} role="button" aria-label="Open student list">
            {data.class_comparison.length
              ? <HorizontalBarChart data={data.class_comparison} height={260} />
              : <p className="text-sm text-slate-muted py-10 text-center">No enrolments yet.</p>}
          </div>
        </Card>
        <Card className="card-hover">
          <CardHeader title="Examination performance" subtitle="Average score by exam type · click to view"
            action={<Link to="/examinations" className="text-xs text-indigo font-medium">View</Link>} />
          <div className="p-4 cursor-pointer" onClick={() => navigate("/examinations")} role="button" aria-label="Open examinations">
            {data.examination_performance.length
              ? <CategoryBarChart data={data.examination_performance} height={260} />
              : <p className="text-sm text-slate-muted py-10 text-center">No finalized exams yet.</p>}
          </div>
        </Card>
      </div>

      {data.top_performers.length > 0 && (
        <div className="mt-4 grid sm:grid-cols-2 gap-4">
          {data.top_performers.map((p) => (
            <Card key={p.student_id} className="p-5 flex items-center gap-4 animate-slideUp">
              <div className="h-12 w-12 rounded-full bg-indigo/10 text-indigo grid place-items-center font-bold text-sm shrink-0">
                {p.name.split(" ").slice(0, 2).map((w) => w[0]?.toUpperCase() ?? "").join("")}
              </div>
              <div className="min-w-0">
                <p className="font-semibold text-ink truncate">{p.name}</p>
                <p className="text-xs text-slate-muted">{p.category}</p>
              </div>
              <div className="ml-auto text-right">
                <p className="text-xl font-bold text-indigo">{p.score}</p>
                <p className="text-[11px] text-slate-muted">{p.metric}</p>
              </div>
            </Card>
          ))}
        </div>
      )}

      <Card className="mt-4">
        <CardHeader title="Recent notices" action={<Link to="/notices" className="text-xs text-indigo font-medium">View all</Link>} />
        <ul className="divide-y divide-slate-border">
          {data.recent_notices.length ? data.recent_notices.map((n) => (
            <li key={n.id} className="px-5 py-3 flex items-start gap-3">
              <Megaphone size={16} className="text-indigo mt-0.5 shrink-0" />
              <div className="min-w-0">
                <p className="text-sm font-medium text-ink truncate">{n.title}</p>
                <p className="text-[11px] text-slate-muted">{formatDateTime(n.published_at)}</p>
              </div>
            </li>
          )) : <li className="px-5 py-8 text-center text-sm text-slate-muted">No notices published.</li>}
        </ul>
      </Card>
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <div>
      <PageHeader title="Administrator Dashboard" />
      <div className="grid grid-cols-2 lg:grid-cols-6 gap-4">
        {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-28" />)}
      </div>
      <div className="grid lg:grid-cols-3 gap-4 mt-6">
        <Skeleton className="h-72" />
        <Skeleton className="lg:col-span-2 h-72" />
      </div>
    </div>
  );
}
