import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { PageHeader, Card, CardHeader, Skeleton, ErrorState } from "@/components/common";
import { Field, TextInput, Select } from "@/components/forms";
import { http, ApiError } from "@/lib/api";
import { useDepartments } from "@/features/academicQueries";
import { useToast } from "@/hooks/useToast";
import type { Teacher } from "@/types";

const createSchema = z.object({
  full_name: z.string().min(1, "Required"),
  email: z.string().email("Valid email required"),
  phone: z.string().optional(),
  employee_id: z.string().min(1, "Required"),
  department_id: z.string().min(1, "Select a department"),
  subject: z.string().min(1, "Subject is required"),
  designation: z.string().min(1, "Required"),
  joining_date: z.string().min(1, "Required"),
  password: z.string().min(10, "At least 10 characters"),
});

const editSchema = z.object({
  full_name: z.string().min(1, "Required"),
  phone: z.string().optional(),
  department_id: z.string().min(1, "Select a department"),
  subject: z.string().min(1, "Subject is required"),
  designation: z.string().min(1, "Required"),
  employment_status: z.string().min(1, "Required"),
  // Optional on edit: an admin can set a new password directly from the form
  // (hashed + applied on the backend). Leave blank to keep the current password.
  password: z.union([z.string().min(10, "At least 10 characters"), z.literal("")]).optional(),
});

type CreateValues = z.infer<typeof createSchema>;
type EditValues = z.infer<typeof editSchema>;

const STATUS_OPTS = ["active", "inactive"];

export function TeacherFormPage() {
  const { id } = useParams<{ id?: string }>();
  const isEdit = !!id;
  const navigate = useNavigate();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [submitting, setSubmitting] = useState(false);
  const departments = useDepartments();

  // Edit mode: load the existing teacher to populate the form.
  const { data: existing, isLoading, isError, refetch } = useQuery({
    queryKey: ["teacher", id],
    queryFn: () => http.get<Teacher>(`/teachers/${id}`),
    enabled: isEdit,
  });

  const form = useForm<CreateValues & EditValues>({
    resolver: zodResolver(isEdit ? editSchema as never : createSchema as never) as never,
    defaultValues: {
      designation: "Lecturer", joining_date: new Date().toISOString().slice(0, 10),
      employment_status: "active",
    },
  });
  const { register, handleSubmit, reset, formState: { errors } } = form;

  useEffect(() => {
    if (isEdit && existing) {
      reset({
        full_name: existing.full_name,
        phone: existing.phone ?? "",
        department_id: existing.department_id,
        subject: existing.subject,
        designation: existing.designation,
        employment_status: existing.employment_status,
      });
    }
  }, [isEdit, existing, reset]);

  const onSubmit = async (v: CreateValues & EditValues) => {
    setSubmitting(true);
    try {
      if (isEdit && id) {
        // Only send editable fields; email/employee_id/joining_date are immutable
        // on update. Password is optional — send it only when the admin typed a
        // new one (it is hashed + applied directly on the backend).
        await http.patch(`/teachers/${id}`, {
          full_name: v.full_name,
          phone: v.phone || null,
          department_id: v.department_id,
          subject: v.subject,
          designation: v.designation,
          employment_status: v.employment_status,
          ...(v.password ? { password: v.password } : {}),
        });
        toast.success("Teacher updated");
        queryClient.invalidateQueries({ queryKey: ["teacher", id] });
        queryClient.invalidateQueries({ queryKey: ["teachers"] });
        navigate(`/teachers/${id}`);
      } else {
        await http.post("/teachers", {
          ...v,
          phone: v.phone || null,
        });
        toast.success("Teacher created");
        queryClient.invalidateQueries({ queryKey: ["teachers"] });
        navigate("/teachers");
      }
    } catch (e) {
      toast.error(isEdit ? "Could not update teacher" : "Could not create teacher", (e as ApiError).message);
    } finally {
      setSubmitting(false);
    }
  };

  if (isEdit && isLoading) return <div className="space-y-4"><Skeleton className="h-8 w-48" /><Skeleton className="h-96" /></div>;
  if (isEdit && isError) return <ErrorState message="Teacher not found." onRetry={() => refetch()} />;

  return (
    <div className="max-w-3xl">
      <PageHeader
        title={isEdit ? "Edit Teacher" : "Add Teacher"}
        description={isEdit ? "Update department, subject and other details." : "Create a teaching staff account."}
      />
      <form onSubmit={handleSubmit(onSubmit)}>
        <Card className="mb-4">
          <CardHeader title="Teacher information" />
          <div className="p-5 grid sm:grid-cols-2 gap-4">
            <Field label="Full name" required error={errors.full_name?.message}><TextInput {...register("full_name")} /></Field>
            {!isEdit && (
              <Field label="Email" required error={errors.email?.message}><TextInput type="email" {...register("email")} /></Field>
            )}
            <Field label="Phone"><TextInput {...register("phone")} /></Field>
            {!isEdit && (
              <Field label="Employee ID" required error={errors.employee_id?.message}><TextInput {...register("employee_id")} /></Field>
            )}
            <Field label="Department" required error={errors.department_id?.message}
              hint="One of the five fixed departments — cannot be created, renamed or deleted here.">
              <Select {...register("department_id")} disabled={departments.isLoading}>
                <option value="">{departments.isLoading ? "Loading…" : "Select department…"}</option>
                {departments.data?.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
              </Select>
            </Field>
            <Field label="Subject" required error={errors.subject?.message}
              hint="Manually entered free text. Independent of department.">
              <TextInput {...register("subject")} placeholder="e.g. Programming Fundamentals" />
            </Field>
            <Field label="Designation" required error={errors.designation?.message}>
              <Select {...register("designation")}>
                <option>Lecturer</option><option>Senior Lecturer</option><option>Assistant Professor</option><option>Professor</option>
              </Select>
            </Field>
            {!isEdit && (
              <Field label="Joining date" required error={errors.joining_date?.message}><TextInput type="date" {...register("joining_date")} /></Field>
            )}
            {isEdit && (
              <Field label="Status" required error={errors.employment_status?.message}>
                <Select {...register("employment_status")}>
                  {STATUS_OPTS.map((s) => <option key={s} value={s}>{s}</option>)}
                </Select>
              </Field>
            )}
            <Field
              label={isEdit ? "New password" : "Initial password"}
              required={!isEdit}
              error={errors.password?.message}
              hint={isEdit ? "Leave blank to keep the current password. Min 10 chars, with upper/lower/digit/symbol." : "Min 10 chars, with upper/lower/digit/symbol."}
            >
              <TextInput type="text" {...register("password")} />
            </Field>
          </div>
        </Card>
        <div className="flex justify-end gap-2">
          <button type="button" onClick={() => navigate(-1)} className="btn-secondary">Cancel</button>
          <button type="submit" disabled={submitting} className="btn-primary">
            {submitting ? "Saving…" : isEdit ? "Save changes" : "Create Teacher"}
          </button>
        </div>
      </form>
    </div>
  );
}
