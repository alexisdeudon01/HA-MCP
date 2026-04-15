ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base-python:3.12-alpine3.20
FROM ${BUILD_FROM}

# ── Dépendances système ───────────────────────────────────────────────────────
RUN apk add --no-cache \
    # C/C++ compilers (requis pour compiler PyMuPDF sur aarch64)
    gcc g++ musl-dev python3-dev \
    # PDF processing (mupdf système — évite de le recompiler depuis PyMuPDF)
    mupdf-tools mupdf-dev \
    freetype-dev harfbuzz-dev jpeg-dev openjpeg-dev zlib-dev jbig2dec-dev \
    # Node.js + npm pour les serveurs MCP stdio (npx)
    nodejs npm \
    # Utilitaires
    curl bash

# ── npm global cache dans un path writeable ───────────────────────────────────
ENV NPM_CONFIG_CACHE=/tmp/npm-cache
ENV NPM_CONFIG_PREFIX=/usr/local

# ── PyMuPDF : utiliser le mupdf système (évite téléchargement + compilation) ──
# PYMUPDF_SETUP_MUPDF_BUILD='' indique à PyMuPDF de ne pas recompiler mupdf
ENV PYMUPDF_SETUP_MUPDF_BUILD=

# ── Pré-installer les serveurs MCP stdio utilisés ────────────────────────────
RUN npm install -g \
    duckduckgo-mcp-server \
    @modelcontextprotocol/server-sequential-thinking \
    @modelcontextprotocol/server-filesystem \
    @modelcontextprotocol/server-memory \
    @modelcontextprotocol/server-everything \
    @playwright/mcp \
    && npm cache clean --force

# ── Dépendances Python ────────────────────────────────────────────────────────
COPY requirements.txt /tmp/
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt

# ── Application ───────────────────────────────────────────────────────────────
COPY app/      /app/
COPY schemas/  /schemas/
COPY config/   /config/
COPY database/ /database/
COPY rootfs/   /

COPY run.sh /
RUN chmod a+x /run.sh

WORKDIR /

CMD ["/run.sh"]
