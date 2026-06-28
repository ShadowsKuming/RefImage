FROM node:22-slim AS builder

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .
RUN npm run build

# ── Runtime ──────────────────────────────────────────────────
FROM node:22-slim

WORKDIR /app

COPY --from=builder /app/.output ./.output

EXPOSE 3000

ENV NODE_ENV=production

CMD ["node", ".output/server/index.mjs"]
