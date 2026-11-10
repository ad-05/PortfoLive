# ---- 1. build the React frontend ----
FROM node:20-alpine AS client
WORKDIR /client
COPY client/package*.json ./
RUN npm ci
COPY client/ ./
RUN npm run build

# ---- 2. Python base with runtime deps ----
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY server/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# ---- 3. test stage: `docker build --target test .` (used by Jenkins) ----
FROM base AS test
COPY server/requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY server/ ./
RUN pytest -q   # pytest.ini adds --cov and writes coverage.xml

# ---- 3b. exports coverage.xml for SonarQube:
#      DOCKER_BUILDKIT=1 docker build --target test-report --output type=local,dest=reports .
FROM scratch AS test-report
COPY --from=test /app/coverage.xml /coverage.xml

# ---- 4. final runtime image (default target) ----
FROM base
COPY server/app ./app
COPY server/templates ./templates
COPY --from=client /client/dist ./public
RUN useradd -m app && mkdir -p /data && chown -R app /data
USER app
ENV APP_ENV=production DATA_DIR=/data PORT=4000
EXPOSE 4000
HEALTHCHECK CMD python -c "import urllib.request as u; u.urlopen('http://localhost:4000/health')" || exit 1
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "4000"]
