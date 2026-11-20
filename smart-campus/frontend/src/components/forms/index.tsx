import { forwardRef, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";
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

// Custom inputs used with react-hook-form's `register` MUST forward `ref`.
// `register` returns { ref, onChange, onBlur, name }; if the wrapper is a plain
// function component React silently drops `ref`, so RHF never sees the DOM node
// and cannot read autofilled values at submit — the form then reports every
// field as empty ("required") even when the box shows text. forwardRef fixes this.
export const TextInput = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  function TextInput({ className, ...props }, ref) {
    return <input ref={ref} className={cn("input", className)} {...props} />;
  }
);

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  function Select({ className, children, ...props }, ref) {
    return <select ref={ref} className={cn("input", className)} {...props}>{children}</select>;
  }
);

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(
  function Textarea({ className, ...props }, ref) {
    return <textarea ref={ref} className={cn("input", className)} {...props} />;
  }
);
