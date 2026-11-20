import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, Search, GraduationCap } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { PageHeader, Badge, Pagination, EmptyState, ErrorState } from "@/components/common";
import { DataTable, type Column } from "@/components/tables/DataTable";
import { useDebounce } from "@/hooks/useDebounce";
import { http } from "@/lib/api";
import type { Page, Teacher } from "@/types";
import { formatDate } from "@/lib/utils";

export function TeacherListPage() {
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const debounced = useDebounce(q, 300);
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["teachers", { q: debounced, page }],
    queryFn: () => http.get<Page<Teacher>>("/teachers", { q: debounced || undefined, page, page_size: 20 }),
    placeholderData: (prev) => prev,
  });

  const columns: Column<Teacher>[] = [
    { key: "employee_id", header: "Employee ID", render: (t) => <span className="font-medium text-navy">{t.employee_id}</span> },
    { key: "full_name", header: "Name", render: (t) => <span className="font-medium text-navy">{t.full_name}</span> },
    { key: "email", header: "Email" },
    { key: "department", header: "Department", render: (t) => t.department || "—" },
    { key: "designation", header: "Designation" },
    { key: "joining_date", header: "Joined", render: (t) => formatDate(t.joining_date) },
    { key: "employment_status", header: "Status", render: (t) => <Badge status={t.employment_status}>{t.employment_status}</Badge> },
  ];

  return (
    <div>
      <PageHeader title="Teachers" description="Create and manage teaching staff accounts."
        action={<button onClick={() => navigate("/teachers/new")} className="btn-primary"><Plus size={16} /> Add Teacher</button>} />
      <div className="card p-4 mb-4">
        <div className="relative max-w-sm">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-muted" />
          <input className="input pl-9" placeholder="Search by name, email or employee ID…" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} />
        </div>
      </div>
      {isError ? <ErrorState message="Failed to load teachers." onRetry={() => refetch()} /> : (
        <DataTable columns={columns} rows={data?.items ?? []} rowKey={(t) => t.id} loading={isLoading}
          onRowClick={(t) => navigate(`/teachers/${t.id}`)}
          emptyState={<EmptyState icon={GraduationCap} title="No teachers found" description="Add a teacher to get started." />} />
      )}
      <Pagination page={page} totalPages={data?.pagination.total_pages ?? 1} onPage={setPage} />
    </div>
  );
}
