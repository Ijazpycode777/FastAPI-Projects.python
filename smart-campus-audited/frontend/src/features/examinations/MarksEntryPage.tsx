import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Save, Lock, Send } from "lucide-react";
import { PageHeader, Card, CardHeader, ErrorState, Skeleton, EmptyState, Badge } from "@/components/common";
import { http } from "@/lib/api";
import { useToast } from "@/hooks/useToast";
import { useState } from "react";
import type { Examination, StudentMark, Student } from "@/types";

export function MarksEntryPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const qc = useQueryClient();
  const [marks, setMarks] = useState<Record<string, { marks: string; absent: boolean }>>({});

  const exam = useQuery({ queryKey: ["exam", id], queryFn: () => http.get<Examination>(`/examinations/${id}`), enabled: !!id });
  const existing = useQuery({ queryKey: ["exam", id, "marks"], queryFn: () => http.get<StudentMark[]>(`/examinations/${id}/marks`), enabled: !!id });
  const students = useQuery({
    queryKey: ["exam-students", exam.data?.class_id],
    queryFn: () => http.get<{ items: Student[] } | Student[]>("/students", { class_id: exam.data?.class_id, page: 1, page_size: 100 }).then((r) => "items" in r ? r.items : r),
    enabled: !!exam.data?.class_id,
  });

  const saveMutation = useMutation({
    mutationFn: () => {
      const entries = (students.data ?? []).map((s) => {
        const m = marks[s.id] ?? { marks: "", absent: false };
        const existingMark = existing.data?.find((x) => x.student_id === s.id);
        return { student_id: s.id, marks_obtained: m.absent ? 0 : Number(m.marks || existingMark?.marks_obtained || 0), is_absent: m.absent };
      });
      return http.post(`/examinations/${id}/marks`, { entries });
    },
    onSuccess: () => { toast.success("Marks saved"); qc.invalidateQueries({ queryKey: ["exam", id, "marks"] }); },
    onError: (e: unknown) => toast.error("Could not save marks", (e as Error).message),
  });

  const finalize = useMutation({
    mutationFn: () => http.post(`/examinations/${id}/finalize`),
    onSuccess: () => { toast.success("Examination finalized"); qc.invalidateQueries({ queryKey: ["exam", id] }); },
    onError: (e: unknown) => toast.error("Could not finalize", (e as Error).message),
  });

  if (exam.isLoading) return <Skeleton className="h-64" />;
  if (exam.isError || !exam.data) return <ErrorState message="Examination not found." />;

  const e = exam.data;
  const isFinalized = e.status === "finalized";

  return (
    <div>
      <PageHeader title={e.name} description={`${e.exam_type.replace("_", " ")} · ${e.max_marks} marks · pass ${e.passing_marks}`}
        action={<>
          <button onClick={() => navigate("/examinations")} className="btn-secondary"><ArrowLeft size={16} /> Back</button>
          <button onClick={() => { exam.refetch(); existing.refetch(); }} className="btn-secondary">Refresh</button>
        </>} />

      <div className="flex items-center gap-2 mb-4">
        <Badge status={e.status}>{e.status}</Badge>
        {!isFinalized && <button onClick={() => saveMutation.mutate()} disabled={saveMutation.isPending} className="btn-primary"><Save size={16} /> {saveMutation.isPending ? "Saving…" : "Save Marks"}</button>}
        {e.status === "published" && <button onClick={() => finalize.mutate()} disabled={finalize.isPending} className="btn-danger"><Lock size={16} /> Finalize</button>}
        {e.status === "draft" && <button onClick={async () => { await http.post(`/examinations/${id}/publish`); toast.success("Published"); exam.refetch(); }} className="btn-secondary"><Send size={16} /> Publish</button>}
      </div>

      <Card>
        <CardHeader title="Marks entry" subtitle={isFinalized ? "Finalized — read only" : "Enter marks per student. Absent students are recorded separately."} />
        {(students.data?.length ?? 0) === 0 ? <EmptyState title="No students in this class" /> : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-slate-border bg-slate-bg/60">
                <th className="px-4 py-2.5 text-left font-semibold text-navy">#</th>
                <th className="px-4 py-2.5 text-left font-semibold text-navy">Student</th>
                <th className="px-4 py-2.5 text-left font-semibold text-navy">Marks / {e.max_marks}</th>
                <th className="px-4 py-2.5 text-left font-semibold text-navy">Absent</th>
                <th className="px-4 py-2.5 text-left font-semibold text-navy">%</th>
                <th className="px-4 py-2.5 text-left font-semibold text-navy">Grade</th>
                <th className="px-4 py-2.5 text-left font-semibold text-navy">Pass</th>
              </tr></thead>
              <tbody>
                {students.data?.map((s, i) => {
                  const em = existing.data?.find((x) => x.student_id === s.id);
                  const cur = marks[s.id];
                  return (
                    <tr key={s.id} className="border-b border-slate-border last:border-0">
                      <td className="px-4 py-2.5 text-slate-muted">{i + 1}</td>
                      <td className="px-4 py-2.5 font-medium text-navy">{s.full_name}</td>
                      <td className="px-4 py-2.5">
                        <input type="number" min={0} max={e.max_marks} disabled={isFinalized}
                          className="input !w-24" defaultValue={em?.marks_obtained ?? ""}
                          onChange={(ev) => setMarks((p) => ({ ...p, [s.id]: { marks: ev.target.value, absent: false } }))} />
                      </td>
                      <td className="px-4 py-2.5">
                        <input type="checkbox" disabled={isFinalized} defaultChecked={em?.is_absent}
                          onChange={(ev) => setMarks((p) => ({ ...p, [s.id]: { marks: "", absent: ev.target.checked } }))} />
                      </td>
                      <td className="px-4 py-2.5 text-slate-muted">{em?.percentage ?? "—"}</td>
                      <td className="px-4 py-2.5">{em?.grade ? <Badge>{em.grade}</Badge> : "—"}</td>
                      <td className="px-4 py-2.5">{em ? (em.is_pass ? <span className="text-teal font-medium">Yes</span> : <span className="text-rose font-medium">No</span>) : "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
