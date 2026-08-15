# Development image. Production builds the SPA inside the root Dockerfile.
FROM node:22-alpine

RUN apk add --no-cache curl

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .

# node:alpine ships an unprivileged `node` user already.
RUN chown -R node:node /app
USER node

EXPOSE 5173
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
    CMD curl -fsS http://127.0.0.1:5173/ || exit 1

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
