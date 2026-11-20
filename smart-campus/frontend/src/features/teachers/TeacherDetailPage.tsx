import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, CalendarOff, CalendarDays } from "lucide-react";
import { PageHeader, Card, CardHeader, Badge, ErrorState, Skeleton } from "@/components/common";
import { LeaveFormModal, LeaveHistory } from "@/features/leave";
import { http } from "@/lib/api";
import { useToast } from "@/hooks/useToast";
import { formatDate } from "@/lib/utils";
import type { Teacher } from "@/types";

export function TeacherDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [leaveOpen, setLeaveOpen] = useState(false);

  const { data: teacher, isLoading, isError, refetch } = useQuery({
    queryKey: ["teacher", id],
    queryFn: () => http.get<Teacher>(`/teachers/${id}`),
    enabled: !!id,
  });

  if (isLoading) return <div className="space-y-4"><Skeleton className="h-8 w-48" /><Skeleton className="h-64" /></div>;
  if (isError || !teacher) return <ErrorState message="Teacher not found." onRetry={() => refetch()} />;

  const onLeaveSaved = () => {
    queryClient.invalidateQueries({ queryKey: ["leave", "teacher", teacher.id] });
  };

  return (
    <div>
      <PageHeader
        title={teacher.full_name}
        description={`${teacher.employee_id} · ${teacher.email}`}
        action={<>
          <button onClick={() => navigate(-1)} className="btn-secondary"><ArrowLeft size={16} /> Back</button>
          <button onClick={() => navigate("/timetable")} className="btn-secondary"><CalendarDays size={16} /> Timetable</button>
          <button onClick={() => setLeaveOpen(true)} className="btn-secondary"><CalendarOff size={16} /> Submit leave</button>
        </>}
      />

      <div className="grid lg:grid-cols-3 gap-4">
        <Card className="lg:col-span-1">
          <CardHeader title="Profile" />
          <dl className="px-5 py-4 space-y-3 text-sm">
            <Row label="Employee ID" value={teacher.employee_id} />
            <Row label="Email" value={teacher.email} />
            <Row label="Phone" value={teacher.phone || "—"} />
            <Row label="Department" value={teacher.department || "—"} />
            <Row label="Designation" value={teacher.designation} />
            <Row label="Joined" value={formatDate(teacher.joining_date)} />
            <div className="flex items-center justify-between">
              <dt className="text-slate-muted">Status</dt>
              <dd><Badge status={teacher.employment_status}>{teacher.employment_status}</Badge></dd>
            </div>
          </dl>
        </Card>

        <div className="lg:col-span-2 space-y-4">
          <LeaveHistory personType="teacher" personId={teacher.id} />
        </div>
      </div>

      <LeaveFormModal
        personType="teacher" personId={teacher.id}
        open={leaveOpen} onClose={() => setLeaveOpen(false)}
        onSaved={onLeaveSaved}
      />
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return <div className="flex items-center justify-between gap-3"><dt className="text-slate-muted">{label}</dt><dd className="font-medium text-ink text-right">{value}</dd></div>;
}
