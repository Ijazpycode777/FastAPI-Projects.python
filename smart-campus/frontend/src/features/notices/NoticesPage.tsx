import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Megaphone, Plus, Pin, Trash2 } from "lucide-react";
import { PageHeader, Card, Badge, EmptyState, ErrorState, Modal } from "@/components/common";
import { Field, TextInput, Textarea, Select } from "@/components/forms";
import { http, ApiError } from "@/lib/api";
import { useToast } from "@/hooks/useToast";
import { useAuth } from "@/hooks/useAuth";
import type { Notice } from "@/types";
import { formatDateTime } from "@/lib/utils";

export function NoticesPage() {
  const { profile } = useAuth();
  const role = profile?.user.role;
  const canPublish = role === "admin" || role === "teacher";
  const toast = useToast();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ title: "", content: "", target_audience: "all" });

  const { data, isLoading, isError, refetch } = useQuery({ queryKey: ["notices"], queryFn: () => http.get<Notice[]>("/notices") });

  const publishMutation = useMutation({
    mutationFn: () => http.post<Notice>("/notices", { title: form.title, content: form.content, target_audience: form.target_audience }),
    onSuccess: () => { toast.success("Notice published"); setOpen(false); setForm({ title: "", content: "", target_audience: "all" }); qc.invalidateQueries({ queryKey: ["notices"] }); },
    onError: (e: unknown) => toast.error("Could not publish", (e as ApiError).message),
  });

  const remove = async (id: string) => {
    try { await http.del(`/notices/${id}`); toast.success("Notice deleted"); qc.invalidateQueries({ queryKey: ["notices"] }); }
    catch (e) { toast.error("Could not delete", (e as ApiError).message); }
  };

  return (
    <div>
      <PageHeader title="Notices" description="College announcements targeted to your role."
        action={canPublish ? <button onClick={() => setOpen(true)} className="btn-primary"><Plus size={16} /> New Notice</button> : undefined} />

      {isError ? <ErrorState message="Could not load notices." onRetry={() => refetch()} /> : (data?.length ?? 0) === 0 ? <Card><EmptyState icon={Megaphone} title="No notices yet" /></Card> : (
        <div className="space-y-3">
          {data?.map((n) => (
            <Card key={n.id} className="p-5">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-start gap-3 min-w-0">
                  {n.is_pinned && <Pin size={16} className="text-amber mt-1 shrink-0" />}
                  <div className="min-w-0">
                    <p className="font-semibold text-navy">{n.title}</p>
                    <p className="text-xs text-slate-muted mt-0.5">{formatDateTime(n.published_at)} · <span className="capitalize">{n.target_audience}</span></p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge>{n.target_audience}</Badge>
                  {canPublish && <button onClick={() => remove(n.id)} className="text-slate-muted hover:text-rose"><Trash2 size={15} /></button>}
                </div>
              </div>
              <p className="text-sm text-slate-muted mt-3 whitespace-pre-wrap">{n.content}</p>
            </Card>
          ))}
        </div>
      )}

      <Modal open={open} onClose={() => setOpen(false)} title="Publish notice"
        footer={<><button onClick={() => setOpen(false)} className="btn-secondary">Cancel</button><button onClick={() => publishMutation.mutate()} disabled={publishMutation.isPending || !form.title || !form.content} className="btn-primary">{publishMutation.isPending ? "Publishing…" : "Publish"}</button></>}>
        <div className="space-y-3">
          <Field label="Title" required><TextInput value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></Field>
          <Field label="Content" required><Textarea rows={5} value={form.content} onChange={(e) => setForm({ ...form, content: e.target.value })} /></Field>
          <Field label="Audience" required>
            <Select value={form.target_audience} onChange={(e) => setForm({ ...form, target_audience: e.target.value })}>
              <option value="all">Everyone</option>
              {role === "admin" && <><option value="admins">Admins</option><option value="teachers">Teachers</option><option value="students">Students</option><option value="program">Program</option><option value="class">Class</option><option value="section">Section</option></>}
              {role === "teacher" && <><option value="class">My class</option><option value="section">My section</option></>}
            </Select>
          </Field>
        </div>
      </Modal>
    </div>
  );
}
