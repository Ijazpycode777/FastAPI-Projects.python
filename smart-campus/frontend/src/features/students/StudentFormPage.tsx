import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { PageHeader, Card, CardHeader } from "@/components/common";
import { Field, TextInput, Select } from "@/components/forms";
import { http, ApiError } from "@/lib/api";
import { useToast } from "@/hooks/useToast";
import { useSessions, usePrograms, useClasses, useSections } from "@/features/academicQueries";

const schema = z.object({
  full_name: z.string().min(1, "Required"),
  email: z.string().email("Valid email required"),
  phone: z.string().optional(),
  date_of_birth: z.string().optional(),
  gender: z.enum(["male", "female", "other"]).or(z.literal("")),
  admission_date: z.string().min(1, "Required"),
  program_id: z.string().min(1, "Required"),
  class_id: z.string().min(1, "Required"),
  section_id: z.string().min(1, "Required"),
  academic_session_id: z.string().min(1, "Required"),
  password: z.string().min(10, "At least 10 characters"),
  guardian_name: z.string().optional(),
  guardian_phone: z.string().optional(),
});
type FormValues = z.infer<typeof schema>;

export function StudentFormPage() {
  const navigate = useNavigate();
  const toast = useToast();
  const [submitting, setSubmitting] = useState(false);
  const { register, handleSubmit, watch, formState: { errors } } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { gender: "", admission_date: new Date().toISOString().slice(0, 10) },
  });

  const sessions = useSessions();
  const programs = usePrograms();
  const programId = watch("program_id");
  const classId = watch("class_id");
  const classes = useClasses(programId);
  const sections = useSections(classId);

  const onSubmit = async (v: FormValues) => {
    setSubmitting(true);
    try {
      const payload: Record<string, unknown> = {
        full_name: v.full_name, email: v.email, phone: v.phone || null,
        date_of_birth: v.date_of_birth || null, gender: v.gender || null,
        admission_date: v.admission_date, program_id: v.program_id, class_id: v.class_id,
        section_id: v.section_id, academic_session_id: v.academic_session_id, password: v.password,
      };
      if (v.guardian_name && v.guardian_phone) {
        payload.guardian = { name: v.guardian_name, phone: v.guardian_phone };
      }
      const student = await http.post<{ id: string }>("/students", payload);
      toast.success("Student created", student.id);
      navigate(`/students/${student.id}`);
    } catch (e) {
      toast.error("Could not create student", (e as ApiError).message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-3xl">
      <PageHeader title="Add Student" description="Create a student account and enrol them in a class." />
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
          <CardHeader title="Placement" />
          <div className="p-5 grid sm:grid-cols-2 gap-4">
            <Field label="Academic session" required error={errors.academic_session_id?.message}>
              <Select {...register("academic_session_id")}>
                <option value="">Select…</option>
                {sessions.data?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </Select>
            </Field>
            <Field label="Program" required error={errors.program_id?.message}>
              <Select {...register("program_id")}>
                <option value="">Select…</option>
                {programs.data?.map((p) => <option key={p.id} value={p.id}>{p.code} — {p.name}</option>)}
              </Select>
            </Field>
            <Field label="Class / Part" required error={errors.class_id?.message}>
              <Select {...register("class_id")} disabled={!programId}>
                <option value="">Select…</option>
                {classes.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </Select>
            </Field>
            <Field label="Section" required error={errors.section_id?.message}>
              <Select {...register("section_id")} disabled={!classId}>
                <option value="">Select…</option>
                {sections.data?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </Select>
            </Field>
          </div>
        </Card>

        <Card className="mb-4">
          <CardHeader title="Account & guardian" />
          <div className="p-5 grid sm:grid-cols-2 gap-4">
            <Field label="Initial password" required error={errors.password?.message} hint="Min 10 chars, with upper/lower/digit/symbol.">
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
          <button type="submit" disabled={submitting} className="btn-primary">{submitting ? "Creating…" : "Create Student"}</button>
        </div>
      </form>
    </div>
  );
}
