# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Caviar frontend - production image (multi-stage).
#
# Stage 1 (builder): install deps and produce the static Vite build.
# Stage 2 (runtime): serve the built assets with nginx.
#
# IMPORTANT: Vite inlines VITE_* variables at BUILD time (they are public
# by design - API base URL and Supabase anon key only, never secrets). They
# must therefore be provided as build args. The primary production target
# is Vercel, which sets these in its own build; this image exists for local
# production simulation and container-based hosting.
# ---------------------------------------------------------------------------

FROM node:22-slim AS builder

WORKDIR /app

# Public build-time configuration (see note above). These are NOT secrets.
ARG VITE_API_BASE_URL=http://localhost:8000/api/v1
ARG VITE_SUPABASE_URL=https://example.supabase.co
ARG VITE_SUPABASE_ANON_KEY=replace-me
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_SUPABASE_URL=$VITE_SUPABASE_URL \
    VITE_SUPABASE_ANON_KEY=$VITE_SUPABASE_ANON_KEY

# Install dependencies against the lockfile for reproducible builds.
COPY package.json package-lock.json ./
RUN npm ci

# Build the static bundle.
COPY . .
RUN npm run build

# ---------------------------------------------------------------------------

FROM nginx:1.27-alpine AS runtime

# Drop the default site and install the SPA config.
RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/caviar.conf

# Copy the built static assets.
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1/healthz || exit 1

CMD ["nginx", "-g", "daemon off;"]
