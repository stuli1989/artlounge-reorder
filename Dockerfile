# Stage 1: Build React frontend
FROM node:20-alpine AS frontend
WORKDIR /app/dashboard
COPY src/dashboard/package.json src/dashboard/package-lock.json ./
RUN npm ci --legacy-peer-deps
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

# Copy startup script
COPY start.sh ./
RUN chmod +x start.sh

# Railway sets PORT env var
ENV PORT=8000
EXPOSE 8000

CMD ["./start.sh"]
