import { Link } from "react-router-dom";
import { ShieldAlert } from "lucide-react";

export function ForbiddenPage() {
  return (
    <div className="min-h-full grid place-items-center bg-slate-bg px-6">
      <div className="text-center max-w-md">
        <div className="mx-auto h-14 w-14 rounded-xl bg-rose/10 text-rose grid place-items-center mb-4">
          <ShieldAlert size={26} />
        </div>
        <h1 className="text-2xl font-bold text-navy">Access denied</h1>
        <p className="mt-2 text-sm text-slate-muted">
          You don’t have permission to view this page. If you believe this is an error, contact an administrator.
        </p>
        <Link to="/" className="btn-primary mt-6">Back to dashboard</Link>
      </div>
    </div>
  );
}
