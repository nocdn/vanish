FROM python:3.11-slim AS builder

# Prevent building as root for security
RUN if [ "$(whoami)" = "root" ] && [ "${DOCKER_BUILDKIT:-}" != "1" ]; then \
        echo "ERROR: Do not build this container as root user for security reasons." && \
        echo "Please run: docker build commands as a non-root user." && \
        exit 1; \
    fi

WORKDIR /app

COPY requirements.txt .
RUN pip wheel --wheel-dir /wheels -r requirements.txt

FROM python:3.11-slim AS runtime
WORKDIR /app

COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

COPY . .

RUN addgroup --system app && adduser --system --ingroup app app
USER app

EXPOSE 6020

ENV FLASK_RUN_PORT=6020
ENV FLASK_DEBUG=false

# Run with a single worker to avoid SQLite write contention (see critique 1.2)
CMD ["gunicorn", "--bind", "0.0.0.0:6020", "--workers", "1", "main:app"]

# --- Notes on Database Persistence ---
# The application uses a SQLite database located at the fixed path /app/data/emails.db inside the container.
# To make this database persistent across container restarts and accessible
# on your host machine, you MUST mount a host directory to the container's
# /app/data directory when running `docker run`.
#
# Example: To store the database in a 'data' subdirectory of your project root:
# docker run ... -v "$(pwd)/data":/app/data ... <image_name>
#
# Failure to mount a volume will result in database loss when the container stops.