import { Link } from "react-router-dom";
import { Compass } from "lucide-react";

export function NotFound() {
  return (
    <div className="min-h-full grid place-items-center bg-slate-bg px-6">
      <div className="text-center max-w-md">
        <div className="mx-auto h-14 w-14 rounded-xl bg-indigo/10 text-indigo grid place-items-center mb-4">
          <Compass size={26} />
        </div>
        <h1 className="text-2xl font-bold text-ink">Page not found</h1>
        <p className="mt-2 text-sm text-slate-muted">
          The page you’re looking for doesn’t exist or may have been moved.
        </p>
        <Link to="/" className="btn-primary mt-6">Back to dashboard</Link>
      </div>
    </div>
  );
}
