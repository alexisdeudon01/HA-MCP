"""
MCP Discovery Loop v2 — découverte itérative avec schéma modulaire.

Flux par MCP :
  1. detect_transport()  → type + probe SDK officiel
  2. list_tools()        → outils réels via SDK
  3. detect_auth()       → plug_and_play + requires_auth  (APRÈS transport)
  4. classify_caps()     → capabilities pipeline
  5. INSERT DB           → mcp, transport, tool, capability (FK)
  6. ask Claude          → MCPs voisins → file d'attente
"""

import asyncio
import json
import logging
import sqlite3
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .mcp_detector import (
    detect_transport_remote, detect_transport_stdio,
    detect_auth, detect_executor,
    upsert_mcp, upsert_transport, upsert_tool, link_capability,
    AuthInfo, TransportInfo,
)

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parent.parent.parent / "database" / "tool_v2.db"

SEED_MCPS = [
    {"mcp_id": "duckduckgo",          "transport": "stdio",
     "command": "npx", "args": ["-y", "duckduckgo-mcp-server"]},
    {"mcp_id": "sequential-thinking", "transport": "stdio",
     "command": "npx", "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"]},
    {"mcp_id": "playwright",          "transport": "stdio",
     "command": "npx", "args": ["-y", "@playwright/mcp"]},
    {"mcp_id": "filesystem",          "transport": "stdio",
     "command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "/"]},
    {"mcp_id": "memory",              "transport": "stdio",
     "command": "npx", "args": ["-y", "@modelcontextprotocol/server-memory"]},
    {"mcp_id": "fetch",               "transport": "stdio",
     "command": "npx", "args": ["-y", "@modelcontextprotocol/server-fetch"]},
    {"mcp_id": "puppeteer",           "transport": "stdio",
     "command": "npx", "args": ["-y", "@modelcontextprotocol/server-puppeteer"]},
    {"mcp_id": "everything",          "transport": "stdio",
     "command": "npx", "args": ["-y", "@modelcontextprotocol/server-everything"]},
    {"mcp_id": "blockscout",          "transport": "sse",
     "url": "https://mcp.blockscout.com/mcp"},
    {"mcp_id": "mermaid-chart",       "transport": "sse",
     "url": "https://chatgpt.mermaid.ai/anthropic/mcp"},
    {"mcp_id": "dice",                "transport": "sse",
     "url": "https://mcp.dice.com/mcp"},
]


class MCPDiscoveryLoop:

    def __init__(self, api_keys: dict | None = None, max_depth: int = 2,
                 db_path: Path | None = None):
        self._api_keys  = api_keys or {}
        self._max_depth = max_depth
        self._db_path   = db_path or DB_PATH
        self._visited:  set[str]   = set()
        self._queue:    deque      = deque()
        self._stats = {"probed": 0, "accessible": 0, "plug_and_play": 0, "saved": 0}

    # ── Point d'entrée ─────────────────────────────────────────────────────────

    async def run(self, seeds: list[dict] | None = None) -> dict[str, dict]:
        self._init_db()
        for seed in (seeds or SEED_MCPS):
            self._queue.append((seed, "seed", 0))

        results: dict[str, dict] = {}

        while self._queue:
            mcp_def, source, depth = self._queue.popleft()
            mcp_id = mcp_def.get("mcp_id", "")
            if mcp_id in self._visited:
                continue
            self._visited.add(mcp_id)

            logger.info("━━ [depth=%d] %s  (from: %s)", depth, mcp_id, source)
            result = await self._process(mcp_def, source)
            if result:
                results[mcp_id] = result
                self._stats["saved"] += 1

                # Chercher des voisins uniquement si accessible + sans auth
                if result.get("plug_and_play") and depth < self._max_depth:
                    neighbours = await self._ask_neighbours(result)
                    for n in neighbours:
                        nid = n.get("mcp_id", "")
                        if nid and nid not in self._visited:
                            logger.info("  → nouveau voisin : %s", nid)
                            self._queue.append((n, mcp_id, depth + 1))

        logger.info("━━ Fin : %s", self._stats)
        return {k: v for k, v in results.items() if v.get("plug_and_play")}

    # ── Traitement d'un MCP ────────────────────────────────────────────────────

    async def _process(self, mcp_def: dict, source: str) -> dict | None:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        from mcp.client.streamable_http import streamable_http_client
        from mcp.client.sse import sse_client
        from .mcp_client import MCPClient

        mcp_id    = mcp_def["mcp_id"]
        transport_hint = mcp_def.get("transport", "stdio")
        self._stats["probed"] += 1

        # ── Étape 1 : détection transport via SDK ──────────────────────────────
        if transport_hint in ("sse", "streamable-http"):
            t_info = await detect_transport_remote(mcp_def["url"])
        else:
            t_info = await detect_transport_stdio(
                mcp_id, mcp_def["command"], mcp_def["args"]
            )

        if not t_info.probe_ok:
            logger.warning("  ✗ inaccessible : %s", t_info.probe_error)
            return None

        self._stats["accessible"] += 1

        # ── Étape 2 : list_tools() via SDK ─────────────────────────────────────
        try:
            if t_info.type == "streamable-http":
                ctx = MCPClient.sse(t_info.url)
            elif t_info.type == "sse":
                ctx = MCPClient.sse(t_info.url)
            else:
                ctx = MCPClient.stdio(t_info.command, t_info.args)

            async with ctx as client:
                server_name = client.server_info.get("name", mcp_id)
                server_ver  = client.server_info.get("version", "1.0.0")
                tools_raw   = await client.list_tools_as_dict()
                caps        = await client.classify_capabilities(self._api_keys)
        except Exception as e:
            logger.warning("  ✗ SDK session failed : %s", e)
            return None

        # ── Étape 3 : detect_auth() APRÈS transport ────────────────────────────
        auth = detect_auth(server_name, " ".join(t.get("description","") for t in tools_raw), tools_raw)

        logger.info("  %s | transport=%s | plug_and_play=%s | tools=%d | caps=%s",
                    server_name, t_info.type, auth.plug_and_play, len(tools_raw), caps)

        if auth.requires_auth:
            logger.info("  ⚠ auth requise (%s) — conservé en DB mais exclu du pipeline",
                        auth.auth_type)

        if auth.plug_and_play:
            self._stats["plug_and_play"] += 1

        # ── Étape 4 : INSERT DB modulaire ──────────────────────────────────────
        # Normaliser source : "seed" et mcp_id référents → "discovered"
        db_source = source if source in ("local","anthropic_registry","community") else "discovered"

        self._save_to_db(
            mcp_id=mcp_id,
            name=server_name,
            version=server_ver,
            description=tools_raw[0].get("description","")[:200] if tools_raw else "",
            auth=auth,
            transport=t_info,
            tools=tools_raw,
            capabilities=caps,
            source=db_source,
        )

        return {
            "mcp_id":       mcp_id,
            "name":         server_name,
            "transport":    t_info.type,
            "plug_and_play":auth.plug_and_play,
            "requires_auth":auth.requires_auth,
            "tools":        tools_raw,
            "capabilities": caps,
        }

    # ── Sauvegarde DB ──────────────────────────────────────────────────────────

    def _save_to_db(self, mcp_id, name, version, description, auth: AuthInfo,
                    transport: TransportInfo, tools: list[dict],
                    capabilities: list[str], source: str) -> None:
        conn = sqlite3.connect(self._db_path)
        cur  = conn.cursor()
        try:
            # mcp
            upsert_mcp(cur, mcp_id, name, version, description, auth, source)
            # transport
            upsert_transport(cur, mcp_id, transport)
            # tools + capabilities
            for tool in tools:
                tool_id = upsert_tool(cur, mcp_id, tool["name"], tool.get("description",""))
                # Associer les capabilities à ce tool
                for cap in capabilities:
                    link_capability(cur, mcp_id, tool_id, cap)
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error("DB save failed for %s: %s", mcp_id, e)
        finally:
            conn.close()

    # ── Voisins ────────────────────────────────────────────────────────────────

    async def _ask_neighbours(self, mcp_result: dict) -> list[dict]:
        """Demande à Claude les MCPs voisins sans auth."""
        if not self._api_keys.get("ANTHROPIC_API_KEY"):
            return self._heuristic_neighbours(mcp_result["mcp_id"])

        import anthropic
        tools_summary = "\n".join(
            f"  - {t['name']}: {t.get('description','')[:100]}"
            for t in mcp_result["tools"][:15]
        )
        prompt = f"""Serveur MCP "{mcp_result['name']}" (id: {mcp_result['mcp_id']}).
Outils : \n{tools_summary}

Connais-tu des MCPs complémentaires SANS authentification (plug & play) ?
Pour chaque MCP suggéré :
  mcp_id, transport (stdio|sse), command+args (si stdio) ou url (si sse), requires_auth: false

Ne suggère que des packages npm ou serveurs HTTP réellement existants.
JSON : {{"mcps": [...]}}"""

        try:
            client = anthropic.Anthropic(api_key=self._api_keys["ANTHROPIC_API_KEY"])
            msg = client.messages.create(
                model="claude-haiku-4-5-20251001", max_tokens=512,
                system="Expert MCP. JSON strict uniquement. Packages npm réels.",
                messages=[{"role": "user", "content": prompt}],
            )
            text = msg.content[0].text.strip()
            if "```" in text:
                text = text.split("```")[1].lstrip("json").strip()
            data = json.loads(text)
            return [m for m in data.get("mcps", []) if not m.get("requires_auth", True)]
        except Exception as e:
            logger.debug("Claude neighbours failed: %s", e)
            return self._heuristic_neighbours(mcp_result["mcp_id"])

    def _heuristic_neighbours(self, mcp_id: str) -> list[dict]:
        MAP = {
            "playwright": [{"mcp_id": "puppeteer", "transport": "stdio",
                            "command": "npx", "args": ["-y", "@modelcontextprotocol/server-puppeteer"]}],
            "filesystem": [{"mcp_id": "memory",    "transport": "stdio",
                            "command": "npx", "args": ["-y", "@modelcontextprotocol/server-memory"]}],
            "duckduckgo": [{"mcp_id": "fetch",      "transport": "stdio",
                            "command": "npx", "args": ["-y", "@modelcontextprotocol/server-fetch"]}],
        }
        return MAP.get(mcp_id, [])

    # ── Init DB ────────────────────────────────────────────────────────────────

    def _init_db(self) -> None:
        schema = Path(__file__).resolve().parent.parent.parent / "database" / "schema_v2.sql"
        if not self._db_path.exists():
            conn = sqlite3.connect(self._db_path)
            conn.executescript(schema.read_text())
            conn.commit()
            conn.close()
            logger.info("DB v2 initialisée : %s", self._db_path)


# ── Runner synchrone ───────────────────────────────────────────────────────────

def run_discovery_sync(api_keys: dict | None = None, seeds: list | None = None,
                       max_depth: int = 2) -> dict:
    loop = MCPDiscoveryLoop(api_keys=api_keys, max_depth=max_depth)
    return asyncio.run(loop.run(seeds))
