# Database image for the BankCashOps stacks.
#
# The upstream ``postgres:16-alpine`` image ships a prebuilt ``gosu`` binary
# compiled with an older Go toolchain. Vulnerability scanners report the
# standard-library advisories of that toolchain against the whole image, even
# though ``gosu`` itself never exercises the affected packages.
# ``gosu`` is only used by the upstream entrypoint to step down from root, so a
# current release is rebuilt here with the current Go toolchain and swapped in.
# The entrypoint and the rest of the image are left untouched.

# --- Build gosu with a patched Go toolchain -------------------------------- #
FROM golang:1.27-alpine AS gosu

ARG GOSU_VERSION=1.20

RUN apk add --no-cache git

# Upstream tags are not Go module versions, so the source is cloned at the
# release tag and built in place. ``golang.org/x/sys`` is bumped past the
# release pinned by gosu because scanners flag that version as well.
RUN git clone --depth 1 --branch "${GOSU_VERSION}" https://github.com/tianon/gosu /src \
    && cd /src \
    && go get golang.org/x/sys@v0.44.0 \
    && CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /gosu .

# --- Runtime --------------------------------------------------------------- #
FROM postgres:16-alpine

# Patch the Alpine packages of the base image. The floating postgres:16-alpine
# tag keeps a cached image alive for a while, and such an image may still carry
# outdated OS libraries with published vulnerabilities.
RUN apk upgrade --no-cache

COPY --from=gosu /gosu /usr/local/bin/gosu
