import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { PageHeader, Card, CardHeader, Badge, ErrorState, Skeleton, EmptyState } from "@/components/common";
import { Field, TextInput, Select } from "@/components/forms";
import { http, ApiError } from "@/lib/api";
import { useToast } from "@/hooks/useToast";
import { useShifts, useRollSchemes } from "./queries";
import type { ClassLevel, Section } from "@/types";
import { Hash } from "lucide-react";

export function RollSchemesPage() {
  const queryClient = useQueryClient();
  const toast = useToast();
  const { data: shifts } = useShifts();
  const { data: schemes, isLoading, isError, refetch } = useRollSchemes();
  const classes = useQuery({ queryKey: ["classes"], queryFn: () => http.get<ClassLevel[]>("/classes") });
  const sections = useQuery({ queryKey: ["sections"], queryFn: () => http.get<Section[]>("/sections") });

  const [form, setForm] = useState({ campus_shift_id: "", class_id: "", section_id: "", prefix: "", min_roll: 1, max_roll: 99, padding: 2 });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const classSections = (sections.data ?? []).filter((s) => s.class_level_id === form.class_id);
  const clsName = (id: string) => (classes.data ?? []).find((c) => c.id === id)?.name ?? "—";
  const secName = (id: string | null) => (id ? (sections.data ?? []).find((s) => s.id === id)?.name ?? "—" : "All sections");
  const shiftName = (id: string) => (shifts ?? []).find((s) => s.id === id)?.name ?? "—";

  const create = async () => {
    setError(null);
    if (!form.campus_shift_id || !form.class_id) { setError("Campus shift and class are required."); return; }
    if (form.max_roll < form.min_roll) { setError("Max roll must be >= min roll."); return; }
    setSubmitting(true);
    try {
      await http.post("/campus/roll-schemes", {
        campus_shift_id: form.campus_shift_id, class_id: form.class_id,
        section_id: form.section_id || null, prefix: form.prefix || null,
        min_roll: Number(form.min_roll), max_roll: Number(form.max_roll), padding: Number(form.padding),
      });
      toast.success("Roll-number scheme created");
      setForm({ ...form, section_id: "", prefix: "" });
      queryClient.invalidateQueries({ queryKey: ["campus", "roll-schemes"] });
    } catch (e) { setError((e as ApiError).message); }
    finally { setSubmitting(false); }
  };

  const remove = async (id: string) => {
    try { await http.del(`/campus/roll-schemes/${id}`); queryClient.invalidateQueries({ queryKey: ["campus", "roll-schemes"] }); }
    catch (e) { toast.error("Could not delete scheme", (e as ApiError).message); }
  };

  return (
    <div>
      <PageHeader title="Roll-Number Schemes" description="Configure per-class roll-number ranges and prefixes. Optional — when absent, only shift-wide uniqueness is enforced." />
      <div className="grid lg:grid-cols-3 gap-4">
        <Card>
          <CardHeader title="Add scheme" />
          <div className="p-5 space-y-4">
            <Field label="Campus shift" required>
              <Select value={form.campus_shift_id} onChange={(e) => setForm({ ...form, campus_shift_id: e.target.value })}>
                <option value="">Select shift…</option>
                {shifts?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </Select>
            </Field>
            <Field label="Class" required>
              <Select value={form.class_id} onChange={(e) => setForm({ ...form, class_id: e.target.value, section_id: "" })}>
                <option value="">Select class…</option>
                {(classes.data ?? []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </Select>
            </Field>
            <Field label="Section" hint="Leave as 'All' to apply class-wide.">
              <Select value={form.section_id} onChange={(e) => setForm({ ...form, section_id: e.target.value })}>
                <option value="">All sections</option>
                {classSections.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </Select>
            </Field>
            <Field label="Prefix" hint="Optional display prefix (e.g. ICS1)"><TextInput value={form.prefix} onChange={(e) => setForm({ ...form, prefix: e.target.value })} /></Field>
            <div className="grid grid-cols-3 gap-3">
              <Field label="Min roll" required><TextInput type="number" min={0} value={form.min_roll} onChange={(e) => setForm({ ...form, min_roll: Number(e.target.value) })} /></Field>
              <Field label="Max roll" required><TextInput type="number" min={1} value={form.max_roll} onChange={(e) => setForm({ ...form, max_roll: Number(e.target.value) })} /></Field>
              <Field label="Padding" hint="Digits"><TextInput type="number" min={1} max={6} value={form.padding} onChange={(e) => setForm({ ...form, padding: Number(e.target.value) })} /></Field>
            </div>
            {error && <p className="text-sm text-rose">{error}</p>}
            <button className="btn-primary w-full" disabled={submitting} onClick={create}>{submitting ? "Creating…" : "Create scheme"}</button>
          </div>
        </Card>

        <Card className="lg:col-span-2 overflow-hidden">
          <CardHeader title="Configured schemes" />
          {isError ? <ErrorState message="Failed to load schemes." onRetry={() => refetch()} />
            : isLoading ? <div className="p-5"><Skeleton className="h-24" /></div>
            : schemes && schemes.length ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead><tr className="border-b border-slate-border bg-slate-bg/60">
                    <th className="px-4 py-2 text-left font-semibold text-ink">Shift</th>
                    <th className="px-4 py-2 text-left font-semibold text-ink">Class</th>
                    <th className="px-4 py-2 text-left font-semibold text-ink">Section</th>
                    <th className="px-4 py-2 text-left font-semibold text-ink">Prefix</th>
                    <th className="px-4 py-2 text-left font-semibold text-ink">Range</th>
                    <th className="px-4 py-2"></th>
                  </tr></thead>
                  <tbody>
                    {schemes.map((s) => (
                      <tr key={s.id} className="border-b border-slate-border last:border-0">
                        <td className="px-4 py-3"><Badge status="active">{shiftName(s.campus_shift_id)}</Badge></td>
                        <td className="px-4 py-3 text-ink">{clsName(s.class_id)}</td>
                        <td className="px-4 py-3 text-slate-muted">{secName(s.section_id ?? null)}</td>
                        <td className="px-4 py-3 text-slate-muted">{s.prefix ?? "—"}</td>
                        <td className="px-4 py-3 text-ink">{s.min_roll}–{s.max_roll}</td>
                        <td className="px-4 py-3 text-right">
                          <button className="btn-ghost !px-2 !py-1 text-xs text-rose" onClick={() => remove(s.id)}>Delete</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : <EmptyState icon={Hash} title="No roll-number schemes" description="Without a scheme, only shift-wide roll uniqueness is enforced." />}
        </Card>
      </div>
    </div>
  );
}
