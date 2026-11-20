/** Leave management: admin submission modal + history list (students & teachers). */
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CalendarOff } from "lucide-react";
import { Modal, Card, CardHeader, EmptyState, Skeleton, Badge } from "@/components/common";
import { Field, TextInput, Textarea } from "@/components/forms";
import { http, ApiError } from "@/lib/api";
import { useToast } from "@/hooks/useToast";
import { formatDateDMY } from "@/lib/utils";
import type { Leave } from "@/types";

interface ModalProps {
  personType: "student" | "teacher";
  personId: string;
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
}

export function LeaveFormModal({ personType, personId, open, onClose, onSaved }: ModalProps) {
  const toast = useToast();
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reset = () => { setStart(""); setEnd(""); setReason(""); setError(null); };

  const submit = async () => {
    setError(null);
    if (!start || !end) { setError("Both dates are required."); return; }
    if (end < start) { setError("End date cannot be earlier than start date."); return; }
    if (reason.trim().length < 3) { setError("Reason must be at least 3 characters."); return; }
    setSubmitting(true);
    try {
      await http.post("/leave", {
        person_type: personType,
        ...(personType === "student" ? { student_id: personId } : { teacher_id: personId }),
        start_date: start, end_date: end, reason: reason.trim(),
      });
      toast.success("Leave submitted", `${formatDateDMY(start)} to ${formatDateDMY(end)}`);
      reset(); onClose(); onSaved();
    } catch (e) {
      setError((e as ApiError).message);
    } finally { setSubmitting(false); }
  };

  return (
    <Modal open={open} onClose={() => { reset(); onClose(); }} title="Submit leave"
      footer={<>
        <button className="btn-secondary" onClick={() => { reset(); onClose(); }}>Cancel</button>
        <button className="btn-primary" disabled={submitting} onClick={submit}>
          {submitting ? "Saving…" : "Submit leave"}
        </button>
      </>}>
      <div className="space-y-4">
        <p className="text-xs text-slate-muted">The date range is inclusive. Dates display as DD-MM-YYYY.</p>
        <div className="grid grid-cols-2 gap-3">
          <Field label="From date" required><TextInput type="date" value={start} onChange={(e) => setStart(e.target.value)} /></Field>
          <Field label="To date" required><TextInput type="date" value={end} onChange={(e) => setEnd(e.target.value)} /></Field>
        </div>
        <Field label="Reason / description" required>
          <Textarea rows={3} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Medical leave" />
        </Field>
        {error && <p className="text-sm text-rose">{error}</p>}
      </div>
    </Modal>
  );
}

export function LeaveHistory({ personType, personId }: { personType: "student" | "teacher"; personId: string }) {
  const { data, isLoading, refetch } = useQuery({
    queryKey: ["leave", personType, personId],
    queryFn: () => http.get<Leave[]>(`/leave/${personType}/${personId}`),
  });
  return (
    <Card>
      <CardHeader title="Leave history" />
      {isLoading ? <div className="p-5"><Skeleton className="h-16" /></div>
        : data && data.length ? (
          <ul className="divide-y divide-slate-border">
            {data.map((l) => (
              <li key={l.id} className="px-5 py-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-ink">{formatDateDMY(l.start_date)} to {formatDateDMY(l.end_date)}</span>
                  <Badge status={l.status === "approved" ? "active" : "inactive"}>{l.status}</Badge>
                </div>
                <p className="text-xs text-slate-muted mt-1">{l.reason}</p>
              </li>
            ))}
          </ul>
        ) : <EmptyState icon={CalendarOff} title="No leave records" description="Submitted leave will appear here." action={<button className="btn-secondary" onClick={() => refetch()}>Refresh</button>} />}
    </Card>
  );
}
