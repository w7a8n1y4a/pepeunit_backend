#!/bin/bash

DB_USER=$(echo "$PU_SQLALCHEMY_DATABASE_URL" | sed -E 's|.*://([^:]+):.*|\1|')
DB_PASS=$(echo "$PU_SQLALCHEMY_DATABASE_URL" | sed -E 's|.*://[^:]+:([^@]+)@.*|\1|')
DB_HOST=$(echo "$PU_SQLALCHEMY_DATABASE_URL" | sed -E 's|.*@([^:/]+):.*|\1|')
DB_PORT=$(echo "$PU_SQLALCHEMY_DATABASE_URL" | sed -E 's|.*:([0-9]+)/.*|\1|')
DB_NAME=$(echo "$PU_SQLALCHEMY_DATABASE_URL" | sed -E 's|.*/([^/?]+).*|\1|')

export PGPASSWORD="$DB_PASS"

echo "Wait Ready PostgreSQL..."
until pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER"; do
  sleep 2
  echo "Wait Ready PostgreSQL..."
done
echo "PostgreSQL available."

echo "Wait check DB '$DB_NAME'..."
until psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -tAc \
      "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1; do
  sleep 2
  echo "Wait check DB '$DB_NAME'..."
done
echo "DB '$DB_NAME' Exist."

echo "Fix collation postgres for swap version containers"
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -c "ALTER DATABASE postgres REFRESH COLLATION VERSION;"
echo "Collation fixed."

echo "Run migration..."
alembic upgrade head

echo "Del old lock files"
rm -rf tmp/*.lock

gunicorn app.main:app \
    --bind 0.0.0.0:5000 \
    --config gunicorn_conf.py \
    --timeout 300 \
    --workers=$PU_WORKER_COUNT \
    --worker-class uvicorn.workers.UvicornWorker \
    --worker-tmp-dir=/dev/shm \
