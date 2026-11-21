import { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Plus, Search, Users, FilterX } from "lucide-react";
import { PageHeader, Badge, Pagination, EmptyState, ErrorState } from "@/components/common";
import { DataTable, type Column } from "@/components/tables/DataTable";
import { Select } from "@/components/forms";
import { useDebounce } from "@/hooks/useDebounce";
import { http } from "@/lib/api";
import { useStudents } from "./queries";
import { useShifts } from "@/features/campus/queries";
import type { Student, AcademicSession, ClassLevel, Section } from "@/types";

const STATUS_OPTS = ["active", "inactive", "graduated", "left", "suspended"];

export function StudentListPage() {
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [shiftId, setShiftId] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [classId, setClassId] = useState("");
  const [sectionId, setSectionId] = useState("");
  const [status, setStatus] = useState("");
  const [sortKey, setSortKey] = useState("created_at");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [page, setPage] = useState(1);
  const debounced = useDebounce(q, 300);

  const { data: shifts } = useShifts();
  const sessions = useQuery({ queryKey: ["sessions"], queryFn: () => http.get<AcademicSession[]>("/sessions") });
  const classes = useQuery({ queryKey: ["classes"], queryFn: () => http.get<ClassLevel[]>("/classes") });
  const sections = useQuery({ queryKey: ["sections"], queryFn: () => http.get<Section[]>("/sections") });

  const classSections = useMemo(() => (sections.data ?? []).filter((s) => s.class_level_id === classId), [sections.data, classId]);
  const nameOf = (list: { id: string; name: string }[] | undefined, id?: string | null) =>
    (id && list?.find((x) => x.id === id)?.name) ?? "—";

  const params = {
    q: debounced || undefined, campus_shift_id: shiftId || undefined, session_id: sessionId || undefined,
    class_id: classId || undefined, section_id: sectionId || undefined, status: status || undefined,
    sort: sortKey, order: sortDir, page, page_size: 20,
  };
  const { data, isLoading, isError, refetch } = useStudents(params);

  const hasFilters = !!(shiftId || sessionId || classId || sectionId || status || q);
  const clearFilters = () => { setQ(""); setShiftId(""); setSessionId(""); setClassId(""); setSectionId(""); setStatus(""); setPage(1); };

  const onSort = (key: string) => {
    const backendKey = key === "roll" ? "roll" : key === "full_name" ? "full_name" : "created_at";
    if (sortKey === backendKey) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else { setSortKey(backendKey); setSortDir("asc"); }
  };

  const columns: Column<Student>[] = [
    { key: "current_roll_number", header: "Roll", sortable: true, render: (s) => <span className="font-semibold text-ink">{s.current_roll_number ?? "—"}</span> },
    { key: "full_name", header: "Name", sortable: true, render: (s) => (
      <div className="min-w-0">
        <p className="font-medium text-ink truncate">{s.full_name}</p>
        <p className="text-[11px] text-slate-muted truncate">{s.admission_number}</p>
      </div>
    ) },
    { key: "campus_shift_id", header: "Shift", render: (s) => <span className="text-slate-muted">{nameOf(shifts, s.campus_shift_id)}</span> },
    { key: "current_session_id", header: "Session", render: (s) => <span className="text-slate-muted">{nameOf(sessions.data, s.current_session_id)}</span> },
    { key: "current_class_id", header: "Class", render: (s) => <span className="text-slate-muted">{nameOf(classes.data, s.current_class_id)}</span> },
    { key: "current_section_id", header: "Section", render: (s) => <span className="text-slate-muted">{nameOf(sections.data, s.current_section_id)}</span> },
    { key: "account_status", header: "Status", render: (s) => <Badge status={s.account_status}>{s.account_status}</Badge> },
  ];

  return (
    <div>
      <PageHeader
        title="Student Logs"
        description="Search and inspect student records by roll number, name, shift, session, class and section."
        action={<button onClick={() => navigate("/students/new")} className="btn-primary"><Plus size={16} /> Add Student</button>}
      />

      <div className="card p-4 mb-4 space-y-3">
        <div className="relative max-w-md">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-muted" />
          <input className="input pl-9" placeholder="Search by roll number, name, admission no. or email…" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} />
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
          <Select value={shiftId} onChange={(e) => { setShiftId(e.target.value); setPage(1); }}>
            <option value="">All shifts</option>
            {shifts?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </Select>
          <Select value={sessionId} onChange={(e) => { setSessionId(e.target.value); setPage(1); }}>
            <option value="">All sessions</option>
            {sessions.data?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </Select>
          <Select value={classId} onChange={(e) => { setClassId(e.target.value); setSectionId(""); setPage(1); }}>
            <option value="">All classes</option>
            {classes.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </Select>
          <Select value={sectionId} onChange={(e) => { setSectionId(e.target.value); setPage(1); }} disabled={!classId}>
            <option value="">{classId ? "All sections" : "Select class"}</option>
            {classSections.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
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

      {isError ? <ErrorState message="Failed to load students." onRetry={() => refetch()} /> : (
        <DataTable
          columns={columns}
          rows={data?.items ?? []}
          rowKey={(s) => s.id}
          loading={isLoading}
          onRowClick={(s) => navigate(`/students/${s.id}`)}
          sortKey={sortKey}
          sortDir={sortDir}
          onSort={onSort}
          emptyState={<EmptyState icon={Users} title="No students found" description="Try adjusting your search or filters." />}
        />
      )}

      <Pagination page={page} totalPages={data?.pagination.total_pages ?? 1} onPage={setPage} />
    </div>
  );
}
