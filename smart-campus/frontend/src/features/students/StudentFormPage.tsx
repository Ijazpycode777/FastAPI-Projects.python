import { useEffect, useState } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { PageHeader, Card, CardHeader, Skeleton } from "@/components/common";
import { Field, TextInput, Select } from "@/components/forms";
import { http, ApiError } from "@/lib/api";
import { useToast } from "@/hooks/useToast";
import { useStudent } from "./queries";
import { useShifts } from "@/features/campus/queries";

// Placement is free text (like a username): the admin types the program,
// class/part, section and academic session names. The backend find-or-creates
// the underlying rows, so there are no fixed dropdown values to pre-populate.
// Campus shift is a managed entity (admin creates Morning/Evening) so it is a
// dropdown. Roll number is manually assigned and unique within the shift.
const schema = z.object({
  full_name: z.string().min(1, "Required"),
  email: z.string().email("Valid email required"),
  phone: z.string().optional(),
  date_of_birth: z.string().optional(),
  gender: z.enum(["male", "female", "other"]).or(z.literal("")),
  admission_date: z.string().min(1, "Required"),
  campus_shift_id: z.string().min(1, "Select a campus shift"),
  roll_number: z.coerce.number().int().min(1, "Roll must be a positive number"),
  program: z.string().min(1, "Required"),
  class_name: z.string().min(1, "Required"),
  section: z.string().min(1, "Required"),
  academic_session: z.string().min(1, "Required"),
  // Only required when creating (edit mode does not render this field).
  password: z.string().min(10, "At least 10 characters").optional(),
  guardian_name: z.string().optional(),
  guardian_phone: z.string().optional(),
});
type FormValues = z.infer<typeof schema>;

export function StudentFormPage() {
  const navigate = useNavigate();
  const toast = useToast();
  const { id } = useParams();
  const isEdit = !!id;
  const [submitting, setSubmitting] = useState(false);

  const { data: existing, isLoading } = useStudent(id);
  const { data: shifts } = useShifts();

  const { register, handleSubmit, reset, formState: { errors } } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { gender: "", admission_date: new Date().toISOString().slice(0, 10), campus_shift_id: "", roll_number: 1 },
  });

  // Prefill from the existing student's resolved placement names when editing.
  useEffect(() => {
    if (isEdit && existing) {
      reset({
        full_name: existing.full_name,
        email: existing.email,
        phone: existing.phone ?? "",
        date_of_birth: existing.date_of_birth ?? "",
        gender: (existing.gender ?? "") as FormValues["gender"],
        admission_date: existing.admission_date,
        campus_shift_id: existing.campus_shift_id ?? "",
        roll_number: existing.current_roll_number ?? 1,
        program: existing.program_name ?? "",
        class_name: existing.class_name ?? "",
        section: existing.section_name ?? "",
        academic_session: existing.session_name ?? "",
        guardian_name: "",
        guardian_phone: "",
      });
    }
  }, [existing, isEdit, reset]);

  const onSubmit = async (v: FormValues) => {
    setSubmitting(true);
    try {
      const payload: Record<string, unknown> = {
        full_name: v.full_name, email: v.email, phone: v.phone || null,
        date_of_birth: v.date_of_birth || null, gender: v.gender || null,
        admission_date: v.admission_date,
        campus_shift_id: v.campus_shift_id, roll_number: v.roll_number,
        program: v.program, class_name: v.class_name,
        section: v.section, academic_session: v.academic_session,
      };
      if (!isEdit) payload.password = v.password;
      if (v.guardian_name && v.guardian_phone) {
        payload.guardian = { name: v.guardian_name, phone: v.guardian_phone };
      }
      const student = isEdit
        ? await http.patch<{ id: string }>(`/students/${id}`, payload)
        : await http.post<{ id: string }>("/students", payload);
      toast.success(isEdit ? "Student updated" : "Student created", student.id);
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

  return (
    <div className="max-w-3xl">
      <PageHeader
        title={isEdit ? "Edit Student" : "Add Student"}
        description={isEdit ? "Update student details and placement." : "Create a student account and enrol them in a class."}
      />
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
          <CardHeader title="Campus & roll number" subtitle="Roll numbers are unique within the selected shift." />
          <div className="p-5 grid sm:grid-cols-2 gap-4">
            <Field label="Campus shift" required error={errors.campus_shift_id?.message}
              hint={shifts && shifts.length === 0 ? "No shifts yet — create one first." : undefined}>
              <Select {...register("campus_shift_id")}>
                <option value="">Select shift…</option>
                {shifts?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </Select>
            </Field>
            <Field label="Roll number" required error={errors.roll_number?.message} hint="Manually assigned (e.g. 1, 2, 3…)">
              <TextInput type="number" min={1} {...register("roll_number", { valueAsNumber: true })} />
            </Field>
            {shifts && shifts.length === 0 && (
              <p className="sm:col-span-2 text-sm text-slate-muted">
                <Link to="/campus/shifts" className="text-indigo font-medium">Create a campus shift</Link> before adding students.
              </p>
            )}
          </div>
        </Card>

        <Card className="mb-4">
          <CardHeader title="Placement" subtitle="Type the names — new values are created automatically." />
          <div className="p-5 grid sm:grid-cols-2 gap-4">
            <Field label="Academic session" required error={errors.academic_session?.message} hint="e.g. 2025-2026">
              <TextInput {...register("academic_session")} placeholder="2025-2026" />
            </Field>
            <Field label="Program" required error={errors.program?.message} hint="e.g. ICS, FSc, BSCS">
              <TextInput {...register("program")} placeholder="ICS" />
            </Field>
            <Field label="Class / Part" required error={errors.class_name?.message} hint="e.g. Part 1, Year 2">
              <TextInput {...register("class_name")} placeholder="Part 1" />
            </Field>
            <Field label="Section" required error={errors.section?.message} hint="e.g. A, B, Morning">
              <TextInput {...register("section")} placeholder="A" />
            </Field>
          </div>
        </Card>

        <Card className="mb-4">
          <CardHeader title={isEdit ? "Guardian" : "Account & guardian"} />
          <div className="p-5 grid sm:grid-cols-2 gap-4">
            {!isEdit && (
              <Field label="Initial password" required error={errors.password?.message} hint="Min 10 chars, with upper/lower/digit/symbol.">
                <TextInput type="text" {...register("password")} />
              </Field>
            )}
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
