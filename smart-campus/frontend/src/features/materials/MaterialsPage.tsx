import { useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { BookOpen, Upload, Download } from "lucide-react";
import { PageHeader, Card, CardHeader, Badge, EmptyState, ErrorState, Modal } from "@/components/common";
import { Field, TextInput, Textarea, Select } from "@/components/forms";
import { http, API_BASE } from "@/lib/api";
import { useToast } from "@/hooks/useToast";
import { useAuth } from "@/hooks/useAuth";
import { usePrograms, useClasses, useSections, useSubjects } from "@/features/academicQueries";
import type { StudyMaterial } from "@/types";
import { formatDateTime, humanSize } from "@/lib/utils";

export function MaterialsPage() {
  const { profile } = useAuth();
  const role = profile?.user.role;
  const canUpload = role === "admin" || role === "teacher";
  const toast = useToast();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const [form, setForm] = useState({ title: "", description: "", program_id: "", class_id: "", section_id: "", subject_id: "" });

  const { data, isLoading, isError, refetch } = useQuery({ queryKey: ["materials"], queryFn: () => http.get<StudyMaterial[]>("/materials") });
  const programs = usePrograms();
  const classes = useClasses(form.program_id);
  const sections = useSections(form.class_id);
  const subjects = useSubjects(form.program_id);

  const uploadMutation = useMutation({
    mutationFn: () => {
      const file = fileRef.current?.files?.[0];
      if (!file) throw new Error("Choose a file");
      const fd = new FormData();
      fd.append("title", form.title); fd.append("description", form.description);
      fd.append("subject_id", form.subject_id); fd.append("class_id", form.class_id);
      if (form.section_id) fd.append("section_id", form.section_id);
      fd.append("file", file);
      return http.post<StudyMaterial>("/materials", fd);
    },
    onSuccess: () => { toast.success("Material uploaded"); setOpen(false); setForm({ title: "", description: "", program_id: "", class_id: "", section_id: "", subject_id: "" }); qc.invalidateQueries({ queryKey: ["materials"] }); },
    onError: (e: unknown) => toast.error("Upload failed", (e as Error).message),
  });

  return (
    <div>
      <PageHeader title="Study Materials" description={canUpload ? "Upload and manage educational resources for your classes." : "Download materials shared for your class."}
        action={canUpload ? <button onClick={() => setOpen(true)} className="btn-primary"><Upload size={16} /> Upload</button> : undefined} />

      {isError ? <ErrorState message="Could not load materials." onRetry={() => refetch()} /> : (data?.length ?? 0) === 0 ? <Card><EmptyState icon={BookOpen} title="No materials available" /></Card> : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {data?.map((m) => (
            <Card key={m.id} className="p-5">
              <div className="flex items-start gap-3">
                <div className="h-10 w-10 rounded-lg bg-indigo/10 text-indigo grid place-items-center"><BookOpen size={18} /></div>
                <div className="min-w-0 flex-1">
                  <p className="font-semibold text-ink truncate">{m.title}</p>
                  <p className="text-xs text-slate-muted mt-0.5">{m.file_name} · {humanSize(m.file_size)}</p>
                </div>
              </div>
              {m.description && <p className="text-sm text-slate-muted mt-3 line-clamp-2">{m.description}</p>}
              <div className="flex items-center justify-between mt-4">
                <Badge>{m.content_type.split("/")[1]?.toUpperCase() ?? "FILE"}</Badge>
                <button onClick={() => window.open(`${API_BASE}/materials/${m.id}/download`, "_blank")} className="btn-secondary !py-1.5"><Download size={14} /> Download</button>
              </div>
              <p className="text-[11px] text-slate-muted mt-3">Uploaded {formatDateTime(m.created_at)}</p>
            </Card>
          ))}
        </div>
      )}

      <Modal open={open} onClose={() => setOpen(false)} title="Upload study material"
        footer={<><button onClick={() => setOpen(false)} className="btn-secondary">Cancel</button><button onClick={() => uploadMutation.mutate()} disabled={uploadMutation.isPending} className="btn-primary">{uploadMutation.isPending ? "Uploading…" : "Upload"}</button></>}>
        <div className="space-y-3">
          <Field label="Title" required><TextInput value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></Field>
          <Field label="Description"><Textarea rows={2} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></Field>
          <Field label="Program" required><Select value={form.program_id} onChange={(e) => setForm({ ...form, program_id: e.target.value, class_id: "", subject_id: "" })}><option value="">Select…</option>{programs.data?.map((p) => <option key={p.id} value={p.id}>{p.code}</option>)}</Select></Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Class" required><Select value={form.class_id} onChange={(e) => setForm({ ...form, class_id: e.target.value })} disabled={!form.program_id}><option value="">Select…</option>{classes.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</Select></Field>
            <Field label="Section"><Select value={form.section_id} onChange={(e) => setForm({ ...form, section_id: e.target.value })} disabled={!form.class_id}><option value="">All</option>{sections.data?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</Select></Field>
          </div>
          <Field label="Subject" required><Select value={form.subject_id} onChange={(e) => setForm({ ...form, subject_id: e.target.value })} disabled={!form.program_id}><option value="">Select…</option>{subjects.data?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</Select></Field>
          <Field label="File" required hint="PDF, DOCX, PPTX or images up to 25 MB"><input ref={fileRef} type="file" className="input" /></Field>
        </div>
      </Modal>
    </div>
  );
}
