# Stage 1: Build React frontend
FROM node:20-alpine AS frontend
WORKDIR /app/dashboard
COPY src/dashboard/package.json src/dashboard/package-lock.json ./
RUN npm ci
COPY src/dashboard/ ./
# Empty VITE_API_URL = same-origin (frontend served by FastAPI)
ENV VITE_API_URL=
RUN npm run build

# Stage 2: Python API
FROM python:3.12-slim
WORKDIR /app

# Install Python dependencies
COPY src/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source (venv, node_modules, dist excluded by .dockerignore)
COPY src/ ./
# Remove dev-only files that sneak through
RUN rm -rf venv/ dashboard/node_modules/ dashboard/dist/ data/sample_responses/

# Copy built frontend from stage 1
COPY --from=frontend /app/dashboard/dist ./dashboard/dist

# Railway sets PORT env var
ENV PORT=8000
EXPOSE 8000

CMD uvicorn api.main:app --host 0.0.0.0 --port $PORT
