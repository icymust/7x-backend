FROM node:20-alpine AS build
WORKDIR /app

# Empty by default so the built app calls the API with relative paths
# (e.g. /api/...), letting the nginx proxy route them same-origin -
# this is what makes single-port forwarding for presentations work.
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
