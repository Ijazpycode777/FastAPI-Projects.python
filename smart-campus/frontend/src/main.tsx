import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider, QueryCache, MutationCache } from "@tanstack/react-query";
import App from "./App";
import { ToastProvider } from "@/hooks/useToast";
import { ApiError } from "@/lib/api";
import "./index.css";

// Global error handler: a 401 (session expired) wipes the cache and bounces
// the user to /login; a 403 PASSWORD_RESET_REQUIRED (backend must-reset gate)
// bounces them to /change-password. window.location is used because the cache
// callbacks live outside React's router context. window.location.assign triggers
// a full reload, which re-runs AuthProvider.refresh() on the destination route.
function onGlobalError(error: unknown) {
  if (!(error instanceof ApiError)) return;
  if (error.status === 401 || error.code === "UNAUTHENTICATED") {
    queryClient.clear();
    if (window.location.pathname !== "/login") window.location.assign("/login");
    return;
  }
  if (error.status === 403 && error.code === "PASSWORD_RESET_REQUIRED") {
    if (window.location.pathname !== "/change-password") window.location.assign("/change-password");
  }
}

const queryClient = new QueryClient({
  queryCache: new QueryCache({ onError: onGlobalError }),
  mutationCache: new MutationCache({ onError: onGlobalError }),
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      gcTime: 5 * 60_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <App />
        </ToastProvider>
      </QueryClientProvider>
    </BrowserRouter>
  </React.StrictMode>
);
