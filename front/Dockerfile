# Use official Node.js LTS image
FROM node:22-alpine AS base

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install --legacy-peer-deps

# Development stage
FROM base AS development
COPY . .
# compose runs this as the host UID so that .nuxt/ and any lockfile the dev
# server writes into the bind-mounted ./front are not root-owned. node_modules
# is an anonymous volume seeded from this path, so it must be chowned too or the
# Vite dep cache under it is unwritable.
RUN chown -R 1000:1000 /app
EXPOSE 3000
CMD ["npm", "run", "dev"]

# Build stage
FROM base AS build
# Both are also passed as runtime env by docker-compose.prod.yml — Nuxt reads
# runtimeConfig.public from the environment per request (nuxt.config.ts), so the
# build arg is what the client bundle falls back to and the env var is what
# actually serves. They must agree.
ARG NUXT_PUBLIC_API_BASE_URL
ARG NUXT_PUBLIC_VERSION
ENV NUXT_PUBLIC_API_BASE_URL=${NUXT_PUBLIC_API_BASE_URL} \
	NUXT_PUBLIC_VERSION=${NUXT_PUBLIC_VERSION}
COPY . .
RUN npm run build

# Production stage: only the Nitro output, which bundles its own runtime
# dependencies. Shipping the build stage instead meant a ~2.2 GB image of
# node_modules, whose export alone took >13 min on the production HDD.
FROM node:22-alpine AS production
WORKDIR /app
ARG NUXT_PUBLIC_API_BASE_URL
ARG NUXT_PUBLIC_VERSION
ENV NODE_ENV=production \
	NUXT_PUBLIC_API_BASE_URL=${NUXT_PUBLIC_API_BASE_URL} \
	NUXT_PUBLIC_VERSION=${NUXT_PUBLIC_VERSION}
COPY --from=build /app/.output ./.output
EXPOSE 3000
CMD ["node", ".output/server/index.mjs"]
