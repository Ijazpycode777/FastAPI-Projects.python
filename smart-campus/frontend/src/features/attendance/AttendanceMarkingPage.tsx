import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { CalendarCheck, Save } from "lucide-react";
import { PageHeader, Card, CardHeader, ErrorState, Skeleton, EmptyState, Badge } from "@/components/common";
import { Select } from "@/components/forms";
import { http } from "@/lib/api";
import { useToast } from "@/hooks/useToast";
import { useAuth } from "@/hooks/useAuth";
import type { TimetableEntry, Student } from "@/types";
import { ATTENDANCE_STATUS } from "@/lib/constants";

export function AttendanceMarkingPage() {
  const { profile } = useAuth();
  const teacherId = profile?.teacher?.id;
  const toast = useToast();
  const qc = useQueryClient();

  const [entryId, setEntryId] = useState<string>("");
  const [date, setDate] = useState<string>(new Date().toISOString().slice(0, 10));
  const [statuses, setStatuses] = useState<Record<string, string>>({});

  const entries = useQuery({
    queryKey: ["my-timetable", teacherId],
    queryFn: () => http.get<TimetableEntry[]>("/timetable/me"),
    enabled: !!teacherId,
  });

  const entry = entries.data?.find((e) => e.id === entryId);
  const students = useQuery({
    queryKey: ["class-students", entry?.class_id],
    queryFn: () => http.get<{ items: Student[] } | Student[]>("/students", { class_id: entry?.class_id, page: 1, page_size: 100 }).then((r) => ("items" in r ? r.items : r)),
    enabled: !!entry?.class_id,
  });

  const markMutation = useMutation({
    mutationFn: (payload: { timetable_entry_id: string; attendance_date: string; marks: { student_id: string; status: string }[] }) =>
      http.post("/attendance/mark", payload),
    onSuccess: () => {
      toast.success("Attendance saved");
      setStatuses({});
      qc.invalidateQueries({ queryKey: ["attendance"] });
    },
    onError: (e: unknown) => toast.error("Could not save attendance", (e as Error).message),
  });

  const onSave = () => {
    if (!entryId || !date) { toast.warning("Select a lecture and date"); return; }
    const list = (students.data ?? []).map((s) => ({ student_id: s.id, status: statuses[s.id] || "present" }));
    if (!list.length) { toast.warning("No students in this class"); return; }
    markMutation.mutate({ timetable_entry_id: entryId, attendance_date: date, marks: list });
  };

  if (entries.isLoading) return <div className="space-y-4"><Skeleton className="h-8 w-48" /><Skeleton className="h-64" /></div>;
  if (entries.isError) return <ErrorState message="Could not load your timetable." />;

  return (
    <div>
      <PageHeader title="Mark Attendance" description="Select one of your scheduled lectures and record attendance per student." />
      <Card className="mb-4">
        <div className="p-5 grid sm:grid-cols-2 gap-4">
          <div>
            <label className="label">Scheduled lecture</label>
            <Select value={entryId} onChange={(e) => { setEntryId(e.target.value); setStatuses({}); }}>
              <option value="">Select a lecture…</option>
              {entries.data?.map((e) => (
                <option key={e.id} value={e.id}>{e.day_of_week} {e.start_time}–{e.end_time} · class {e.class_id.slice(0, 8)}</option>
              ))}
            </Select>
          </div>
          <div>
            <label className="label">Date</label>
            <input type="date" className="input" value={date} onChange={(e) => setDate(e.target.value)} />
          </div>
        </div>
      </Card>

      <Card>
        <CardHeader title="Students" subtitle={entry ? `Lecture on ${entry.day_of_week}` : "Pick a lecture to load students"} action={
          <button onClick={onSave} disabled={markMutation.isPending || !entryId} className="btn-primary"><Save size={16} /> {markMutation.isPending ? "Saving…" : "Save Attendance"}</button>
        } />
        {students.isLoading ? <div className="p-5"><Skeleton className="h-40" /></div> :
         (students.data?.length ?? 0) === 0 ? <EmptyState icon={CalendarCheck} title="No students" description="This class has no enrolled students." /> : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-slate-border bg-slate-bg/60">
                <th className="px-4 py-2.5 text-left font-semibold text-navy">Roll</th>
                <th className="px-4 py-2.5 text-left font-semibold text-navy">Name</th>
                <th className="px-4 py-2.5 text-left font-semibold text-navy">Admission No.</th>
                <th className="px-4 py-2.5 text-left font-semibold text-navy">Status</th>
              </tr></thead>
              <tbody>
                {students.data?.map((s, i) => (
                  <tr key={s.id} className="border-b border-slate-border last:border-0">
                    <td className="px-4 py-2.5 text-slate-muted">{i + 1}</td>
                    <td className="px-4 py-2.5 font-medium text-navy">{s.full_name}</td>
                    <td className="px-4 py-2.5 text-slate-muted">{s.admission_number}</td>
                    <td className="px-4 py-2.5">
                      <div className="flex gap-1.5">
                        {Object.values(ATTENDANCE_STATUS).map((st) => (
                          <button key={st} onClick={() => setStatuses((p) => ({ ...p, [s.id]: st }))}
                            className={`badge capitalize ${statuses[s.id] === st ? STATUS_STYLES[st] : "bg-slate-bg text-slate-muted"}`}>
                            {st}
                          </button>
                        ))}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

const STATUS_STYLES: Record<string, string> = {
  present: "bg-teal text-white",
  late: "bg-amber text-white",
  absent: "bg-rose text-white",
  excused: "bg-indigo text-white",
};
