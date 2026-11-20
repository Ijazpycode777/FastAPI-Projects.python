# Postgres initialization script (docker-compose)

# Mounted by docker-compose into the Postgres container's
# /docker-entrypoint-initdb.d/ directory. Runs once when the data volume is
# first created.

# Ensure deterministic, timezone-aware timestamps everywhere.
ALTER DATABASE smartcampus SET timezone TO 'UTC';

# Connection logging is helpful during local development.
ALTER DATABASE smartcampus SET log_connections TO 'on';
