import { useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Wallet, Plus, Download } from "lucide-react";
import { useState } from "react";
import { PageHeader, Card, CardHeader, Badge, ErrorState, Skeleton, EmptyState } from "@/components/common";
import { Field, Select, TextInput } from "@/components/forms";
import { http, API_BASE } from "@/lib/api";
import { useToast } from "@/hooks/useToast";
import { useAuth } from "@/hooks/useAuth";
import type { InvoiceDetail, Payment } from "@/types";
import { formatCurrency, formatDate } from "@/lib/utils";

export function InvoiceDetailPage() {
  const { id } = useParams();
  const { profile } = useAuth();
  const role = profile?.user.role;
  // For students, use the "me" statement endpoint instead of a specific invoice.
  const invoiceId = role === "student" ? undefined : id;
  const toast = useToast();
  const qc = useQueryClient();
  const [payment, setPayment] = useState({ amount: "", method: "cash", paid_at: new Date().toISOString().slice(0, 10), reference: "" });

  const statement = useQuery({
    queryKey: ["my-statement"],
    queryFn: () => http.get<{ total_outstanding: number; total_paid: number; total_invoiced: number; items: { invoice: InvoiceDetail }[] }>("/fees/statement/me"),
    enabled: role === "student",
  });
  const invoice = useQuery({
    queryKey: ["invoice", invoiceId],
    queryFn: () => http.get<InvoiceDetail>(`/fees/invoices/${invoiceId}`),
    enabled: !!invoiceId,
  });

  const payMutation = useMutation({
    mutationFn: () => http.post<Payment>("/fees/payments", { invoice_id: invoiceId, amount: Number(payment.amount), method: payment.method, paid_at: payment.paid_at, reference: payment.reference || null }),
    onSuccess: () => { toast.success("Payment recorded"); setPayment({ ...payment, amount: "", reference: "" }); qc.invalidateQueries({ queryKey: ["invoice", invoiceId] }); },
    onError: (e: unknown) => toast.error("Could not record payment", (e as Error).message),
  });

  if (role === "student") {
    if (statement.isLoading) return <Skeleton className="h-64" />;
    if (statement.isError || !statement.data) return <ErrorState message="Could not load your fee statement." />;
    const s = statement.data;
    return (
      <div>
        <PageHeader title="My Fees" description="Your fee statement and payment history." />
        <div className="grid grid-cols-3 gap-4 mb-4">
          <Card className="p-5"><p className="text-xs text-slate-muted">Invoiced</p><p className="text-2xl font-bold text-ink mt-1">{formatCurrency(s.total_invoiced)}</p></Card>
          <Card className="p-5"><p className="text-xs text-slate-muted">Paid</p><p className="text-2xl font-bold text-teal mt-1">{formatCurrency(s.total_paid)}</p></Card>
          <Card className="p-5"><p className="text-xs text-slate-muted">Outstanding</p><p className="text-2xl font-bold text-rose mt-1">{formatCurrency(s.total_outstanding)}</p></Card>
        </div>
        <Card>
          <CardHeader title="Invoices" />
          <div className="divide-y divide-slate-border">
            {s.items.map(({ invoice: inv }) => (
              <div key={inv.id} className="px-5 py-3 flex items-center justify-between">
                <div><p className="text-sm font-medium text-ink">{inv.invoice_number}</p><p className="text-xs text-slate-muted">Due {formatDate(inv.due_date)}</p></div>
                <div className="flex items-center gap-3">
                  <span className="text-sm font-semibold text-ink">{formatCurrency(inv.amount)}</span>
                  <Badge status={inv.status}>{inv.status}</Badge>
                </div>
              </div>
            ))}
            {s.items.length === 0 && <EmptyState icon={Wallet} title="No invoices" />}
          </div>
        </Card>
      </div>
    );
  }

  if (invoice.isLoading) return <Skeleton className="h-64" />;
  if (invoice.isError || !invoice.data) return <ErrorState message="Invoice not found." />;
  const inv = invoice.data;

  return (
    <div>
      <PageHeader title={inv.invoice_number} description={`Issued ${formatDate(inv.issued_date)} · due ${formatDate(inv.due_date)}`}
        action={<a href={`${API_BASE}/reports/payments?`} className="btn-secondary" onClick={(e) => { e.preventDefault(); window.open(`${API_BASE}/reports/fees/${inv.student_id}.pdf`, "_blank"); }}><Download size={16} /> PDF</a>} />
      <div className="grid lg:grid-cols-3 gap-4">
        <Card className="lg:col-span-2">
          <CardHeader title="Invoice" action={<Badge status={inv.status}>{inv.status}</Badge>} />
          <div className="p-5 grid grid-cols-3 gap-4 text-center">
            <div><p className="text-xs text-slate-muted">Amount</p><p className="text-xl font-bold text-ink mt-1">{formatCurrency(inv.amount)}</p></div>
            <div><p className="text-xs text-slate-muted">Paid</p><p className="text-xl font-bold text-teal mt-1">{formatCurrency(inv.paid_amount)}</p></div>
            <div><p className="text-xs text-slate-muted">Outstanding</p><p className="text-xl font-bold text-rose mt-1">{formatCurrency(inv.outstanding)}</p></div>
          </div>
          <div className="px-5 pb-5">
            <div className="h-2 w-full rounded-full bg-slate-bg overflow-hidden">
              <div className="h-full bg-teal rounded-full" style={{ width: `${inv.amount ? (inv.paid_amount / inv.amount) * 100 : 0}%` }} />
            </div>
          </div>
        </Card>
        <Card>
          <CardHeader title="Record payment" />
          <div className="p-5 space-y-3">
            <Field label="Amount"><TextInput type="number" value={payment.amount} onChange={(e) => setPayment({ ...payment, amount: e.target.value })} placeholder="0.00" /></Field>
            <Field label="Method"><Select value={payment.method} onChange={(e) => setPayment({ ...payment, method: e.target.value })}><option value="cash">Cash</option><option value="cheque">Cheque</option><option value="bank_transfer">Bank transfer</option><option value="card">Card</option><option value="online">Online</option></Select></Field>
            <Field label="Date"><TextInput type="date" value={payment.paid_at} onChange={(e) => setPayment({ ...payment, paid_at: e.target.value })} /></Field>
            <Field label="Reference"><TextInput value={payment.reference} onChange={(e) => setPayment({ ...payment, reference: e.target.value })} /></Field>
            <button disabled={!payment.amount || inv.outstanding <= 0} onClick={() => payMutation.mutate()} className="btn-primary w-full"><Plus size={16} /> Record Payment</button>
          </div>
        </Card>
      </div>

      <Card className="mt-4">
        <CardHeader title="Payment history" />
        {inv.payments.length ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-slate-border bg-slate-bg/60"><th className="px-4 py-2.5 text-left font-semibold text-ink">Receipt</th><th className="px-4 py-2.5 text-left font-semibold text-ink">Date</th><th className="px-4 py-2.5 text-left font-semibold text-ink">Method</th><th className="px-4 py-2.5 text-left font-semibold text-ink">Reference</th><th className="px-4 py-2.5 text-left font-semibold text-ink">Amount</th></tr></thead>
              <tbody>{inv.payments.map((p) => (<tr key={p.id} className="border-b border-slate-border last:border-0"><td className="px-4 py-2.5 font-medium text-ink">{p.receipt_number}</td><td className="px-4 py-2.5">{formatDate(p.paid_at)}</td><td className="px-4 py-2.5 capitalize">{p.method}</td><td className="px-4 py-2.5">{p.reference || "—"}</td><td className="px-4 py-2.5 font-semibold text-teal">{formatCurrency(p.amount)}</td></tr>))}</tbody>
            </table>
          </div>
        ) : <EmptyState icon={Wallet} title="No payments yet" />}
      </Card>
    </div>
  );
}
