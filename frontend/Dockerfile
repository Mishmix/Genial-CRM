FROM node:20-alpine AS builder

# Force rebuild v2 - timezone fix
WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

# Build with production API URL
ENV VITE_API_URL=https://genial-crm-production.up.railway.app/api
ENV VITE_WS_URL=wss://genial-crm-production.up.railway.app/ws

RUN npm run build

# Production image with nginx
FROM nginx:alpine

# Copy built files
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy startup script
COPY start.sh /start.sh
RUN chmod +x /start.sh

EXPOSE 80

CMD ["/start.sh"]
