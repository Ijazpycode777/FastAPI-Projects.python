import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { CalendarCheck } from "lucide-react";
import { PageHeader, Card, CardHeader, Badge, ErrorState, EmptyState } from "@/components/common";
import { DataTable, type Column } from "@/components/tables/DataTable";
import { http } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import type { AttendanceRecord, AttendanceSummary } from "@/types";
import { formatDate } from "@/lib/utils";

export function AttendanceHistoryPage() {
  const { profile } = useAuth();
  const role = profile?.user.role;
  const studentId = profile?.student?.id;
  const [status] = useState<string | undefined>(undefined);

  const records = useQuery({
    queryKey: ["attendance-records", role, studentId],
    queryFn: () => http.get<AttendanceRecord[]>("/attendance/records", { status }),
  });

  const summary = useQuery({
    queryKey: ["attendance-summary", studentId],
    queryFn: () => http.get<AttendanceSummary>(`/students/me/attendance`),
    enabled: role === "student",
  });

  if (records.isError) return <ErrorState message="Could not load attendance." onRetry={() => records.refetch()} />;

  const columns: Column<AttendanceRecord>[] = [
    { key: "attendance_date", header: "Date", render: (r) => formatDate(r.attendance_date) },
    { key: "subject_id", header: "Subject", render: (r) => <span className="text-slate-muted">{r.subject_id.slice(0, 8)}</span> },
    { key: "status", header: "Status", render: (r) => <Badge status={r.status} >{r.status}</Badge> },
    { key: "is_finalized", header: "Finalized", render: (r) => <span className="text-slate-muted">{r.is_finalized ? "Yes" : "No"}</span> },
    { key: "note", header: "Note", render: (r) => r.note || "—" },
  ];

  return (
    <div>
      <PageHeader title="Attendance History" description={role === "student" ? "Your lecture attendance over time." : role === "teacher" ? "Attendance you have recorded." : "All attendance records."} />
      {role === "student" && summary.data && (
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-4">
          <Mini label="Present" value={summary.data.present} />
          <Mini label="Late" value={summary.data.late} />
          <Mini label="Absent" value={summary.data.absent} />
          <Mini label="Excused" value={summary.data.excused} />
          <Mini label="Overall" value={`${summary.data.percentage}%`} />
        </div>
      )}
      <Card>
        <CardHeader title="Records" />
        <DataTable columns={columns} rows={records.data ?? []} rowKey={(r) => r.id} loading={records.isLoading}
          emptyState={<EmptyState icon={CalendarCheck} title="No attendance records yet" />} />
      </Card>
    </div>
  );
}

function Mini({ label, value }: { label: string; value: number | string }) {
  return <div className="card p-4 text-center"><p className="text-xs text-slate-muted">{label}</p><p className="text-xl font-bold text-navy mt-0.5">{value}</p></div>;
}
