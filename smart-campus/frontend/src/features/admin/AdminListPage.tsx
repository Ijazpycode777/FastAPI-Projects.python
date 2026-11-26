import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ShieldCheck, KeyRound } from "lucide-react";
import { PageHeader, Card, CardHeader, Badge, EmptyState, ErrorState, Skeleton } from "@/components/common";
import { Field, TextInput } from "@/components/forms";
import { http, ApiError } from "@/lib/api";
import { useToast } from "@/hooks/useToast";
import { useAuth } from "@/hooks/useAuth";
import { formatDateTime } from "@/lib/utils";
import type { User } from "@/types";

const schema = z.object({
  full_name: z.string().min(1, "Required"),
  email: z.string().email("Valid email required"),
  phone: z.string().optional(),
  password: z.string().min(10, "At least 10 characters").max(128),
});
type FormValues = z.infer<typeof schema>;

export function AdminListPage() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [submitting, setSubmitting] = useState(false);
  const { profile } = useAuth();
  const selfId = profile?.user.id;

  const { data: admins, isLoading, isError, refetch } = useQuery({
    queryKey: ["admins"],
    queryFn: () => http.get<User[]>("/auth/admins"),
  });

  const { register, handleSubmit, reset, formState: { errors } } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { full_name: "", email: "", phone: "", password: "" },
  });

  const onSubmit = async (v: FormValues) => {
    setSubmitting(true);
    try {
      const created = await http.post<User>("/auth/admins", {
        full_name: v.full_name,
        email: v.email,
        phone: v.phone || null,
        password: v.password,
      });
      toast.success("Administrator created", created.email);
      reset({ full_name: "", email: "", phone: "", password: "" });
      queryClient.invalidateQueries({ queryKey: ["admins"] });
    } catch (e) {
      toast.error("Could not create administrator", (e as ApiError).message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-4xl space-y-4">
      <PageHeader
        title="Administrators"
        description="Create additional administrator accounts. A new admin can sign in immediately with the password you set."
      />

      <Card>
        <CardHeader title="Create administrator" subtitle="Min 10 characters, with upper/lower/digit/symbol." />
        <form onSubmit={handleSubmit(onSubmit)} className="p-5 grid sm:grid-cols-2 gap-4">
          <Field label="Full name" required error={errors.full_name?.message}><TextInput {...register("full_name")} /></Field>
          <Field label="Email" required error={errors.email?.message}><TextInput type="email" {...register("email")} /></Field>
          <Field label="Phone"><TextInput {...register("phone")} /></Field>
          <Field label="Password" required error={errors.password?.message} hint="Hand this to the new admin — they can change it later from their own account.">
            <TextInput type="text" {...register("password")} />
          </Field>
          <div className="sm:col-span-2 flex justify-end">
            <button type="submit" disabled={submitting} className="btn-primary">
              <ShieldCheck size={16} /> {submitting ? "Creating…" : "Create administrator"}
            </button>
          </div>
        </form>
      </Card>

      <Card>
        <CardHeader title="All administrators" />
        <div className="p-5">
          {isLoading ? (
            <div className="space-y-2"><Skeleton className="h-10 w-full" /><Skeleton className="h-10 w-full" /><Skeleton className="h-10 w-full" /></div>
          ) : isError ? (
            <ErrorState message="Could not load administrators." onRetry={() => refetch()} />
          ) : !admins?.length ? (
            <EmptyState icon={ShieldCheck} title="No administrators" description="Create one above." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-slate-muted border-b border-line">
                    <th className="py-2 pr-4 font-medium">Name</th>
                    <th className="py-2 pr-4 font-medium">Email</th>
                    <th className="py-2 pr-4 font-medium">Phone</th>
                    <th className="py-2 pr-4 font-medium">Last login</th>
                    <th className="py-2 pr-4 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {admins.map((a) => (
                    <tr key={a.id} className="border-b border-line/60">
                      <td className="py-2 pr-4">
                        <span className="font-medium text-ink">{a.full_name}</span>
                        {a.id === selfId && <span className="ml-2 text-[11px] text-slate-muted">(you)</span>}
                      </td>
                      <td className="py-2 pr-4 text-slate-muted">{a.email}</td>
                      <td className="py-2 pr-4 text-slate-muted">{a.phone || "—"}</td>
                      <td className="py-2 pr-4 text-slate-muted">{a.last_login_at ? formatDateTime(a.last_login_at) : "never"}</td>
                      <td className="py-2 pr-4">
                        {a.is_active ? <Badge status="active">active</Badge> : <Badge>inactive</Badge>}
                        {a.must_reset_password && <span className="ml-2 inline-flex items-center gap-1 text-[11px] text-amber-600"><KeyRound size={11} /> reset</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}
