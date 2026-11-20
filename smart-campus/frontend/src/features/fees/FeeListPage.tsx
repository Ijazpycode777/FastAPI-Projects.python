import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Wallet, Search } from "lucide-react";
import { PageHeader, Badge, EmptyState, ErrorState } from "@/components/common";
import { DataTable, type Column } from "@/components/tables/DataTable";
import { http } from "@/lib/api";
import { useDebounce } from "@/hooks/useDebounce";
import type { FeeInvoice, Page } from "@/types";
import { formatCurrency, formatDate } from "@/lib/utils";

export function FeeListPage() {
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const debounced = useDebounce(q, 300);
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["invoices", debounced],
    queryFn: () => http.get<Page<FeeInvoice>>("/fees/invoices", { status: debounced || undefined, page: 1, page_size: 50 }),
  });

  const columns: Column<FeeInvoice>[] = [
    { key: "invoice_number", header: "Invoice", render: (i) => <span className="font-medium text-ink">{i.invoice_number}</span> },
    { key: "student_id", header: "Student", render: (i) => <span className="text-slate-muted">{i.student_id.slice(0, 8)}</span> },
    { key: "amount", header: "Amount", render: (i) => formatCurrency(i.amount) },
    { key: "issued_date", header: "Issued", render: (i) => formatDate(i.issued_date) },
    { key: "due_date", header: "Due", render: (i) => formatDate(i.due_date) },
    { key: "status", header: "Status", render: (i) => <Badge status={i.status}>{i.status}</Badge> },
  ];

  return (
    <div>
      <PageHeader title="Fees" description="Generate invoices, record payments and track outstanding balances." />
      <div className="card p-4 mb-4">
        <div className="relative max-w-xs">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-muted" />
          <select className="input pl-9" value={q} onChange={(e) => setQ(e.target.value)}>
            <option value="">All statuses</option>
            <option value="unpaid">Unpaid</option>
            <option value="partial">Partial</option>
            <option value="paid">Paid</option>
            <option value="overdue">Overdue</option>
          </select>
        </div>
      </div>
      {isError ? <ErrorState message="Could not load invoices." onRetry={() => refetch()} /> : (
        <DataTable columns={columns} rows={data?.items ?? []} rowKey={(i) => i.id} loading={isLoading}
          onRowClick={(i) => navigate(`/fees/${i.id}`)}
          emptyState={<EmptyState icon={Wallet} title="No invoices found" />} />
      )}
    </div>
  );
}
