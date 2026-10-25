# Development image for the BankCashOps frontend (Vite dev server).
FROM node:22-alpine

# Patch the Alpine packages of the base image. The floating node:22-alpine tag
# keeps a cached image alive for a while, and such an image may still carry
# outdated OS libraries (for example zlib) with published vulnerabilities.
RUN apk upgrade --no-cache

# The npm CLI bundled into the Node image pins its own dependencies (pacote,
# sigstore, brace-expansion, glob matchers, ...). Install the current CLI so the
# image does not ship the versions those advisories are filed against.
RUN npm install -g npm@12.2.1

# npm 12.2.1 still vendors undici 6.29.0 and ip-address 10.7.2, which have
# published advisories. Substitute the patched releases without touching the
# rest of the bundled CLI.
RUN mkdir -p /tmp/npm-patch \
    && cd /tmp/npm-patch \
    && npm init -y > /dev/null \
    && npm install --silent undici@6.29.1 ip-address@10.7.4 \
    && rm -rf /usr/local/lib/node_modules/npm/node_modules/undici \
    && rm -rf /usr/local/lib/node_modules/npm/node_modules/ip-address \
    && cp -a /tmp/npm-patch/node_modules/undici /usr/local/lib/node_modules/npm/node_modules/undici \
    && cp -a /tmp/npm-patch/node_modules/ip-address /usr/local/lib/node_modules/npm/node_modules/ip-address \
    && rm -rf /tmp/npm-patch

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev"]
