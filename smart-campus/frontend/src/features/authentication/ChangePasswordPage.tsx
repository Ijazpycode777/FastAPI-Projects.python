import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { KeyRound, Eye, EyeOff } from "lucide-react";
import { PageHeader, Card, CardHeader } from "@/components/common";
import { Field, TextInput } from "@/components/forms";
import { http, ApiError } from "@/lib/api";
import { useToast } from "@/hooks/useToast";
import { useAuth } from "@/hooks/useAuth";

const schema = z.object({
  current_password: z.string().min(1, "Current password is required."),
  new_password: z
    .string()
    .min(10, "At least 10 characters.")
    .max(128, "At most 128 characters."),
});
type FormValues = z.infer<typeof schema>;

export function ChangePasswordPage() {
  const navigate = useNavigate();
  const toast = useToast();
  const { refresh, profile } = useAuth();
  const [submitting, setSubmitting] = useState(false);
  const [showCurrent, setShowCurrent] = useState(false);
  const [showNew, setShowNew] = useState(false);

  const { register, handleSubmit, formState: { errors } } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { current_password: "", new_password: "" },
  });

  const onSubmit = async (v: FormValues) => {
    setSubmitting(true);
    try {
      await http.post("/auth/password", { current_password: v.current_password, new_password: v.new_password });
      toast.success("Password changed");
      // Re-fetch the profile so must_reset_password flips to false before we
      // route away — otherwise the Protected guard would bounce us back here.
      await refresh();
      const role = profile?.user.role;
      navigate(role === "admin" ? "/admin" : role === "teacher" ? "/teacher" : "/student", { replace: true });
    } catch (e) {
      const err = e as ApiError;
      toast.error("Could not change password", err.message ?? "Action failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-md">
      <PageHeader
        title="Change Password"
        description="Your account requires a password reset before you can continue. Choose a new password (minimum 10 characters)."
      />
      <form onSubmit={handleSubmit(onSubmit)}>
        <Card>
          <CardHeader title="Set a new password" />
          <div className="p-5 space-y-4">
            <Field label="Current password" required error={errors.current_password?.message}>
              <div className="relative">
                <TextInput type={showCurrent ? "text" : "password"} autoComplete="current-password" {...register("current_password")} />
                <button type="button" onClick={() => setShowCurrent((s) => !s)} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-muted hover:text-ink">
                  {showCurrent ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </Field>
            <Field label="New password" required error={errors.new_password?.message} hint="Min 10 characters, with upper/lower/digit/symbol.">
              <div className="relative">
                <TextInput type={showNew ? "text" : "password"} autoComplete="new-password" {...register("new_password")} />
                <button type="button" onClick={() => setShowNew((s) => !s)} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-muted hover:text-ink">
                  {showNew ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </Field>
            <div className="flex justify-end gap-2">
              <button type="submit" disabled={submitting} className="btn-primary">
                <KeyRound size={16} /> {submitting ? "Saving…" : "Change password"}
              </button>
            </div>
          </div>
        </Card>
      </form>
    </div>
  );
}
