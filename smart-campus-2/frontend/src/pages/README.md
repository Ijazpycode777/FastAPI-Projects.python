# pages/

Route-level page components are organized **by feature** under
`src/features/<module>/` (e.g. `features/students/StudentListPage.tsx`),
co-located with their queries and supporting code. This keeps each module's
UI, data fetching and form logic together.

The route table that wires these pages into URL paths lives in
`src/routes/AppRoutes.tsx`.

This directory is kept intentionally empty to match the recommended repository
structure; new top-level pages that don't belong to a feature module may be
placed here.
