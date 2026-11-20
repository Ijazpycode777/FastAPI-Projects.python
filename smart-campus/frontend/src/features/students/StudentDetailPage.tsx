import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, UserCog, Power, KeyRound, CalendarOff } from "lucide-react";
import { PageHeader, Card, CardHeader, Badge, ErrorState, Skeleton, EmptyState } from "@/components/common";
import { AttendanceDonut } from "@/components/charts";
import { LeaveFormModal, LeaveHistory } from "@/features/leave";
import { http } from "@/lib/api";
import { useStudent } from "./queries";
import { useToast } from "@/hooks/useToast";
import { formatDate } from "@/lib/utils";
import type { BoardRecord, AttendanceBreakdown } from "@/types";

export function StudentDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const queryClient = useQueryClient();
  const { data: student, isLoading, isError, refetch } = useStudent(id);
  const [leaveOpen, setLeaveOpen] = useState(false);

  const breakdown = useQuery({
    queryKey: ["student", id, "breakdown"],
    queryFn: () => http.get<AttendanceBreakdown>(`/attendance/student/${id}/breakdown`),
    enabled: !!id,
  });
  const board = useQuery({
    queryKey: ["student", id, "board"],
    queryFn: () => http.get<BoardRecord[]>(`/students/${id}/board-records`),
    enabled: !!id,
  });

  if (isLoading) return <div className="space-y-4"><Skeleton className="h-8 w-48" /><Skeleton className="h-64" /></div>;
  if (isError || !student) return <ErrorState message="Student not found." onRetry={() => refetch()} />;

  const toggleActive = async () => {
    const action = student.account_status === "active" ? "deactivate" : "activate";
    await http.post(`/students/${student.id}/${action}`);
    toast.success(`Student ${action}d`);
    refetch();
  };
  const resetPassword = async () => {
    const res = await http.post<{ temporary_password: string }>(`/auth/reset/${student.user_id}`);
    toast.success("Password reset", `Temporary password: ${res.temporary_password}`);
  };
  const onLeaveSaved = () => {
    queryClient.invalidateQueries({ queryKey: ["leave", "student", student.id] });
    queryClient.invalidateQueries({ queryKey: ["student", student.id, "breakdown"] });
  };

  return (
    <div>
      <PageHeader
        title={student.full_name}
        description={`${student.admission_number} · ${student.email}`}
        action={<>
          <button onClick={() => navigate(-1)} className="btn-secondary"><ArrowLeft size={16} /> Back</button>
          <button onClick={() => navigate(`/students/${student.id}/edit`)} className="btn-secondary"><UserCog size={16} /> Edit</button>
          <button onClick={() => setLeaveOpen(true)} className="btn-secondary"><CalendarOff size={16} /> Submit leave</button>
          <button onClick={resetPassword} className="btn-secondary"><KeyRound size={16} /> Reset password</button>
          <button onClick={toggleActive} className={student.account_status === "active" ? "btn-danger" : "btn-primary"}>
            <Power size={16} /> {student.account_status === "active" ? "Deactivate" : "Activate"}
          </button>
        </>}
      />

      <div className="grid lg:grid-cols-3 gap-4">
        <Card className="lg:col-span-1">
          <CardHeader title="Profile" />
          <dl className="px-5 py-4 space-y-3 text-sm">
            <Row label="Admission No." value={student.admission_number} />
            <Row label="Email" value={student.email} />
            <Row label="Phone" value={student.phone || "—"} />
            <Row label="Date of birth" value={formatDate(student.date_of_birth)} />
            <Row label="Gender" value={student.gender || "—"} />
            <Row label="Admitted" value={formatDate(student.admission_date)} />
            <Row label="Roll No." value={student.current_roll_number ? String(student.current_roll_number) : "—"} />
            <Row label="Program" value={student.program_name || "—"} />
            <Row label="Class / Part" value={student.class_name || "—"} />
            <Row label="Section" value={student.section_name || "—"} />
            <Row label="Session" value={student.session_name || "—"} />
            <div className="flex items-center justify-between">
              <dt className="text-slate-muted">Status</dt>
              <dd><Badge status={student.account_status}>{student.account_status}</Badge></dd>
            </div>
          </dl>
        </Card>

        <div className="lg:col-span-2 space-y-4">
          <Card>
            <CardHeader title="Attendance" subtitle="Present · Absent · Leave" />
            <div className="p-5 flex justify-center">
              {breakdown.isLoading
                ? <Skeleton className="h-60 w-60 rounded-full" />
                : breakdown.data
                  ? <AttendanceDonut
                      present={breakdown.data.present} absent={breakdown.data.absent} leave={breakdown.data.leave}
                      percentage={breakdown.data.percentage} size={260}
                      onSegmentClick={() => navigate("/attendance")}
                      onCentreClick={() => navigate("/attendance")}
                    />
                  : <EmptyState icon={CalendarOff} title="No attendance records yet" />}
            </div>
          </Card>

          <LeaveHistory personType="student" personId={student.id} />

          <Card>
            <CardHeader title="Previous academic records" subtitle="Matriculation & Intermediate Part 1" />
            {board.data && board.data.length ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead><tr className="border-b border-slate-border bg-slate-bg/60"><Th>Level</Th><Th>Board</Th><Th>Year</Th><Th>Obtained</Th><Th>Total</Th><Th>%</Th><Th>Grade</Th></tr></thead>
                  <tbody>
                    {board.data.map((r) => (
                      <tr key={r.id} className="border-b border-slate-border last:border-0">
                        <Td>{r.level === "inter_part1" ? "Inter Part 1" : "Matric"}</Td>
                        <Td>{r.board}</Td><Td>{r.examination_year}</Td><Td>{r.obtained_marks}</Td><Td>{r.total_marks}</Td>
                        <Td>{r.percentage}%</Td><Td>{r.grade || "—"}</Td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : <EmptyState title="No previous records" />}
          </Card>
        </div>
      </div>

      <LeaveFormModal
        personType="student" personId={student.id}
        open={leaveOpen} onClose={() => setLeaveOpen(false)}
        onSaved={onLeaveSaved}
      />
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return <div className="flex items-center justify-between gap-3"><dt className="text-slate-muted">{label}</dt><dd className="font-medium text-ink text-right">{value}</dd></div>;
}
function Th({ children }: { children: React.ReactNode }) { return <th className="px-4 py-2 text-left font-semibold text-ink">{children}</th>; }
function Td({ children }: { children: React.ReactNode }) { return <td className="px-4 py-2.5 text-ink">{children}</td>; }
