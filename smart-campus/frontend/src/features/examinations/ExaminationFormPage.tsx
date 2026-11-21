import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { PageHeader, Card, CardHeader, Skeleton } from "@/components/common";
import { Field, TextInput, Select } from "@/components/forms";
import { http, ApiError } from "@/lib/api";
import { useToast } from "@/hooks/useToast";
import { usePrograms, useClasses, useSections, useSubjects, useSessions } from "@/features/academicQueries";

interface GradingPolicy {
  id: string;
  name: string;
  is_active: boolean;
}

const EXAM_TYPES = [
  { value: "monthly_test", label: "Monthly Test" },
  { value: "class_test", label: "Class Test" },
  { value: "midterm", label: "Midterm" },
  { value: "final", label: "Final" },
  { value: "quiz", label: "Quiz" },
] as const;

const schema = z
  .object({
    name: z.string().min(1, "Required").max(120, "Max 120 characters"),
    exam_type: z.enum(["monthly_test", "class_test", "midterm", "final", "quiz"]),
    academic_session_id: z.string().min(1, "Required"),
    program_id: z.string().min(1, "Required"),
    class_id: z.string().min(1, "Required"),
    section_id: z.string().optional(),
    subject_id: z.string().min(1, "Required"),
    max_marks: z.coerce.number().int("Must be a whole number").min(1, "Min 1").max(1000, "Max 1000"),
    passing_marks: z.coerce.number().int("Must be a whole number").min(0, "Min 0").max(1000, "Max 1000"),
    exam_date: z.string().min(1, "Required"),
    grading_policy_id: z.string().optional(),
  })
  .refine((d) => d.passing_marks <= d.max_marks, {
    message: "Cannot exceed max marks",
    path: ["passing_marks"],
  });
type FormValues = z.infer<typeof schema>;

export function ExaminationFormPage() {
  const navigate = useNavigate();
  const toast = useToast();
  const qc = useQueryClient();
  const [submitting, setSubmitting] = useState(false);

  const sessions = useSessions();
  const programs = usePrograms();
  const gradingPolicies = useQuery({
    queryKey: ["grading-policies"],
    queryFn: () => http.get<GradingPolicy[]>("/grading"),
  });

  const { register, handleSubmit, watch, setValue, formState: { errors } } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: "",
      exam_type: "class_test",
      academic_session_id: "",
      program_id: "",
      class_id: "",
      section_id: "",
      subject_id: "",
      max_marks: 100,
      passing_marks: 40,
      exam_date: new Date().toISOString().slice(0, 10),
      grading_policy_id: "",
    },
  });

  const programId = watch("program_id");
  const classId = watch("class_id");
  const classes = useClasses(programId || undefined);
  const sections = useSections(classId || undefined);
  const subjects = useSubjects(programId || undefined);

  const onSubmit = async (v: FormValues) => {
    setSubmitting(true);
    try {
      const payload = {
        name: v.name,
        exam_type: v.exam_type,
        academic_session_id: v.academic_session_id,
        program_id: v.program_id,
        class_id: v.class_id,
        section_id: v.section_id || null,
        subject_id: v.subject_id,
        max_marks: Number(v.max_marks),
        passing_marks: Number(v.passing_marks),
        exam_date: v.exam_date,
        grading_policy_id: v.grading_policy_id || null,
      };
      const exam = await http.post<{ id: string }>("/examinations", payload);
      toast.success("Examination created", exam.id);
      qc.invalidateQueries({ queryKey: ["examinations"] });
      navigate("/examinations");
    } catch (e) {
      toast.error("Could not create examination", (e as ApiError).message);
    } finally {
      setSubmitting(false);
    }
  };

  const busy = sessions.isLoading || programs.isLoading || gradingPolicies.isLoading;

  if (busy) {
    return <div className="space-y-4"><Skeleton className="h-8 w-48" /><Skeleton className="h-96" /></div>;
  }

  return (
    <div className="max-w-3xl">
      <PageHeader title="New Examination" description="Create an examination for a subject, class and academic session." />
      <form onSubmit={handleSubmit(onSubmit)}>
        <Card className="mb-4">
          <CardHeader title="Examination details" />
          <div className="p-5 grid sm:grid-cols-2 gap-4">
            <Field label="Name" required error={errors.name?.message}>
              <TextInput {...register("name")} placeholder="e.g. Midterm Fall 2025 — Physics" />
            </Field>
            <Field label="Type" required error={errors.exam_type?.message}>
              <Select {...register("exam_type")}>
                {EXAM_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
              </Select>
            </Field>
            <Field label="Exam date" required error={errors.exam_date?.message}>
              <TextInput type="date" {...register("exam_date")} />
            </Field>
            <Field label="Grading policy" hint="Optional — defaults to the active policy.">
              <Select {...register("grading_policy_id")}>
                <option value="">Default (active)</option>
                {gradingPolicies.data?.map((p) => <option key={p.id} value={p.id}>{p.name}{p.is_active ? " (active)" : ""}</option>)}
              </Select>
            </Field>
            <Field label="Max marks" required error={errors.max_marks?.message}>
              <TextInput type="number" min={1} max={1000} {...register("max_marks")} />
            </Field>
            <Field label="Passing marks" required error={errors.passing_marks?.message}>
              <TextInput type="number" min={0} max={1000} {...register("passing_marks")} />
            </Field>
          </div>
        </Card>

        <Card className="mb-4">
          <CardHeader title="Placement" subtitle="Pick the academic session, program, class, section and subject." />
          <div className="p-5 grid sm:grid-cols-2 gap-4">
            <Field label="Academic session" required error={errors.academic_session_id?.message}>
              <Select {...register("academic_session_id")}>
                <option value="">Select session…</option>
                {sessions.data?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </Select>
            </Field>
            <Field label="Program" required error={errors.program_id?.message}>
              <Select
                {...register("program_id", { onChange: () => { setValue("class_id", ""); setValue("section_id", ""); setValue("subject_id", ""); } })}
              >
                <option value="">Select program…</option>
                {programs.data?.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </Select>
            </Field>
            <Field label="Class / Part" required error={errors.class_id?.message}>
              <Select
                {...register("class_id", { onChange: () => setValue("section_id", "") })}
                disabled={!programId}
              >
                <option value="">{programId ? "Select class…" : "Select a program first"}</option>
                {classes.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </Select>
            </Field>
            <Field label="Section" hint="Optional.">
              <Select {...register("section_id")} disabled={!classId}>
                <option value="">{classId ? "All sections" : "Select a class first"}</option>
                {sections.data?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </Select>
            </Field>
            <Field label="Subject" required error={errors.subject_id?.message}>
              <Select {...register("subject_id")} disabled={!programId}>
                <option value="">{programId ? "Select subject…" : "Select a program first"}</option>
                {subjects.data?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </Select>
            </Field>
          </div>
        </Card>

        <div className="flex justify-end gap-2">
          <button type="button" onClick={() => navigate("/examinations")} className="btn-secondary">Cancel</button>
          <button type="submit" disabled={submitting} className="btn-primary">
            {submitting ? "Creating…" : "Create Examination"}
          </button>
        </div>
      </form>
    </div>
  );
}
