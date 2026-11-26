import { useState } from "react";
import {
  Layers, Plus, Trash2, Pencil, Building2, BookOpen, Users, GraduationCap, X, Check,
} from "lucide-react";
import {
  PageHeader, Card, CardHeader, Badge, EmptyState, ErrorState, Modal, Skeleton,
} from "@/components/common";
import { Field, TextInput, Select } from "@/components/forms";
import { ApiError } from "@/lib/api";
import { useToast } from "@/hooks/useToast";
import {
  useClassDistribution, usePrograms, useAllSubjects, useDepartments,
  useCreateProgram, useDeleteProgram,
  useCreateClass, useUpdateClass, useDeleteClass,
  useCreateSection, useDeleteSection,
  useCreateSubject, useDeleteSubject,
} from "@/features/academicQueries";
import type { ClassDistribution } from "@/types";

/**
 * Admin "Classes Distribution" page.
 *
 * The canonical place to build the academic structure BEFORE enrolling
 * students: programs, classes (parts/years), sections and subjects. Students
 * are then placed by selecting these rows (by ID) in the student form — so two
 * students in "PB 21" always share the same class row. Departments are the
 * fixed, migration-seeded set (read-only).
 */
export function ClassesDistributionPage() {
  const toast = useToast();
  const { data: dist, isLoading, isError, refetch } = useClassDistribution();
  const { data: programs } = usePrograms();
  const { data: subjects } = useAllSubjects();
  const { data: departments } = useDepartments();

  // --- Modals + form state ---
  const [programModal, setProgramModal] = useState(false);
  const [classModal, setClassModal] = useState(false);
  const [subjectModal, setSubjectModal] = useState(false);
  const [programForm, setProgramForm] = useState({ code: "", name: "" });
  const [classForm, setClassForm] = useState({ program_id: "", name: "", year: 1 });
  const [subjectForm, setSubjectForm] = useState({ program_id: "", code: "", name: "", theory_marks: 100, practical_marks: 0 });

  // Inline section add (per class) + class rename.
  const [sectionAdding, setSectionAdding] = useState<string | null>(null);
  const [sectionName, setSectionName] = useState("");
  const [renaming, setRenaming] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");

  // --- Mutations ---
  const createProgram = useCreateProgram();
  const deleteProgram = useDeleteProgram();
  const createClass = useCreateClass();
  const updateClass = useUpdateClass();
  const deleteClass = useDeleteClass();
  const createSection = useCreateSection();
  const deleteSection = useDeleteSection();
  const createSubject = useCreateSubject();
  const deleteSubject = useDeleteSubject();

  const errOf = (e: unknown) => (e instanceof ApiError ? e.message : (e as Error).message);

  // --- Handlers ---
  const onProgramCreate = async () => {
    if (!programForm.code || !programForm.name) return;
    try {
      await createProgram.mutateAsync({ code: programForm.code, name: programForm.name });
      toast.success("Program created");
      setProgramModal(false); setProgramForm({ code: "", name: "" });
    } catch (e) { toast.error("Could not create program", errOf(e)); }
  };
  const onProgramDelete = async (id: string, name: string) => {
    if (!confirm(`Delete program "${name}"? This fails if it still has classes, subjects or students.`)) return;
    try { await deleteProgram.mutateAsync(id); toast.success("Program deleted"); }
    catch (e) { toast.error("Could not delete program", errOf(e)); }
  };

  const onClassCreate = async () => {
    if (!classForm.program_id || !classForm.name) return;
    try {
      await createClass.mutateAsync({ program_id: classForm.program_id, name: classForm.name, year: classForm.year });
      toast.success("Class created");
      setClassModal(false); setClassForm({ program_id: "", name: "", year: 1 });
    } catch (e) { toast.error("Could not create class", errOf(e)); }
  };
  const onClassRename = async (cls: ClassDistribution) => {
    if (!renameValue.trim()) { setRenaming(null); return; }
    try {
      await updateClass.mutateAsync({ id: cls.id, name: renameValue.trim() });
      toast.success("Class renamed");
    } catch (e) { toast.error("Could not rename class", errOf(e)); }
    finally { setRenaming(null); }
  };
  const onClassDelete = async (cls: ClassDistribution) => {
    if (!confirm(`Delete class "${cls.name}" (${cls.program_name})? This fails if it has students, assignments, exams or materials.`)) return;
    try { await deleteClass.mutateAsync(cls.id); toast.success("Class deleted"); }
    catch (e) { toast.error("Could not delete class", errOf(e)); }
  };

  const onSectionAdd = async (cls: ClassDistribution) => {
    if (!sectionName.trim()) { setSectionAdding(null); return; }
    try {
      await createSection.mutateAsync({ class_level_id: cls.id, name: sectionName.trim(), capacity: 40 });
      toast.success("Section added");
      setSectionName(""); setSectionAdding(null);
    } catch (e) { toast.error("Could not add section", errOf(e)); }
  };
  const onSectionDelete = async (sectionId: string, name: string) => {
    if (!confirm(`Delete section "${name}"? This fails if a student is placed in it.`)) return;
    try { await deleteSection.mutateAsync(sectionId); toast.success("Section deleted"); }
    catch (e) { toast.error("Could not delete section", errOf(e)); }
  };

  const onSubjectCreate = async () => {
    if (!subjectForm.program_id || !subjectForm.code || !subjectForm.name) return;
    try {
      await createSubject.mutateAsync({
        program_id: subjectForm.program_id, code: subjectForm.code, name: subjectForm.name,
        theory_marks: subjectForm.theory_marks, practical_marks: subjectForm.practical_marks,
      });
      toast.success("Subject created");
      setSubjectModal(false);
      setSubjectForm({ program_id: "", code: "", name: "", theory_marks: 100, practical_marks: 0 });
    } catch (e) { toast.error("Could not create subject", errOf(e)); }
  };
  const onSubjectDelete = async (id: string, name: string) => {
    if (!confirm(`Delete subject "${name}"? This fails if it is used by assignments, exams or marks.`)) return;
    try { await deleteSubject.mutateAsync(id); toast.success("Subject deleted"); }
    catch (e) { toast.error("Could not delete subject", errOf(e)); }
  };

  const programName = (id: string) => programs?.find((p) => p.id === id)?.name ?? "—";
  const subjectsByProgram = (programId: string) => subjects?.filter((s) => s.program_id === programId) ?? [];

  return (
    <div className="max-w-5xl">
      <PageHeader
        title="Classes Distribution"
        description="Build the academic structure first — programs, classes, sections and subjects. Students are then placed by selecting these rows, so two students in the same class always share one class row."
        action={<button onClick={() => setClassModal(true)} className="btn-primary" disabled={!programs?.length}>
          <Plus size={16} /> New Class
        </button>}
      />

      {!programs?.length && (
        <Card className="mb-4">
          <EmptyState icon={Building2} title="Create a program first"
            description="Classes belong to programs. Create a program before adding classes."
            action={<button onClick={() => setProgramModal(true)} className="btn-primary"><Plus size={16} /> New Program</button>} />
        </Card>
      )}

      {/* ---------------- Classes (distribution view) ---------------- */}
      <Card className="mb-4">
        <CardHeader title="Classes" subtitle="Each class with its sections, designated subjects and enrolment."
          action={<button onClick={() => setProgramModal(true)} className="btn-ghost !px-2" title="New program"><Building2 size={16} /></button>} />
        <div className="p-5">
          {isError ? <ErrorState message="Could not load classes." onRetry={() => refetch()} /> :
           isLoading ? <div className="space-y-3"><Skeleton className="h-24" /><Skeleton className="h-24" /></div> :
           !dist?.length ? <EmptyState icon={Layers} title="No classes yet" description="Create a class to get started." /> :
           <div className="space-y-3">
             {dist.map((cls) => (
               <div key={cls.id} className="rounded-xl border border-slate-hairline p-4">
                 <div className="flex items-start justify-between gap-3 flex-wrap">
                   <div className="min-w-0">
                     <div className="flex items-center gap-2 flex-wrap">
                       {renaming === cls.id ? (
                         <span className="flex items-center gap-1">
                           <TextInput value={renameValue} onChange={(e) => setRenameValue(e.target.value)}
                             className="!w-40" autoFocus onKeyDown={(e) => e.key === "Enter" && onClassRename(cls)} />
                           <button onClick={() => onClassRename(cls)} className="text-teal hover:text-teal/80"><Check size={16} /></button>
                           <button onClick={() => setRenaming(null)} className="text-slate-muted hover:text-ink"><X size={16} /></button>
                         </span>
                       ) : (
                         <p className="font-semibold text-ink">{cls.name}</p>
                       )}
                       <Badge>{cls.program_name}</Badge>
                       <span className="text-xs text-slate-muted">Year {cls.year}</span>
                       <span className="text-xs text-slate-muted">· {cls.enrolled} enrolled</span>
                     </div>
                   </div>
                   <div className="flex items-center gap-1">
                     {renaming !== cls.id && (
                       <button onClick={() => { setRenaming(cls.id); setRenameValue(cls.name); }} className="btn-ghost !px-2" title="Rename"><Pencil size={15} /></button>
                     )}
                     <button onClick={() => onClassDelete(cls)} className="btn-ghost !px-2 text-slate-muted hover:text-rose" title="Delete class"><Trash2 size={15} /></button>
                   </div>
                 </div>

                 <div className="mt-3 grid sm:grid-cols-2 gap-4">
                   {/* Sections */}
                   <div>
                     <div className="flex items-center justify-between mb-1.5">
                       <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-muted">Sections</p>
                       <button onClick={() => { setSectionAdding(sectionAdding === cls.id ? null : cls.id); setSectionName(""); }}
                         className="text-xs text-indigo hover:underline">{sectionAdding === cls.id ? "Cancel" : "+ Add"}</button>
                     </div>
                     {sectionAdding === cls.id && (
                       <div className="flex items-center gap-1 mb-2">
                         <TextInput value={sectionName} onChange={(e) => setSectionName(e.target.value)} placeholder="e.g. B"
                           className="!w-28" autoFocus onKeyDown={(e) => e.key === "Enter" && onSectionAdd(cls)} />
                         <button onClick={() => onSectionAdd(cls)} className="btn-primary !px-2"><Check size={15} /></button>
                       </div>
                     )}
                     <div className="flex flex-wrap gap-1.5">
                       {cls.sections.length === 0 && !sectionAdding && <span className="text-xs text-slate-muted">No sections</span>}
                       {cls.sections.map((s) => (
                         <span key={s.id} className="inline-flex items-center gap-1 rounded-md bg-slate-bg px-2 py-1 text-xs">
                           {s.name} <span className="text-slate-muted">· {s.enrolled}/{s.capacity}</span>
                           <button onClick={() => onSectionDelete(s.id, s.name)} className="text-slate-muted hover:text-rose"><X size={12} /></button>
                         </span>
                       ))}
                     </div>
                   </div>
                   {/* Designated subjects (from the program) */}
                   <div>
                     <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-muted mb-1.5">Subjects</p>
                     <div className="flex flex-wrap gap-1.5">
                       {cls.subjects.length === 0 && <span className="text-xs text-slate-muted">No subjects for {cls.program_name}</span>}
                       {cls.subjects.map((s) => (
                         <span key={s.id} className="inline-flex items-center gap-1 rounded-md bg-indigo/10 px-2 py-1 text-xs text-indigo">
                           <BookOpen size={12} /> {s.code} · {s.name}
                         </span>
                       ))}
                     </div>
                   </div>
                 </div>
               </div>
             ))}
           </div>}
        </div>
      </Card>

      {/* ---------------- Programs ---------------- */}
      <Card className="mb-4">
        <CardHeader title="Programs" subtitle="e.g. ICS, FSc, BSCS."
          action={<button onClick={() => setProgramModal(true)} className="btn-ghost !px-2" title="New program"><Plus size={16} /></button>} />
        <div className="p-5">
          {!programs?.length ? <EmptyState icon={Building2} title="No programs yet" /> : (
            <div className="divide-y divide-slate-hairline">
              {programs.map((p) => (
                <div key={p.id} className="flex items-center justify-between py-2.5">
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-xs rounded bg-slate-bg px-1.5 py-0.5 text-slate-muted">{p.code}</span>
                    <span className="font-medium text-ink">{p.name}</span>
                    <span className="text-xs text-slate-muted">· {dist?.filter((c) => c.program_id === p.id).length ?? 0} classes</span>
                  </div>
                  <button onClick={() => onProgramDelete(p.id, p.name)} className="text-slate-muted hover:text-rose" title="Delete program"><Trash2 size={15} /></button>
                </div>
              ))}
            </div>
          )}
        </div>
      </Card>

      {/* ---------------- Subjects ---------------- */}
      <Card className="mb-4">
        <CardHeader title="Subjects" subtitle="Designated to programs; shown on each class of the program."
          action={<button onClick={() => setSubjectModal(true)} className="btn-ghost !px-2" disabled={!programs?.length} title="New subject"><Plus size={16} /></button>} />
        <div className="p-5">
          {!programs?.length ? <EmptyState icon={BookOpen} title="Create a program first" /> :
           !subjects?.length ? <EmptyState icon={BookOpen} title="No subjects yet" description="Add subjects to programs." /> : (
            <div className="space-y-3">
              {programs.map((p) => {
                const subs = subjectsByProgram(p.id);
                if (!subs.length) return null;
                return (
                  <div key={p.id}>
                    <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-muted mb-1.5">{p.name}</p>
                    <div className="divide-y divide-slate-hairline rounded-lg border border-slate-hairline">
                      {subs.map((s) => (
                        <div key={s.id} className="flex items-center justify-between py-2 px-3">
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-xs text-slate-muted">{s.code}</span>
                            <span className="text-sm text-ink">{s.name}</span>
                            <span className="text-xs text-slate-muted">· {s.theory_marks}+{s.practical_marks}</span>
                          </div>
                          <button onClick={() => onSubjectDelete(s.id, s.name)} className="text-slate-muted hover:text-rose" title="Delete subject"><Trash2 size={14} /></button>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </Card>

      {/* ---------------- Departments (read-only) ---------------- */}
      <Card>
        <CardHeader title="Departments" subtitle="The fixed set every teacher belongs to. Not creatable or deletable." />
        <div className="p-5">
          {!departments?.length ? <EmptyState icon={Users} title="No departments" /> : (
            <div className="flex flex-wrap gap-2">
              {departments.map((d) => (
                <span key={d.id} className="inline-flex items-center gap-1.5 rounded-lg bg-slate-bg px-3 py-1.5 text-sm text-ink">
                  <GraduationCap size={14} className="text-slate-muted" /> {d.name}
                </span>
              ))}
            </div>
          )}
        </div>
      </Card>

      {/* ---------------- Modals ---------------- */}
      <Modal open={programModal} onClose={() => setProgramModal(false)} title="New program"
        footer={<><button onClick={() => setProgramModal(false)} className="btn-secondary">Cancel</button>
          <button onClick={onProgramCreate} disabled={createProgram.isPending || !programForm.code || !programForm.name} className="btn-primary">
            {createProgram.isPending ? "Creating…" : "Create"}</button></>}>
        <div className="space-y-3">
          <Field label="Code" required><TextInput value={programForm.code} onChange={(e) => setProgramForm({ ...programForm, code: e.target.value })} placeholder="ICS" /></Field>
          <Field label="Name" required><TextInput value={programForm.name} onChange={(e) => setProgramForm({ ...programForm, name: e.target.value })} placeholder="Intermediate in Computer Science" /></Field>
        </div>
      </Modal>

      <Modal open={classModal} onClose={() => setClassModal(false)} title="New class"
        footer={<><button onClick={() => setClassModal(false)} className="btn-secondary">Cancel</button>
          <button onClick={onClassCreate} disabled={createClass.isPending || !classForm.program_id || !classForm.name} className="btn-primary">
            {createClass.isPending ? "Creating…" : "Create"}</button></>}>
        <div className="space-y-3">
          <Field label="Program" required>
            <Select value={classForm.program_id} onChange={(e) => setClassForm({ ...classForm, program_id: e.target.value })}>
              <option value="">— select —</option>
              {programs?.map((p) => <option key={p.id} value={p.id}>{p.name} ({p.code})</option>)}
            </Select>
          </Field>
          <Field label="Class / Part name" required><TextInput value={classForm.name} onChange={(e) => setClassForm({ ...classForm, name: e.target.value })} placeholder="e.g. Part 1, Year 2, PB 21" /></Field>
          <Field label="Year" required>
            <Select value={classForm.year} onChange={(e) => setClassForm({ ...classForm, year: Number(e.target.value) })}>
              {[1, 2, 3, 4].map((y) => <option key={y} value={y}>{y}</option>)}
            </Select>
          </Field>
        </div>
      </Modal>

      <Modal open={subjectModal} onClose={() => setSubjectModal(false)} title="New subject"
        footer={<><button onClick={() => setSubjectModal(false)} className="btn-secondary">Cancel</button>
          <button onClick={onSubjectCreate} disabled={createSubject.isPending || !subjectForm.program_id || !subjectForm.code || !subjectForm.name} className="btn-primary">
            {createSubject.isPending ? "Creating…" : "Create"}</button></>}>
        <div className="space-y-3">
          <Field label="Program" required>
            <Select value={subjectForm.program_id} onChange={(e) => setSubjectForm({ ...subjectForm, program_id: e.target.value })}>
              <option value="">— select —</option>
              {programs?.map((p) => <option key={p.id} value={p.id}>{p.name} ({p.code})</option>)}
            </Select>
          </Field>
          <Field label="Code" required><TextInput value={subjectForm.code} onChange={(e) => setSubjectForm({ ...subjectForm, code: e.target.value })} placeholder="CS101" /></Field>
          <Field label="Name" required><TextInput value={subjectForm.name} onChange={(e) => setSubjectForm({ ...subjectForm, name: e.target.value })} placeholder="Computer Science" /></Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Theory marks"><TextInput type="number" value={subjectForm.theory_marks} onChange={(e) => setSubjectForm({ ...subjectForm, theory_marks: Number(e.target.value) })} /></Field>
            <Field label="Practical marks"><TextInput type="number" value={subjectForm.practical_marks} onChange={(e) => setSubjectForm({ ...subjectForm, practical_marks: Number(e.target.value) })} /></Field>
          </div>
        </div>
      </Modal>
    </div>
  );
}
