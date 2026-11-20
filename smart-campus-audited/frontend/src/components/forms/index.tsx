import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export function Field({ label, error, required, children, hint }: { label: string; error?: string; required?: boolean; children: ReactNode; hint?: string }) {
  return (
    <div>
      <label className="label">
        {label} {required && <span className="text-rose">*</span>}
      </label>
      {children}
      {hint && !error && <p className="mt-1 text-xs text-slate-muted">{hint}</p>}
      {error && <p className="mt-1 text-xs text-rose">{error}</p>}
    </div>
  );
}

export function Select({ className, children, ...props }: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={cn("input", className)} {...props}>{children}</select>;
}

export function TextInput({ className, ...props }: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn("input", className)} {...props} />;
}

export function Textarea({ className, ...props }: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={cn("input", className)} {...props} />;
}
