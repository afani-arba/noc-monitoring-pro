# Tahap 1: Build React App (Vite)
FROM node:20-alpine AS build
WORKDIR /app

ARG APP_COMMIT_SHA=dev
ARG REACT_APP_EDITION=monitoring_pro
ARG REACT_APP_PRODUCT_NAME="NOC Monitoring Pro"

ENV VITE_API_URL=/api
ENV VITE_EDITION=${REACT_APP_EDITION}
ENV VITE_PRODUCT_NAME=${REACT_APP_PRODUCT_NAME}
ENV GENERATE_SOURCEMAP=false
ENV CI=false
ENV DISABLE_ESLINT_PLUGIN=true
ENV NODE_OPTIONS="--max_old_space_size=4096"

COPY package*.json ./
RUN npm install --legacy-peer-deps

COPY . .
RUN npm run build

# Tahap 2: Serve dengan Nginx
FROM nginx:alpine
# Menghapus konfigurasi default nginx
RUN rm -rf /usr/share/nginx/html/*
# Vite output ke /dist bukan /build
COPY --from=build /app/dist /usr/share/nginx/html
# Konfigurasi routing Nginx (SPA support)
COPY nginx-custom.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
