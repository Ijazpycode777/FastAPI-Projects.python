import { useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { BookOpen, Upload, Download, Eye, Trash2 } from "lucide-react";
import { PageHeader, Card, Badge, EmptyState, ErrorState, Modal } from "@/components/common";
import { Field, TextInput, Textarea, Select } from "@/components/forms";
import { http, API_BASE } from "@/lib/api";
import { useToast } from "@/hooks/useToast";
import { useAuth } from "@/hooks/useAuth";
import { usePrograms, useClasses } from "@/features/academicQueries";
import type { StudyMaterial } from "@/types";
import { formatDateTime, humanSize } from "@/lib/utils";

/** Browsers can render PDF and images inline; Office formats cannot, so they
 *  only get a Download button (preview would just download anyway). */
function isPreviewable(contentType: string): boolean {
  return contentType === "application/pdf" || contentType.startsWith("image/");
}

export function MaterialsPage() {
  const { profile } = useAuth();
  const role = profile?.user.role;
  const canUpload = role === "admin" || role === "teacher";
  const toast = useToast();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const [form, setForm] = useState({ title: "", description: "", program_id: "", class_id: "" });

  const { data, isLoading, isError, refetch } = useQuery({ queryKey: ["materials"], queryFn: () => http.get<StudyMaterial[]>("/materials") });
  const programs = usePrograms();
  const classes = useClasses(form.program_id);

  const uploadMutation = useMutation({
    mutationFn: () => {
      const file = fileRef.current?.files?.[0];
      if (!file) throw new Error("Choose a file");
      const fd = new FormData();
      fd.append("title", form.title); fd.append("description", form.description);
      fd.append("class_id", form.class_id);
      fd.append("file", file);
      return http.post<StudyMaterial>("/materials", fd);
    },
    onSuccess: () => { toast.success("Material uploaded"); setOpen(false); setForm({ title: "", description: "", program_id: "", class_id: "" }); qc.invalidateQueries({ queryKey: ["materials"] }); },
    onError: (e: unknown) => toast.error("Upload failed", (e as Error).message),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => http.del(`/materials/${id}`),
    onSuccess: () => { toast.success("Material removed"); qc.invalidateQueries({ queryKey: ["materials"] }); },
    onError: (e: unknown) => toast.error("Could not delete material", (e as Error).message),
  });

  const onDelete = (m: StudyMaterial) => {
    if (!confirm(`Delete "${m.title}"? The stored file is removed and the material is hidden from students.`)) return;
    deleteMutation.mutate(m.id);
  };

  return (
    <div>
      <PageHeader title="Study Materials" description={canUpload ? "Upload and manage educational resources for your classes." : "Download materials shared for your class."}
        action={canUpload ? <button onClick={() => setOpen(true)} className="btn-primary"><Upload size={16} /> Upload</button> : undefined} />

      {isError ? <ErrorState message="Could not load materials." onRetry={() => refetch()} /> : isLoading ? (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="card p-5 h-44 animate-pulse bg-slate-bg/40" />
          ))}
        </div>
      ) : (data?.length ?? 0) === 0 ? <Card><EmptyState icon={BookOpen} title="No materials available" description={canUpload ? "Upload your first study material to share it with your classes." : "Materials shared for your class will appear here."} /></Card> : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {data?.map((m) => {
            const previewable = isPreviewable(m.content_type);
            return (
              <Card key={m.id} className="p-5 flex flex-col">
                {/* Header: icon + title + filename (both truncated so long names
                    never overflow the card). Delete control for staff sits
                    top-right so it is reachable but unobtrusive. */}
                <div className="flex items-start gap-3">
                  <div className="h-10 w-10 rounded-lg bg-indigo/10 text-indigo grid place-items-center shrink-0">
                    <BookOpen size={18} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="font-semibold text-ink truncate" title={m.title}>{m.title}</p>
                    <p className="text-xs text-slate-muted mt-0.5 truncate" title={m.file_name}>{m.file_name}</p>
                  </div>
                  {canUpload && (
                    <button onClick={() => onDelete(m)} disabled={deleteMutation.isPending}
                      className="btn-ghost !px-1.5 !py-1.5 text-slate-muted hover:text-rose shrink-0"
                      title="Delete material" aria-label="Delete material">
                      <Trash2 size={15} />
                    </button>
                  )}
                </div>

                {m.description && <p className="text-sm text-slate-muted mt-3 line-clamp-2">{m.description}</p>}

                {/* Meta: file type + size, wrapped (never overflows). */}
                <div className="flex items-center gap-2 mt-4 flex-wrap">
                  <Badge>{m.content_type.split("/")[1]?.toUpperCase() ?? "FILE"}</Badge>
                  <span className="text-xs text-slate-muted">{humanSize(m.file_size)}</span>
                </div>

                {/* Actions pinned to the card bottom: Preview (inline, for
                    PDF/images) + Download (attachment). Both full-width split so
                    they stay within the card on every screen size. */}
                <div className="flex items-center gap-2 mt-auto pt-3">
                  {previewable && (
                    <button type="button"
                      onClick={() => window.open(`${API_BASE}/materials/${m.id}/preview`, "_blank")}
                      className="btn-secondary flex-1 inline-flex items-center justify-center gap-1.5">
                      <Eye size={15} /> Preview
                    </button>
                  )}
                  <a href={`${API_BASE}/materials/${m.id}/download`}
                    className="btn-primary flex-1 inline-flex items-center justify-center gap-1.5 no-underline"
                    download>
                    <Download size={15} /> Download
                  </a>
                </div>

                <p className="text-[11px] text-slate-muted mt-3">Uploaded {formatDateTime(m.created_at)}</p>
              </Card>
            );
          })}
        </div>
      )}

      <Modal open={open} onClose={() => setOpen(false)} title="Upload study material"
        footer={<><button onClick={() => setOpen(false)} className="btn-secondary">Cancel</button><button onClick={() => uploadMutation.mutate()} disabled={uploadMutation.isPending} className="btn-primary">{uploadMutation.isPending ? "Uploading…" : "Upload"}</button></>}>
        <div className="space-y-3">
          <Field label="Title" required><TextInput value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></Field>
          <Field label="Description"><Textarea rows={2} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></Field>
          <Field label="Program" required><Select value={form.program_id} onChange={(e) => setForm({ ...form, program_id: e.target.value, class_id: "" })}><option value="">Select…</option>{programs.data?.map((p) => <option key={p.id} value={p.id}>{p.code}</option>)}</Select></Field>
          <Field label="Class" required hint="e.g. Part 1 or Part 2"><Select value={form.class_id} onChange={(e) => setForm({ ...form, class_id: e.target.value })} disabled={!form.program_id}><option value="">Select…</option>{classes.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</Select></Field>
          <Field label="File" required hint="PDF, DOCX, PPTX or images up to 25 MB"><input ref={fileRef} type="file" className="input" /></Field>
        </div>
      </Modal>
    </div>
  );
}
