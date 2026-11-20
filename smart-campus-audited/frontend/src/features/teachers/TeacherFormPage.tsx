import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { PageHeader, Card, CardHeader } from "@/components/common";
import { Field, TextInput, Select } from "@/components/forms";
import { http, ApiError } from "@/lib/api";
import { useToast } from "@/hooks/useToast";

const schema = z.object({
  full_name: z.string().min(1, "Required"),
  email: z.string().email("Valid email required"),
  phone: z.string().optional(),
  employee_id: z.string().min(1, "Required"),
  department: z.string().optional(),
  designation: z.string().min(1, "Required"),
  joining_date: z.string().min(1, "Required"),
  password: z.string().min(10, "At least 10 characters"),
});
type FormValues = z.infer<typeof schema>;

export function TeacherFormPage() {
  const navigate = useNavigate();
  const toast = useToast();
  const [submitting, setSubmitting] = useState(false);
  const { register, handleSubmit, formState: { errors } } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { designation: "Lecturer", joining_date: new Date().toISOString().slice(0, 10) },
  });

  const onSubmit = async (v: FormValues) => {
    setSubmitting(true);
    try {
      await http.post("/teachers", { ...v, phone: v.phone || null, department: v.department || null });
      toast.success("Teacher created");
      navigate("/teachers");
    } catch (e) {
      toast.error("Could not create teacher", (e as ApiError).message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-3xl">
      <PageHeader title="Add Teacher" description="Create a teaching staff account." />
      <form onSubmit={handleSubmit(onSubmit)}>
        <Card className="mb-4">
          <CardHeader title="Teacher information" />
          <div className="p-5 grid sm:grid-cols-2 gap-4">
            <Field label="Full name" required error={errors.full_name?.message}><TextInput {...register("full_name")} /></Field>
            <Field label="Email" required error={errors.email?.message}><TextInput type="email" {...register("email")} /></Field>
            <Field label="Phone"><TextInput {...register("phone")} /></Field>
            <Field label="Employee ID" required error={errors.employee_id?.message}><TextInput {...register("employee_id")} /></Field>
            <Field label="Department"><TextInput {...register("department")} /></Field>
            <Field label="Designation" required error={errors.designation?.message}>
              <Select {...register("designation")}>
                <option>Lecturer</option><option>Senior Lecturer</option><option>Assistant Professor</option><option>Professor</option>
              </Select>
            </Field>
            <Field label="Joining date" required error={errors.joining_date?.message}><TextInput type="date" {...register("joining_date")} /></Field>
            <Field label="Initial password" required error={errors.password?.message} hint="Min 10 chars, with upper/lower/digit/symbol."><TextInput type="text" {...register("password")} /></Field>
          </div>
        </Card>
        <div className="flex justify-end gap-2">
          <button type="button" onClick={() => navigate("/teachers")} className="btn-secondary">Cancel</button>
          <button type="submit" disabled={submitting} className="btn-primary">{submitting ? "Creating…" : "Create Teacher"}</button>
        </div>
      </form>
    </div>
  );
}
