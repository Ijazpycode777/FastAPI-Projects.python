import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { PageHeader, Card, CardHeader, Badge, ErrorState, Skeleton, EmptyState } from "@/components/common";
import { Field, TextInput, Select } from "@/components/forms";
import { http, ApiError } from "@/lib/api";
import { useToast } from "@/hooks/useToast";
import { useShifts } from "./queries";
import { formatTime } from "@/lib/utils";
import { Sunrise } from "lucide-react";

export function ShiftsPage() {
  const queryClient = useQueryClient();
  const toast = useToast();
  const { data: shifts, isLoading, isError, refetch } = useShifts();
  const [form, setForm] = useState({ name: "", code: "", start_time: "", end_time: "", is_active: true });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const create = async () => {
    setError(null);
    if (!form.name.trim() || !form.code.trim()) { setError("Name and code are required."); return; }
    setSubmitting(true);
    try {
      await http.post("/campus/shifts", {
        name: form.name.trim(), code: form.code.trim().toUpperCase(),
        start_time: form.start_time || null, end_time: form.end_time || null,
        is_active: form.is_active,
      });
      toast.success("Shift created", form.name);
      setForm({ name: "", code: "", start_time: "", end_time: "", is_active: true });
      queryClient.invalidateQueries({ queryKey: ["campus", "shifts"] });
    } catch (e) {
      setError((e as ApiError).message);
    } finally { setSubmitting(false); }
  };

  const toggle = async (id: string, active: boolean) => {
    try {
      await http.patch(`/campus/shifts/${id}`, { is_active: !active });
      queryClient.invalidateQueries({ queryKey: ["campus", "shifts"] });
    } catch (e) { toast.error("Could not update shift", (e as ApiError).message); }
  };

  return (
    <div>
      <PageHeader title="Campus Shifts" description="Manage morning / evening shifts. Roll numbers are unique within a shift." />
      <div className="grid lg:grid-cols-3 gap-4">
        <Card>
          <CardHeader title="Add shift" />
          <div className="p-5 space-y-4">
            <Field label="Name" required><TextInput value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Morning" /></Field>
            <Field label="Code" required hint="Short, unique (e.g. MORNING, EVE)"><TextInput value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} placeholder="MORNING" /></Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Start time"><TextInput type="time" value={form.start_time} onChange={(e) => setForm({ ...form, start_time: e.target.value })} /></Field>
              <Field label="End time"><TextInput type="time" value={form.end_time} onChange={(e) => setForm({ ...form, end_time: e.target.value })} /></Field>
            </div>
            <label className="flex items-center gap-2 text-sm text-ink">
              <input type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} /> Active
            </label>
            {error && <p className="text-sm text-rose">{error}</p>}
            <button className="btn-primary w-full" disabled={submitting} onClick={create}>{submitting ? "Creating…" : "Create shift"}</button>
          </div>
        </Card>

        <Card className="lg:col-span-2 overflow-hidden">
          <CardHeader title="Shifts" />
          {isError ? <ErrorState message="Failed to load shifts." onRetry={() => refetch()} />
            : isLoading ? <div className="p-5"><Skeleton className="h-20" /></div>
            : shifts && shifts.length ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead><tr className="border-b border-slate-border bg-slate-bg/60">
                    <th className="px-4 py-2 text-left font-semibold text-ink">Name</th>
                    <th className="px-4 py-2 text-left font-semibold text-ink">Code</th>
                    <th className="px-4 py-2 text-left font-semibold text-ink">Hours</th>
                    <th className="px-4 py-2 text-left font-semibold text-ink">Status</th>
                    <th className="px-4 py-2"></th>
                  </tr></thead>
                  <tbody>
                    {shifts.map((s) => (
                      <tr key={s.id} className="border-b border-slate-border last:border-0">
                        <td className="px-4 py-3 font-medium text-ink">{s.name}</td>
                        <td className="px-4 py-3 text-slate-muted">{s.code}</td>
                        <td className="px-4 py-3 text-slate-muted">{formatTime(s.start_time)} – {formatTime(s.end_time)}</td>
                        <td className="px-4 py-3"><Badge status={s.is_active ? "active" : "inactive"}>{s.is_active ? "Active" : "Inactive"}</Badge></td>
                        <td className="px-4 py-3 text-right">
                          <button className="btn-ghost !px-2 !py-1 text-xs" onClick={() => toggle(s.id, s.is_active)}>{s.is_active ? "Deactivate" : "Activate"}</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : <EmptyState icon={Sunrise} title="No campus shifts yet" description="Create a Morning or Evening shift to get started." />}
        </Card>
      </div>
    </div>
  );
}
