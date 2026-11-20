# docker/

Auxiliary Docker assets used by `docker-compose.yml`.

- `postgres-init.sql` — runs once when the local Postgres data volume is first
  created (sets the database timezone to UTC and enables connection logging
  for local development).

The build itself uses the root `Dockerfile` (multi-stage: builds the frontend
and runs the backend, serving both from one origin). See the root
`docker-compose.yml` and `docs/DEPLOYMENT.md` for details.
