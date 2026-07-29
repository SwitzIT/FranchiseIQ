FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
# v6.6 — Vite bakes import.meta.env.VITE_API_URL into the built JS bundle
# at BUILD time, not container-run time. The old Dockerfile had no way to
# receive this value at all, so any docker-compose/docker-run 'environment:'
# setting for VITE_API_URL was silently ignored — the frontend would fall
# back to whatever default is hardcoded in src/services/api.js. Pass it as
# a build arg instead: `docker build --build-arg VITE_API_URL=https://your-backend-url ...`
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
