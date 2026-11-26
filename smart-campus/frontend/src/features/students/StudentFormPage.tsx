import { useEffect, useState } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useQueryClient } from "@tanstack/react-query";
import { PageHeader, Card, CardHeader, Skeleton, EmptyState } from "@/components/common";
import { Field, TextInput, Select } from "@/components/forms";
import { Layers } from "lucide-react";
import { http, ApiError } from "@/lib/api";
import { useToast } from "@/hooks/useToast";
import { useStudent } from "./queries";
import { useSessions, usePrograms, useClasses, useSections } from "@/features/academicQueries";

// Placement is ID-based: the admin selects canonical academic rows (managed on
// the Classes Distribution page) from dropdowns. No free text — so two students
// in "PB 21" always share the same class row. Roll numbers are auto-assigned.
const schema = z.object({
  full_name: z.string().min(1, "Required"),
  email: z.string().email("Valid email required"),
  phone: z.string().optional(),
  date_of_birth: z.string().optional(),
  gender: z.enum(["male", "female", "other"]).or(z.literal("")),
  admission_date: z.string().min(1, "Required"),
  academic_session_id: z.string().min(1, "Required"),
  program_id: z.string().min(1, "Required"),
  class_id: z.string().min(1, "Required"),
  section_id: z.string().min(1, "Required"),
  // Required when creating; optional when editing (leave blank to keep the
  // current password). An admin can set a new password directly from the edit
  // form — it is hashed and applied on the backend (no temporary/reset flow).
  password: z.union([z.string().min(10, "At least 10 characters"), z.literal("")]).optional(),
  guardian_name: z.string().optional(),
  guardian_phone: z.string().optional(),
});
type FormValues = z.infer<typeof schema>;

export function StudentFormPage() {
  const navigate = useNavigate();
  const toast = useToast();
  const queryClient = useQueryClient();
  const { id } = useParams();
  const isEdit = !!id;
  const [submitting, setSubmitting] = useState(false);

  const { data: existing, isLoading } = useStudent(id);
  const { data: sessions } = useSessions();
  const { data: programs } = usePrograms();

  const { register, handleSubmit, reset, watch, setValue, formState: { errors } } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { gender: "", admission_date: new Date().toISOString().slice(0, 10) },
  });

  const programId = watch("program_id");
  const classId = watch("class_id");
  const sectionId = watch("section_id");
  // Cascading dropdowns: classes filtered by the selected program, sections by
  // the selected class. Both are disabled (skip the fetch) until the parent is set.
  const { data: classes } = useClasses(programId);
  const { data: sections } = useSections(classId);

  // Prefill from the existing student's placement IDs when editing.
  useEffect(() => {
    if (isEdit && existing) {
      reset({
        full_name: existing.full_name,
        email: existing.email,
        phone: existing.phone ?? "",
        date_of_birth: existing.date_of_birth ?? "",
        gender: (existing.gender ?? "") as FormValues["gender"],
        admission_date: existing.admission_date,
        academic_session_id: existing.current_session_id ?? "",
        program_id: existing.current_program_id ?? "",
        class_id: existing.current_class_id ?? "",
        section_id: existing.current_section_id ?? "",
        guardian_name: "",
        guardian_phone: "",
      });
    }
  }, [existing, isEdit, reset]);

  // When the program changes, drop the class/section if they no longer belong to it.
  useEffect(() => {
    if (programId && classes && classId && !classes.some((c) => c.id === classId)) {
      setValue("class_id", "");
      setValue("section_id", "");
    }
  }, [programId, classes, classId, setValue]);

  // When the class changes, drop the section if it no longer belongs to it.
  useEffect(() => {
    if (classId && sections && sectionId && !sections.some((s) => s.id === sectionId)) {
      setValue("section_id", "");
    }
  }, [classId, sections, sectionId, setValue]);

  const onSubmit = async (v: FormValues) => {
    setSubmitting(true);
    try {
      const payload: Record<string, unknown> = {
        full_name: v.full_name, email: v.email, phone: v.phone || null,
        date_of_birth: v.date_of_birth || null, gender: v.gender || null,
        admission_date: v.admission_date,
        program_id: v.program_id, class_id: v.class_id,
        section_id: v.section_id, academic_session_id: v.academic_session_id,
      };
      if (!isEdit) {
        if (!v.password) {
          toast.error("Initial password is required", "Min 10 characters, with upper/lower/digit/symbol.");
          setSubmitting(false);
          return;
        }
        payload.password = v.password;
      } else if (v.password) {
        // Edit: only send a password when the admin typed a new one.
        payload.password = v.password;
      }
      if (v.guardian_name && v.guardian_phone) {
        payload.guardian = { name: v.guardian_name, phone: v.guardian_phone };
      }
      const student = isEdit
        ? await http.patch<{ id: string }>(`/students/${id}`, payload)
        : await http.post<{ id: string }>("/students", payload);
      toast.success(isEdit ? "Student updated" : "Student created", student.id);
      queryClient.invalidateQueries({ queryKey: ["students"] });
      navigate(`/students/${student.id}`);
    } catch (e) {
      toast.error(isEdit ? "Could not update student" : "Could not create student", (e as ApiError).message);
    } finally {
      setSubmitting(false);
    }
  };

  if (isEdit && isLoading) {
    return <div className="space-y-4"><Skeleton className="h-8 w-48" /><Skeleton className="h-96" /></div>;
  }

  // If the academic structure is empty, the admin must build it first — there is
  // nothing to select from. This is the whole point of the Classes Distribution page.
  const noStructure = !isEdit && (!programs?.length || !sessions?.length);

  return (
    <div className="max-w-3xl">
      <PageHeader
        title={isEdit ? "Edit Student" : "Add Student"}
        description={isEdit ? "Update student details and placement." : "Create a student account and enrol them in a class."}
      />

      {noStructure && (
        <Card className="mb-4">
          <EmptyState icon={Layers} title="Set up the academic structure first"
            description="Before enrolling students, create at least one program, class, section and academic session."
            action={<Link to="/classes" className="btn-primary"><Layers size={16} /> Open Classes Distribution</Link>} />
        </Card>
      )}

      <form onSubmit={handleSubmit(onSubmit)}>
        <Card className="mb-4">
          <CardHeader title="Personal information" />
          <div className="p-5 grid sm:grid-cols-2 gap-4">
            <Field label="Full name" required error={errors.full_name?.message}><TextInput {...register("full_name")} /></Field>
            <Field label="Email" required error={errors.email?.message}><TextInput type="email" {...register("email")} /></Field>
            <Field label="Phone"><TextInput {...register("phone")} /></Field>
            <Field label="Date of birth"><TextInput type="date" {...register("date_of_birth")} /></Field>
            <Field label="Gender"><Select {...register("gender")}><option value="">—</option><option value="male">Male</option><option value="female">Female</option><option value="other">Other</option></Select></Field>
            <Field label="Admission date" required error={errors.admission_date?.message}><TextInput type="date" {...register("admission_date")} /></Field>
          </div>
        </Card>

        <Card className="mb-4">
          <CardHeader title="Placement" subtitle="Select the academic rows created on the Classes Distribution page." />
          <div className="p-5 grid sm:grid-cols-2 gap-4">
            <Field label="Academic session" required error={errors.academic_session_id?.message}>
              <Select {...register("academic_session_id")}>
                <option value="">— select —</option>
                {sessions?.map((s) => <option key={s.id} value={s.id}>{s.name}{s.is_active ? " (active)" : ""}</option>)}
              </Select>
            </Field>
            <Field label="Program" required error={errors.program_id?.message}>
              <Select {...register("program_id")}>
                <option value="">— select —</option>
                {programs?.map((p) => <option key={p.id} value={p.id}>{p.name} ({p.code})</option>)}
              </Select>
            </Field>
            <Field label="Class / Part" required error={errors.class_id?.message} hint={programId && !classes?.length ? "No classes for this program yet" : undefined}>
              <Select {...register("class_id")} disabled={!programId}>
                <option value="">— select —</option>
                {classes?.map((c) => <option key={c.id} value={c.id}>{c.name} (Year {c.year})</option>)}
              </Select>
            </Field>
            <Field label="Section" required error={errors.section_id?.message} hint={classId && !sections?.length ? "No sections for this class yet" : undefined}>
              <Select {...register("section_id")} disabled={!classId}>
                <option value="">— select —</option>
                {sections?.map((s) => <option key={s.id} value={s.id}>{s.name} (cap {s.capacity})</option>)}
              </Select>
            </Field>
          </div>
        </Card>

        <Card className="mb-4">
          <CardHeader title={isEdit ? "Password & guardian" : "Account & guardian"} />
          <div className="p-5 grid sm:grid-cols-2 gap-4">
            <Field
              label={isEdit ? "New password" : "Initial password"}
              required={!isEdit}
              error={errors.password?.message}
              hint={isEdit ? "Leave blank to keep the current password. Min 10 chars, with upper/lower/digit/symbol." : "Min 10 chars, with upper/lower/digit/symbol."}
            >
              <TextInput type="text" {...register("password")} />
            </Field>
            <div className="sm:col-span-2 grid sm:grid-cols-2 gap-4">
              <Field label="Guardian name"><TextInput {...register("guardian_name")} /></Field>
              <Field label="Guardian phone"><TextInput {...register("guardian_phone")} /></Field>
            </div>
          </div>
        </Card>

        <div className="flex justify-end gap-2">
          <button type="button" onClick={() => navigate("/students")} className="btn-secondary">Cancel</button>
          <button type="submit" disabled={submitting} className="btn-primary">
            {submitting ? (isEdit ? "Saving…" : "Creating…") : (isEdit ? "Save changes" : "Create Student")}
          </button>
        </div>
      </form>
    </div>
  );
}
