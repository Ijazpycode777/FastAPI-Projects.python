import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Plus, Search, GraduationCap, FilterX } from "lucide-react";
import { PageHeader, Badge, Pagination, EmptyState, ErrorState } from "@/components/common";
import { DataTable, type Column } from "@/components/tables/DataTable";
import { Select } from "@/components/forms";
import { useDebounce } from "@/hooks/useDebounce";
import { http } from "@/lib/api";
import type { Page, Teacher, Subject } from "@/types";
import { formatDate } from "@/lib/utils";

const STATUS_OPTS = ["active", "inactive", "on_leave"];

export function TeacherListPage() {
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [status, setStatus] = useState("");
  const [sortKey, setSortKey] = useState("created_at");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [page, setPage] = useState(1);
  const debounced = useDebounce(q, 300);

  const subjects = useQuery({ queryKey: ["subjects"], queryFn: () => http.get<Subject[]>("/subjects") });

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["teachers", { q: debounced, subject_id: subjectId, status, sort: sortKey, order: sortDir, page }],
    queryFn: () => http.get<Page<Teacher>>("/teachers", {
      q: debounced || undefined,
      subject_id: subjectId || undefined, status: status || undefined,
      sort: sortKey, order: sortDir, page, page_size: 20,
    }),
    placeholderData: (prev) => prev,
  });

  const hasFilters = !!(subjectId || status || q);
  const clearFilters = () => { setQ(""); setSubjectId(""); setStatus(""); setPage(1); };

  const onSort = (key: string) => {
    const backendKey = key === "full_name" ? "full_name" : "created_at";
    if (sortKey === backendKey) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else { setSortKey(backendKey); setSortDir("asc"); }
  };

  const columns: Column<Teacher>[] = [
    { key: "employee_id", header: "Employee ID", render: (t) => <span className="font-medium text-ink">{t.employee_id}</span> },
    { key: "full_name", header: "Name", sortable: true, render: (t) => (
      <div className="min-w-0">
        <p className="font-medium text-ink truncate">{t.full_name}</p>
        <p className="text-[11px] text-slate-muted truncate">{t.email}</p>
      </div>
    ) },
    { key: "department", header: "Department", render: (t) => <span className="text-slate-muted">{t.department || "—"}</span> },
    { key: "joining_date", header: "Joined", render: (t) => formatDate(t.joining_date) },
    { key: "employment_status", header: "Status", render: (t) => <Badge status={t.employment_status}>{t.employment_status}</Badge> },
  ];

  return (
    <div>
      <PageHeader
        title="Teacher Logs"
        description="Search and inspect teachers by name, employee ID, subject and status."
        action={<button onClick={() => navigate("/teachers/new")} className="btn-primary"><Plus size={16} /> Add Teacher</button>}
      />

      <div className="card p-4 mb-4 space-y-3">
        <div className="relative max-w-md">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-muted" />
          <input className="input pl-9" placeholder="Search by name, email or employee ID…" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} />
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          <Select value={subjectId} onChange={(e) => { setSubjectId(e.target.value); setPage(1); }}>
            <option value="">All subjects</option>
            {subjects.data?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </Select>
          <Select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
            <option value="">Any status</option>
            {STATUS_OPTS.map((s) => <option key={s} value={s}>{s}</option>)}
          </Select>
        </div>
        {hasFilters && (
          <button onClick={clearFilters} className="btn-ghost !py-1 !px-2 text-xs self-start"><FilterX size={14} /> Clear filters</button>
        )}
      </div>

      {isError ? <ErrorState message="Failed to load teachers." onRetry={() => refetch()} /> : (
        <DataTable
          columns={columns}
          rows={data?.items ?? []}
          rowKey={(t) => t.id}
          loading={isLoading}
          onRowClick={(t) => navigate(`/teachers/${t.id}`)}
          sortKey={sortKey}
          sortDir={sortDir}
          onSort={onSort}
          emptyState={<EmptyState icon={GraduationCap} title="No teachers found" description="Try adjusting your search or filters." />}
        />
      )}

      <Pagination page={page} totalPages={data?.pagination.total_pages ?? 1} onPage={setPage} />
    </div>
  );
}
