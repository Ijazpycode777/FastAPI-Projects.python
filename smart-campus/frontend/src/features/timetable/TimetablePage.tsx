import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarDays, Plus, Pencil, Trash2 } from "lucide-react";
import { PageHeader, Card, CardHeader, ErrorState, EmptyState, Modal, Skeleton } from "@/components/common";
import { Field, TextInput, Select } from "@/components/forms";
import { http, ApiError } from "@/lib/api";
import { useToast } from "@/hooks/useToast";
import { useAuth } from "@/hooks/useAuth";
import { formatTime } from "@/lib/utils";
import type { TimetableEntry, AcademicSession, ClassLevel, Section, Subject, Classroom, Teacher, Page } from "@/types";

const DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday"];
const DAY_LABEL: Record<string, string> = { monday: "Mon", tuesday: "Tue", wednesday: "Wed", thursday: "Thu", friday: "Fri" };
const subjectColor = (name: string) => {
  const palette = ["#2457A6", "#23865B", "#D99A27", "#163A70", "#9AA3AF"];
  let h = 0; for (const c of name) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return palette[h % palette.length];
};

export function TimetablePage() {
  const { profile } = useAuth();
  const role = profile?.user.role;
  if (role === "admin") return <AdminTimetable />;
  return <ReadOnlyTimetable />;
}

// ---------------- Read-only (teacher / student) ----------------
function ReadOnlyTimetable() {
  const { data, isLoading, isError, refetch } = useQuery({ queryKey: ["my-timetable-view"], queryFn: () => http.get<TimetableEntry[]>("/timetable/me") });
  if (isError) return <ErrorState message="Could not load timetable." onRetry={() => refetch()} />;
  const byDay: Record<string, TimetableEntry[]> = {};
  for (const d of DAYS) byDay[d] = [];
  (data ?? []).forEach((e) => { (byDay[e.day_of_week] ??= []).push(e); });
  return (
    <div>
      <PageHeader title="Timetable" description="Your weekly lecture schedule." />
      {isLoading ? <div className="grid lg:grid-cols-5 gap-3">{DAYS.map((d) => <Card key={d} className="h-64 animate-pulse"><span /></Card>)}</div>
        : (data?.length ?? 0) === 0 ? <Card><EmptyState icon={CalendarDays} title="No timetable entries" description="Your schedule will appear here once lectures are scheduled." /></Card>
        : (
          <div className="grid sm:grid-cols-2 lg:grid-cols-5 gap-3">
            {DAYS.map((day) => (
              <Card key={day}>
                <div className="px-4 py-3 border-b border-slate-border font-semibold text-ink text-sm">{DAY_LABEL[day]}</div>
                <div className="p-3 space-y-2 min-h-[120px]">
                  {byDay[day].length ? byDay[day].map((e) => (
                    <div key={e.id} className="rounded-lg p-2.5 text-white" style={{ backgroundColor: subjectColor(e.subject_name || e.subject_id) }}>
                      <p className="text-xs font-semibold">{formatTime(e.start_time)} – {formatTime(e.end_time)}</p>
                      <p className="text-sm mt-0.5 truncate">{e.subject_name || e.subject_id.slice(0, 8)}</p>
                      {e.classroom_number && <p className="text-[11px] opacity-90">Room {e.classroom_number}</p>}
                    </div>
                  )) : <p className="text-xs text-slate-muted text-center py-6">No lectures</p>}
                </div>
              </Card>
            ))}
          </div>
        )}
    </div>
  );
}

// ---------------- Admin CRUD ----------------
function AdminTimetable() {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [sessionId, setSessionId] = useState("");
  const [classId, setClassId] = useState("");
  const [sectionId, setSectionId] = useState("");
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<TimetableEntry | null>(null);

  const sessions = useQuery({ queryKey: ["sessions"], queryFn: () => http.get<AcademicSession[]>("/sessions") });
  const classes = useQuery({ queryKey: ["classes"], queryFn: () => http.get<ClassLevel[]>("/classes") });
  const sections = useQuery({ queryKey: ["sections"], queryFn: () => http.get<Section[]>("/sections") });
  const subjects = useQuery({ queryKey: ["subjects"], queryFn: () => http.get<Subject[]>("/subjects") });
  const classrooms = useQuery({ queryKey: ["classrooms"], queryFn: () => http.get<Classroom[]>("/classrooms") });
  const teachers = useQuery({ queryKey: ["teachers", "all"], queryFn: () => http.get<Page<Teacher>>("/teachers", { page: 1, page_size: 100 }) });

  const entries = useQuery({
    queryKey: ["timetable", "entries", sessionId, classId, sectionId],
    queryFn: () => http.get<TimetableEntry[]>("/timetable/entries", {
      academic_session_id: sessionId || undefined,
      class_id: classId || undefined, section_id: sectionId || undefined,
    }),
    enabled: !!sessionId,
  });

  const classSections = (sections.data ?? []).filter((s) => s.class_level_id === classId);
  const byDay: Record<string, TimetableEntry[]> = {};
  for (const d of DAYS) byDay[d] = [];
  (entries.data ?? []).forEach((e) => { (byDay[e.day_of_week] ??= []).push(e); });

  const openCreate = () => { setEditing(null); setModalOpen(true); };
  const openEdit = (e: TimetableEntry) => { setEditing(e); setModalOpen(true); };
  const remove = async (id: string) => {
    if (!confirm("Delete this lecture?")) return;
    try { await http.del(`/timetable/entries/${id}`); queryClient.invalidateQueries({ queryKey: ["timetable"] }); toast.success("Lecture deleted"); }
    catch (e) { toast.error("Could not delete", (e as ApiError).message); }
  };

  return (
    <div>
      <PageHeader title="Timetable Administration" description="Build the weekly schedule. Conflicts (teacher / classroom / class overlap) are rejected."
        action={<button onClick={openCreate} className="btn-primary" disabled={!sessionId}><Plus size={16} /> Add lecture</button>} />

      <div className="card p-4 mb-4 grid grid-cols-2 sm:grid-cols-3 gap-2">
        <Field label="Academic session">
          <Select value={sessionId} onChange={(e) => setSessionId(e.target.value)}>
            <option value="">Select session…</option>
            {sessions.data?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </Select>
        </Field>
        <Field label="Class">
          <Select value={classId} onChange={(e) => { setClassId(e.target.value); setSectionId(""); }}>
            <option value="">All classes</option>
            {classes.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </Select>
        </Field>
        <Field label="Section">
          <Select value={sectionId} onChange={(e) => setSectionId(e.target.value)} disabled={!classId}>
            <option value="">{classId ? "All sections" : "Select class"}</option>
            {classSections.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </Select>
        </Field>
      </div>

      {!sessionId ? (
        <Card><EmptyState icon={CalendarDays} title="Select an academic session" description="Choose a session to view and build the timetable." /></Card>
      ) : entries.isError ? <ErrorState message="Could not load timetable." onRetry={() => entries.refetch()} />
      : entries.isLoading ? <div className="grid lg:grid-cols-5 gap-3">{DAYS.map((d) => <Skeleton key={d} className="h-64" />)}</div>
      : (entries.data?.length ?? 0) === 0 ? <Card><EmptyState icon={CalendarDays} title="No lectures scheduled" description="Add a lecture to start building the week." action={<button className="btn-primary" onClick={openCreate}><Plus size={16} /> Add lecture</button>} /></Card>
      : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-5 gap-3">
          {DAYS.map((day) => (
            <Card key={day}>
              <div className="px-4 py-3 border-b border-slate-border font-semibold text-ink text-sm">{DAY_LABEL[day]}</div>
              <div className="p-3 space-y-2 min-h-[120px]">
                {byDay[day].length ? byDay[day].map((e) => (
                  <div key={e.id} className="rounded-lg p-2.5 text-white" style={{ backgroundColor: subjectColor(e.subject_name || e.subject_id) }}>
                    <div className="flex items-start justify-between gap-1">
                      <p className="text-xs font-semibold">{formatTime(e.start_time)} – {formatTime(e.end_time)}</p>
                      <div className="flex gap-1">
                        <button onClick={() => openEdit(e)} className="rounded bg-white/20 hover:bg-white/30 p-0.5"><Pencil size={12} /></button>
                        <button onClick={() => remove(e.id)} className="rounded bg-white/20 hover:bg-white/30 p-0.5"><Trash2 size={12} /></button>
                      </div>
                    </div>
                    <p className="text-sm mt-0.5 truncate">{e.subject_name || "—"}</p>
                    <p className="text-[11px] opacity-90 truncate">{e.teacher_name || "—"}</p>
                    {e.classroom_number && <p className="text-[11px] opacity-90">Room {e.classroom_number}</p>}
                  </div>
                )) : <p className="text-xs text-slate-muted text-center py-6">No lectures</p>}
              </div>
            </Card>
          ))}
        </div>
      )}

      {modalOpen && (
        <EntryModal
          editing={editing}
          sessionId={sessionId}
          classes={classes.data ?? []}
          sections={sections.data ?? []}
          subjects={subjects.data ?? []}
          teachers={teachers.data?.items ?? []}
          classrooms={classrooms.data ?? []}
          onClose={() => setModalOpen(false)}
          onSaved={() => { setModalOpen(false); queryClient.invalidateQueries({ queryKey: ["timetable"] }); }}
        />
      )}
    </div>
  );
}

function EntryModal({ editing, sessionId, classes, sections, subjects, teachers, classrooms, onClose, onSaved }: {
  editing: TimetableEntry | null;
  sessionId: string;
  classes: ClassLevel[];
  sections: Section[];
  subjects: Subject[];
  teachers: Teacher[];
  classrooms: Classroom[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const toast = useToast();
  const [form, setForm] = useState({
    day_of_week: editing?.day_of_week ?? "monday",
    start_time: (editing?.start_time ?? "08:30").slice(0, 5),
    end_time: (editing?.end_time ?? "09:30").slice(0, 5),
    subject_id: editing?.subject_id ?? "",
    teacher_id: editing?.teacher_id ?? "",
    class_id: editing?.class_id ?? "",
    section_id: editing?.section_id ?? "",
    classroom_id: editing?.classroom_id ?? "",
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const classSections = sections.filter((s) => s.class_level_id === form.class_id);
  const cls = classes.find((c) => c.id === form.class_id);
  const classSubjects = cls ? subjects.filter((s) => s.program_id === cls.program_id) : subjects;

  const submit = async () => {
    setError(null);
    if (!form.subject_id || !form.teacher_id || !form.class_id) { setError("Subject, teacher and class are required."); return; }
    setSubmitting(true);
    const payload = {
      academic_session_id: sessionId, day_of_week: form.day_of_week,
      start_time: form.start_time, end_time: form.end_time,
      subject_id: form.subject_id, teacher_id: form.teacher_id, class_id: form.class_id,
      section_id: form.section_id || null, classroom_id: form.classroom_id || null,
    };
    try {
      if (editing) await http.patch(`/timetable/entries/${editing.id}`, payload);
      else await http.post("/timetable/entries", payload);
      toast.success(editing ? "Lecture updated" : "Lecture created");
      onSaved();
    } catch (e) {
      setError((e as ApiError).message);
    } finally { setSubmitting(false); }
  };

  return (
    <Modal open onClose={onClose} title={editing ? "Edit lecture" : "Add lecture"}
      footer={<>
        <button className="btn-secondary" onClick={onClose}>Cancel</button>
        <button className="btn-primary" disabled={submitting} onClick={submit}>{submitting ? "Saving…" : (editing ? "Save changes" : "Add lecture")}</button>
      </>}>
      <div className="space-y-4">
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          <Field label="Day" required>
            <Select value={form.day_of_week} onChange={(e) => setForm({ ...form, day_of_week: e.target.value })}>
              {DAYS.map((d) => <option key={d} value={d}>{DAY_LABEL[d]}</option>)}
            </Select>
          </Field>
          <Field label="Start time" required><TextInput type="time" value={form.start_time} onChange={(e) => setForm({ ...form, start_time: e.target.value })} /></Field>
          <Field label="End time" required><TextInput type="time" value={form.end_time} onChange={(e) => setForm({ ...form, end_time: e.target.value })} /></Field>
        </div>
        <Field label="Class" required>
          <Select value={form.class_id} onChange={(e) => setForm({ ...form, class_id: e.target.value, section_id: "" })}>
            <option value="">Select class…</option>
            {classes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </Select>
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Section"><Select value={form.section_id} onChange={(e) => setForm({ ...form, section_id: e.target.value })} disabled={!form.class_id}><option value="">All sections</option>{classSections.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</Select></Field>
          <Field label="Subject" required><Select value={form.subject_id} onChange={(e) => setForm({ ...form, subject_id: e.target.value })}><option value="">Select subject…</option>{classSubjects.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</Select></Field>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Teacher" required><Select value={form.teacher_id} onChange={(e) => setForm({ ...form, teacher_id: e.target.value })}><option value="">Select teacher…</option>{teachers.map((t) => <option key={t.id} value={t.id}>{t.full_name}</option>)}</Select></Field>
          <Field label="Classroom"><Select value={form.classroom_id} onChange={(e) => setForm({ ...form, classroom_id: e.target.value })}><option value="">—</option>{classrooms.map((c) => <option key={c.id} value={c.id}>{c.room_number}</option>)}</Select></Field>
        </div>
        {error && <p className="text-sm text-rose">{error}</p>}
      </div>
    </Modal>
  );
}
