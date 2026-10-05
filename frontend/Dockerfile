FROM node:24-alpine
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# GATEWAY_URL: where the Next server proxies /api (inside the compose network).
# NEXT_PUBLIC_GATEWAY_WS: where the *browser* opens the live WebSocket (the stream service).
ARG GATEWAY_URL=http://engine:8000
ARG NEXT_PUBLIC_GATEWAY_WS=ws://localhost:8002/ws/live
ENV GATEWAY_URL=$GATEWAY_URL \
    NEXT_PUBLIC_GATEWAY_WS=$NEXT_PUBLIC_GATEWAY_WS \
    NEXT_TELEMETRY_DISABLED=1
RUN npm run build
EXPOSE 3000
CMD ["npm", "start"]
