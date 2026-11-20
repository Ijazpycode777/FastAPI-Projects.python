import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { GraduationCap, Eye, EyeOff, AlertCircle } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { useToast } from "@/hooks/useToast";
import { ApiError } from "@/lib/api";
import { Field, TextInput } from "@/components/forms";

const schema = z.object({
  email: z.string().email("Enter a valid email address."),
  password: z.string().min(1, "Password is required."),
});
type FormValues = z.infer<typeof schema>;

export function LoginPage() {
  const { login } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  const { register, handleSubmit, formState: { errors } } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { email: "", password: "" },
  });

  const onSubmit = async (values: FormValues) => {
    setSubmitting(true);
    setServerError(null);
    try {
      const profile = await login(values.email, values.password);
      toast.success("Welcome back", profile.user.full_name);
      const role = profile.user.role;
      navigate(role === "admin" ? "/admin" : role === "teacher" ? "/teacher" : "/student", { replace: true });
    } catch (e) {
      const err = e as ApiError;
      setServerError(err.message ?? "Login failed. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-full grid lg:grid-cols-2 bg-slate-bg">
      {/* Brand panel */}
      <div className="hidden lg:flex flex-col justify-between bg-navy text-white p-12 relative overflow-hidden">
        <div className="absolute -top-20 -right-20 h-72 w-72 rounded-full bg-indigo/30 blur-3xl" />
        <div className="absolute -bottom-24 -left-10 h-72 w-72 rounded-full bg-teal/20 blur-3xl" />
        <div className="relative flex items-center gap-3">
          <div className="h-11 w-11 rounded-xl bg-indigo grid place-items-center font-bold">SC</div>
          <div>
            <p className="font-bold text-lg">Smart Campus</p>
            <p className="text-white/60 text-xs">College Management System</p>
          </div>
        </div>
        <div className="relative max-w-md">
          <h1 className="text-3xl font-bold leading-tight">Run your campus with clarity.</h1>
          <p className="mt-3 text-white/70 text-sm leading-relaxed">
            One platform for students, teachers and administrators — attendance, examinations,
            grading, fees, timetables, study materials and notices, all in one place.
          </p>
          <div className="mt-8 grid grid-cols-3 gap-4">
            {[["Students", "Enrolment & history"], ["Academics", "Exams & grading"], ["Finance", "Fees & receipts"]].map(([t, d]) => (
              <div key={t} className="rounded-lg bg-white/5 border border-white/10 p-3">
                <p className="text-sm font-semibold">{t}</p>
                <p className="text-[11px] text-white/50 mt-0.5">{d}</p>
              </div>
            ))}
          </div>
        </div>
        <p className="relative text-white/40 text-xs">© {new Date().getFullYear()} Smart Campus. Synthetic demo data only.</p>
      </div>

      {/* Form panel */}
      <div className="flex items-center justify-center p-6 sm:p-12">
        <div className="w-full max-w-sm">
          <div className="lg:hidden flex items-center gap-2.5 mb-8">
            <div className="h-10 w-10 rounded-xl bg-indigo grid place-items-center text-white"><GraduationCap size={20} /></div>
            <p className="font-bold text-navy text-lg">Smart Campus</p>
          </div>

          <h2 className="text-2xl font-bold text-navy">Sign in</h2>
          <p className="text-sm text-slate-muted mt-1">Enter your credentials to access your dashboard.</p>

          {serverError && (
            <div className="mt-5 flex items-start gap-2 rounded-lg border border-rose/30 bg-rose/5 px-3.5 py-2.5 text-sm text-rose">
              <AlertCircle size={16} className="mt-0.5 shrink-0" />
              <span>{serverError}</span>
            </div>
          )}

          <form onSubmit={handleSubmit(onSubmit)} className="mt-6 space-y-4">
            <Field label="Email address" required error={errors.email?.message}>
              <TextInput type="email" autoComplete="email" placeholder="you@smartcampus.edu" {...register("email")} />
            </Field>
            <Field label="Password" required error={errors.password?.message}>
              <div className="relative">
                <TextInput type={showPassword ? "text" : "password"} autoComplete="current-password" placeholder="••••••••" {...register("password")} />
                <button type="button" onClick={() => setShowPassword((s) => !s)} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-muted hover:text-navy">
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </Field>
            <button type="submit" disabled={submitting} className="btn-primary w-full">
              {submitting ? "Signing in…" : "Sign in"}
            </button>
          </form>

          <div className="mt-8 rounded-lg border border-slate-border bg-white p-4">
            <p className="text-xs font-semibold text-navy mb-2">Demo accounts</p>
            <ul className="text-xs text-slate-muted space-y-1">
              <li><span className="text-navy font-medium">Admin</span> · admin@smartcampus.edu / ChangeMe!2025</li>
              <li><span className="text-navy font-medium">Teacher</span> · teacher.sarah@smartcampus.edu / Teacher!2025</li>
              <li><span className="text-navy font-medium">Student</span> · student.ali@smartcampus.edu / Student!2025</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
