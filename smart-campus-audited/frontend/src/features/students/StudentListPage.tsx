import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, Search, Users } from "lucide-react";
import { PageHeader, Badge, Pagination, EmptyState } from "@/components/common";
import { DataTable, type Column } from "@/components/tables/DataTable";
import { useDebounce } from "@/hooks/useDebounce";
import { useStudents } from "./queries";
import type { Student } from "@/types";
import { formatDate } from "@/lib/utils";

export function StudentListPage() {
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const debounced = useDebounce(q, 300);
  const { data, isLoading } = useStudents({ q: debounced || undefined, page, page_size: 20 });

  const columns: Column<Student>[] = [
    { key: "admission_number", header: "Admission No.", sortable: true, render: (s) => <span className="font-medium text-navy">{s.admission_number}</span> },
    { key: "full_name", header: "Name", render: (s) => <span className="font-medium text-navy">{s.full_name}</span> },
    { key: "email", header: "Email" },
    { key: "admission_date", header: "Admitted", render: (s) => formatDate(s.admission_date) },
    { key: "account_status", header: "Status", render: (s) => <Badge status={s.account_status}>{s.account_status}</Badge> },
  ];

  return (
    <div>
      <PageHeader
        title="Students"
        description="Manage student enrolment, profiles and status."
        action={<button onClick={() => navigate("/students/new")} className="btn-primary"><Plus size={16} /> Add Student</button>}
      />

      <div className="card p-4 mb-4">
        <div className="relative max-w-sm">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-muted" />
          <input className="input pl-9" placeholder="Search by name, admission no. or email…" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} />
        </div>
      </div>

      <DataTable
        columns={columns}
        rows={data?.items ?? []}
        rowKey={(s) => s.id}
        loading={isLoading}
        onRowClick={(s) => navigate(`/students/${s.id}`)}
        emptyState={<EmptyState icon={Users} title="No students found" description="Try adjusting your search or add a new student." />}
      />

      <Pagination page={page} totalPages={data?.pagination.total_pages ?? 1} onPage={setPage} />
    </div>
  );
}
