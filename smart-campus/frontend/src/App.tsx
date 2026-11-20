import { AuthProvider } from "@/hooks/useAuth";
import { AppRoutes } from "@/routes/AppRoutes";

/**
 * Top-level application: wires the auth context and the route table.
 * Route definitions, lazy imports and role guards live in `routes/AppRoutes`.
 */
export default function App() {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  );
}
