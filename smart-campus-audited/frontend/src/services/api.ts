/**
 * Service barrel.
 *
 * The HTTP client implementation lives in `lib/api.ts` (low-level, no React
 * dependencies) so it can be reused outside React if needed. This file
 * re-exports the public surface under the conventional `services/` path
 * expected by the repository structure.
 */
export { http, api, ApiError, API_BASE, setCsrfToken } from "@/lib/api";
export type { RequestOptions } from "@/lib/api";
