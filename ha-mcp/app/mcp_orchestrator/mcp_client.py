"""
MCP Client — wrappeur officiel SDK (pip install mcp).

Cycle obligatoire pour tout serveur MCP :
  1. Connexion  : stdio_client (local) ou sse_client (distant via IP/HTTP)
  2. Init       : await session.initialize()  — le serveur partage ses capacités
  3. Extraction :
       session.list_tools()              → outils disponibles
       session.list_resources()          → données/fichiers exposés
       session.get_server_capabilities() → structure technique du serveur

Transports :
  - stdio_client : serveur local lancé via ligne de commande (subprocess)
  - sse_client   : serveur distant via IP/HTTP (Server-Sent Events)
"""

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client
from mcp.types import Tool, Resource

logger = logging.getLogger(__name__)


class MCPClient:
    """Client MCP unifié — stdio (local) ou SSE (distant via IP)."""

    def __init__(self, session: ClientSession, server_info: dict[str, Any]):
        self._session = session
        self.server_info = server_info

    # ── Factories ──────────────────────────────────────────────────────────────

    @classmethod
    @asynccontextmanager
    async def stdio(cls, command: str, args: list[str], env: dict[str, str] | None = None) -> AsyncIterator["MCPClient"]:
        """Connecte un serveur MCP local via stdio (subprocess)."""
        params = StdioServerParameters(command=command, args=args, env=env)
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                info = await session.initialize()
                server_info = {
                    "name":         info.serverInfo.name,
                    "version":      info.serverInfo.version,
                    "transport":    "stdio",
                    "capabilities": info.capabilities.model_dump() if hasattr(info.capabilities, "model_dump") else {},
                }
                logger.info("MCP stdio connected: %s v%s", server_info["name"], server_info["version"])
                yield cls(session, server_info)

    @classmethod
    @asynccontextmanager
    async def sse(cls, url: str, headers: dict[str, str] | None = None) -> AsyncIterator["MCPClient"]:
        """
        Connecte un serveur MCP distant.
        Détecte automatiquement le transport : streamable-http (moderne) ou SSE (ancien).
        """
        transport = await cls._detect_transport(url, headers or {})
        logger.debug("Transport détecté pour %s : %s", url, transport)

        if transport == "streamable-http":
            from mcp.client.streamable_http import streamable_http_client
            import httpx
            # headers passés via http_client personnalisé
            h = headers or {}
            http_client = httpx.AsyncClient(headers=h) if h else None
            async with streamable_http_client(url, http_client=http_client) as (read, write, _):
                async with ClientSession(read, write) as session:
                    info = await session.initialize()
                    yield cls(session, cls._build_server_info(info, "streamable-http", url))
        else:
            async with sse_client(url, headers=headers or {}) as (read, write):
                async with ClientSession(read, write) as session:
                    info = await session.initialize()
                    yield cls(session, cls._build_server_info(info, "sse", url))

    @staticmethod
    async def _detect_transport(url: str, headers: dict) -> str:
        """
        Détecte le bon transport via un POST JSON-RPC minimal.
        streamable-http requiert Accept: application/json, text/event-stream
        et répond 200. SSE répond à un GET avec text/event-stream.
        """
        import httpx
        try:
            async with httpx.AsyncClient(timeout=6) as c:
                r = await c.post(
                    url,
                    json={"jsonrpc": "2.0", "id": 0, "method": "initialize",
                          "params": {"protocolVersion": "2024-11-05",
                                     "capabilities": {},
                                     "clientInfo": {"name": "probe", "version": "1.0"}}},
                    headers={
                        **headers,
                        "Content-Type": "application/json",
                        "Accept": "application/json, text/event-stream",
                    },
                )
                if r.status_code in (200, 202):
                    return "streamable-http"
        except Exception:
            pass
        return "sse"

    @staticmethod
    def _build_server_info(info: Any, transport: str, url: str) -> dict[str, Any]:
        return {
            "name":         info.serverInfo.name,
            "version":      info.serverInfo.version,
            "transport":    transport,
            "url":          url,
            "capabilities": info.capabilities.model_dump() if hasattr(info.capabilities, "model_dump") else {},
        }

    # ── Extraction ─────────────────────────────────────────────────────────────

    async def list_tools(self) -> list[Tool]:
        """Récupère les fonctions/outils exposés par le serveur."""
        result = await self._session.list_tools()
        return result.tools

    async def list_tools_as_dict(self) -> list[dict[str, Any]]:
        """Retourne les outils sous forme de dicts sérialisables (pour la DB)."""
        tools = await self.list_tools()
        return [
            {
                "name":        t.name,
                "description": t.description or "",
                "inputSchema": t.inputSchema.model_dump() if hasattr(t.inputSchema, "model_dump") else dict(t.inputSchema),
            }
            for t in tools
        ]

    async def list_resources(self) -> list[Resource]:
        """Récupère les données/fichiers exposés par le serveur."""
        try:
            result = await self._session.list_resources()
            return result.resources
        except Exception as e:
            logger.debug("list_resources not supported by this server: %s", e)
            return []

    async def list_resources_as_dict(self) -> list[dict[str, Any]]:
        resources = await self.list_resources()
        return [
            {
                "uri":         str(r.uri),
                "name":        r.name,
                "description": r.description or "",
                "mimeType":    r.mimeType or "",
            }
            for r in resources
        ]

    async def get_server_capabilities(self) -> dict[str, Any]:
        """
        Retourne les capacités protocole MCP du serveur (ce qu'il supporte).
        Vient de initialize() — ex: {tools: {...}, resources: None, prompts: None}
        Ce sont des capacités TECHNIQUES, pas des capacités pipeline.
        """
        return self.server_info.get("capabilities", {})

    async def classify_capabilities(self, api_keys: dict[str, str] | None = None) -> list[str]:
        """
        Dérive les capacités PIPELINE depuis les tools.

        Stratégie :
          1. Si api_keys fourni + ANTHROPIC_API_KEY présente → Claude classifie
          2. Sinon → fallback keyword matching (rapide, offline)

        Capacités possibles :
          ingestion | structuration | enrichissement | raisonnement |
          validation | generation | nlp | web_search | web_scrape |
          file_read | file_write | storage
        """
        tools = await self.list_tools_as_dict()
        if not tools:
            return []

        if api_keys and api_keys.get("ANTHROPIC_API_KEY"):
            return await self._classify_with_claude(tools, api_keys)
        return self._classify_with_keywords(tools)

    async def _classify_with_claude(self, tools: list[dict], api_keys: dict) -> list[str]:
        """Claude classifie tous les tools en une seule requête."""
        import anthropic, json as _json

        VALID = {
            "ingestion", "structuration", "enrichissement", "raisonnement",
            "validation", "generation", "nlp", "web_search", "web_scrape",
            "file_read", "file_write", "storage",
        }

        tools_summary = "\n".join(
            f"- {t['name']}: {t['description'][:120]}" for t in tools
        )

        prompt = f"""Tu es un classificateur de capacités MCP. Voici les outils d'un serveur MCP :

{tools_summary}

Classe ce serveur dans les capacités pipeline qu'il couvre parmi cette liste EXACTE :
ingestion, structuration, enrichissement, raisonnement, validation, generation, nlp, web_search, web_scrape, file_read, file_write, storage

Règles :
- Choisis UNIQUEMENT les capacités réellement couvertes par les outils listés
- Ne surclassifie pas : si le serveur fait de la recherche web → web_search, pas raisonnement
- Un serveur de fichiers → file_read et/ou file_write, pas generation

Réponds en JSON : {{"capabilities": ["cap1", "cap2"]}}"""

        client = anthropic.Anthropic(api_key=api_keys["ANTHROPIC_API_KEY"])
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",   # haiku : rapide + pas cher pour cette tâche
            max_tokens=256,
            system="Tu es un classificateur précis. Réponds uniquement en JSON strict.",
            messages=[{"role": "user", "content": prompt}],
        )

        text = msg.content[0].text.strip()
        # Extraire le JSON même si enveloppé dans ```
        if "```" in text:
            text = text.split("```")[1].lstrip("json").strip()

        result = _json.loads(text)
        caps = [c for c in result.get("capabilities", []) if c in VALID]
        logger.info("Claude classified %s → %s", self.server_info.get("name"), caps)
        return sorted(caps)

    def _classify_with_keywords(self, tools: list[dict]) -> list[str]:
        """Fallback : keyword matching avec scoring par tool.

        - Tokenise le nom (snake_case + camelCase → mots)
        - Pour chaque tool : compte les keywords matchés par catégorie
        - Retient la catégorie avec le meilleur score (évite faux positif 1 mot)
        - Seuil minimum : 2 keywords OU 1 keyword dans le nom tokenisé
        """
        import re
        from .discovery import CAPABILITY_KEYWORDS

        def tokenize(text: str) -> str:
            t = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
            return t.replace("_", " ").replace("-", " ").lower()

        found: set[str] = set()
        for tool in tools:
            name_raw = tool["name"].lower()          # original : read_file, web_search
            name_tok = tokenize(tool["name"])         # tokenisé : read file, web search
            desc     = tool["description"].lower()

            scores: dict[str, int] = {}
            for cap_name, keywords in CAPABILITY_KEYWORDS.items():
                score = 0
                for kw in keywords:
                    kw_tok     = kw.replace("_", " ")
                    pat_raw    = rf"\b{re.escape(kw)}\b"
                    pat_tok    = rf"\b{re.escape(kw_tok)}\b"
                    # x4 : keyword exact dans le nom brut (ex: "read_file" dans "read_file")
                    if re.search(pat_raw, name_raw):
                        score += 4
                    # x3 : keyword tokenisé dans le nom tokenisé
                    elif re.search(pat_tok, name_tok):
                        score += 3
                    # x1 : keyword dans la description
                    elif re.search(pat_tok, desc) or re.search(pat_raw, desc):
                        score += 1
                if score > 0:
                    scores[cap_name] = score

            if scores:
                best_cap = max(scores, key=lambda c: scores[c])
                found.add(best_cap)

        return sorted(found)

    async def probe(self) -> bool:
        """
        Vérifie que le serveur répond.
        initialize() déjà appelé dans le context manager —
        si on arrive ici la connexion est établie.
        """
        try:
            await self._session.list_tools()
            return True
        except Exception as e:
            logger.warning("Probe failed: %s", e)
            return False

    # ── Exécution ──────────────────────────────────────────────────────────────

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Appelle un outil et retourne le résultat (structuré si dispo, texte sinon)."""
        result = await self._session.call_tool(tool_name, arguments)

        if result.isError:
            raise RuntimeError(f"MCP tool '{tool_name}' error: {result.content}")

        if getattr(result, "structuredContent", None):
            return result.structuredContent

        texts = [c.text for c in result.content if hasattr(c, "text")]
        return "\n".join(texts) if texts else result.content


# ── Helpers synchrones (pour code non-async comme Flask) ───────────────────────

def _run(coro):
    import asyncio
    return asyncio.run(coro)


def get_stdio_tools_sync(command: str, args: list[str]) -> list[dict[str, Any]]:
    """Découverte tools stdio — synchrone."""
    async def _():
        async with MCPClient.stdio(command, args) as c:
            return await c.list_tools_as_dict()
    return _run(_())


def get_sse_tools_sync(url: str, headers: dict | None = None) -> list[dict[str, Any]]:
    """Découverte tools SSE — synchrone."""
    async def _():
        async with MCPClient.sse(url, headers) as c:
            return await c.list_tools_as_dict()
    return _run(_())


def probe_stdio_sync(command: str, args: list[str]) -> bool:
    """Probe stdio — synchrone."""
    async def _():
        try:
            async with MCPClient.stdio(command, args) as c:
                return await c.probe()
        except Exception as e:
            logger.warning("Stdio probe failed for %s: %s", command, e)
            return False
    return _run(_())


def probe_sse_sync(url: str, headers: dict | None = None) -> bool:
    """Probe SSE — synchrone."""
    async def _():
        try:
            async with MCPClient.sse(url, headers) as c:
                return await c.probe()
        except Exception as e:
            logger.warning("SSE probe failed for %s: %s", url, e)
            return False
    return _run(_())
