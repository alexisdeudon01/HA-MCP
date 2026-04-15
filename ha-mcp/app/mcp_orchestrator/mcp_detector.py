"""
MCP Detector — détection modulaire du transport, de l'exécuteur et de l'auth.

Flux :
  1. detect_transport()  → type (streamable-http | sse | stdio) via SDK officiel
  2. detect_auth()       → plug_and_play + requires_auth + auth_type
  3. detect_executor()   → npx | uvx selon les indices Python/Node

Basé sur la logique is_plug_and_play() / determine_executor() du registre MCP.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# Mots interdits → auth requise (is_plug_and_play logic)
AUTH_FORBIDDEN = frozenset([
    "key", "token", "secret", "auth", "password",
    "api-key", "credentials", "oauth", "bearer",
    "authenticate", "sign_in", "login",
])

# Indices Python → executor = uvx
PYTHON_INDICATORS = frozenset(["python", "py-", "uvx", "pip", ".py", "uv run"])


@dataclass
class TransportInfo:
    type:       str             # streamable-http | sse | stdio
    executor:   str | None      # npx | uvx | node | python | None
    command:    str | None      # commande stdio
    args:       list            # args stdio
    url:        str | None      # URL HTTP
    probe_ok:   bool  = False
    probe_error:str | None = None
    probe_at:   str   = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class AuthInfo:
    plug_and_play:  bool        # True = aucune clé requise
    requires_auth:  bool
    auth_type:      str         # none | api_key | oauth | bearer_token
    auth_key_name:  str | None  # ex: ANTHROPIC_API_KEY


# ── Transport ──────────────────────────────────────────────────────────────────

async def detect_transport_remote(url: str) -> TransportInfo:
    """
    Détecte le transport d'un serveur distant via POST JSON-RPC (SDK officiel).
    Ordre : streamable-http → SSE.
    """
    import httpx
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client
    from mcp.client.sse import sse_client

    # 1. Probe HTTP pour détecter le type
    transport_type = "sse"  # défaut
    try:
        async with httpx.AsyncClient(timeout=6) as c:
            r = await c.post(
                url,
                json={"jsonrpc": "2.0", "id": 0, "method": "initialize",
                      "params": {"protocolVersion": "2024-11-05",
                                 "capabilities": {},
                                 "clientInfo": {"name": "probe", "version": "1.0"}}},
                headers={"Content-Type": "application/json",
                         "Accept": "application/json, text/event-stream"},
            )
            if r.status_code in (200, 202):
                transport_type = "streamable-http"
    except Exception as e:
        logger.debug("HTTP probe failed for %s: %s", url, e)

    # 2. Connexion SDK officielle pour valider
    try:
        if transport_type == "streamable-http":
            async with streamable_http_client(url) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
        else:
            async with sse_client(url) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()

        return TransportInfo(
            type=transport_type, executor=None, command=None, args=[], url=url,
            probe_ok=True,
        )
    except Exception as e:
        return TransportInfo(
            type=transport_type, executor=None, command=None, args=[], url=url,
            probe_ok=False, probe_error=str(e)[:200],
        )


async def detect_transport_stdio(mcp_id: str, command: str, args: list[str]) -> TransportInfo:
    """
    Valide un transport stdio via le SDK officiel (initialize + list_tools).
    """
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    executor = detect_executor({"package_name": " ".join(args), "description": command})

    try:
        params = StdioServerParameters(command=command, args=args)
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

        return TransportInfo(
            type="stdio", executor=executor, command=command, args=args, url=None,
            probe_ok=True,
        )
    except Exception as e:
        return TransportInfo(
            type="stdio", executor=executor, command=command, args=args, url=None,
            probe_ok=False, probe_error=str(e)[:200],
        )


# ── Auth ───────────────────────────────────────────────────────────────────────

def detect_auth(name: str, description: str, tools: list[dict]) -> AuthInfo:
    """
    Détecte si le MCP requiert une authentification.
    Applique la logique is_plug_and_play() sur nom + description + noms des outils.
    Appelé APRÈS la détection du transport.
    """
    # 1. Analyse textuelle (is_plug_and_play)
    combined = f"{name} {description}".lower()
    text_needs_auth = any(
        re.search(rf"\b{re.escape(w)}\b", combined)
        for w in AUTH_FORBIDDEN
    )

    # 2. Analyse des noms d'outils (authenticate, sign_in, etc.)
    tool_names = " ".join(t.get("name", "").lower() for t in tools)
    tool_needs_auth = any(
        re.search(rf"\b{re.escape(w)}\b", tool_names)
        for w in {"authenticate", "sign_in", "login", "complete_authentication"}
    )

    requires_auth = text_needs_auth or tool_needs_auth
    plug_and_play = not requires_auth

    # 3. Inférence du type d'auth
    auth_type = "none"
    auth_key  = None
    if requires_auth:
        lc = combined
        if "oauth" in lc:
            auth_type = "oauth"
        elif "bearer" in lc:
            auth_type = "bearer_token"
        elif any(w in lc for w in ["api_key", "api-key", "api key", "apikey"]):
            auth_type = "api_key"
        else:
            auth_type = "api_key"   # défaut pour auth requise
        # Tente d'extraire le nom de la variable de config
        m = re.search(r"\b([A-Z][A-Z0-9_]{3,}_(?:KEY|TOKEN|SECRET|API_KEY))\b", description)
        auth_key = m.group(1) if m else None

    logger.debug("Auth detect: plug_and_play=%s, auth_type=%s", plug_and_play, auth_type)
    return AuthInfo(
        plug_and_play=plug_and_play,
        requires_auth=requires_auth,
        auth_type=auth_type,
        auth_key_name=auth_key,
    )


# ── Executor ───────────────────────────────────────────────────────────────────

def detect_executor(server_data: dict) -> str:
    """
    Détermine le moteur d'exécution : uvx (Python) ou npx (Node.js).
    Logique determine_executor() du registre MCP.
    """
    pkg  = server_data.get("package_name", "").lower()
    desc = server_data.get("description", "").lower()
    if any(k in pkg or k in desc for k in PYTHON_INDICATORS):
        return "uvx"
    return "npx"


# ── DB helpers ─────────────────────────────────────────────────────────────────

def upsert_mcp(cur, mcp_id: str, name: str, version: str, description: str,
               auth: AuthInfo, source: str = "discovered",
               registry_category: str | None = None,
               discovered_from: str | None = None,
               homepage_url: str | None = None) -> None:
    cur.execute("""
        INSERT INTO mcp
          (mcp_id, name, version, description, plug_and_play, requires_auth,
           auth_type, auth_key_name, source, registry_category,
           discovered_from, discovered_at, homepage_url)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(mcp_id) DO UPDATE SET
          name=excluded.name, version=excluded.version,
          plug_and_play=excluded.plug_and_play,
          requires_auth=excluded.requires_auth,
          auth_type=excluded.auth_type,
          auth_key_name=excluded.auth_key_name
    """, (
        mcp_id, name, version, description,
        int(auth.plug_and_play), int(auth.requires_auth),
        auth.auth_type, auth.auth_key_name,
        source, registry_category, discovered_from,
        datetime.now(timezone.utc).isoformat(),
        homepage_url,
    ))


def upsert_transport(cur, mcp_id: str, t: TransportInfo) -> None:
    cur.execute("""
        INSERT INTO transport
          (mcp_id, type, executor, command, args_json, url,
           last_probe_at, last_probe_ok, last_probe_error)
        VALUES (?,?,?,?,?,?,?,?,?)
        ON CONFLICT(mcp_id, type) DO UPDATE SET
          executor=excluded.executor, command=excluded.command,
          args_json=excluded.args_json, url=excluded.url,
          last_probe_at=excluded.last_probe_at,
          last_probe_ok=excluded.last_probe_ok,
          last_probe_error=excluded.last_probe_error
    """, (
        mcp_id, t.type, t.executor, t.command,
        json.dumps(t.args), t.url,
        t.probe_at, int(t.probe_ok), t.probe_error,
    ))


def upsert_tool(cur, mcp_id: str, name: str, description: str,
                timeout_ms: int = 10000) -> int:
    cur.execute("""
        INSERT INTO tool (mcp_id, name, description, timeout_ms)
        VALUES (?,?,?,?)
        ON CONFLICT(mcp_id, name) DO UPDATE SET
          description=excluded.description, timeout_ms=excluded.timeout_ms
        RETURNING id
    """, (mcp_id, name, description, timeout_ms))
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute("SELECT id FROM tool WHERE mcp_id=? AND name=?", (mcp_id, name))
    return cur.fetchone()[0]


def link_capability(cur, mcp_id: str, tool_id: int, cap_name: str) -> None:
    """Lie un MCP et un outil à une capability (crée si inexistante)."""
    cur.execute("SELECT id FROM capability WHERE name=?", (cap_name,))
    row = cur.fetchone()
    if not row:
        cur.execute("INSERT OR IGNORE INTO capability (name) VALUES (?)", (cap_name,))
        cur.execute("SELECT id FROM capability WHERE name=?", (cap_name,))
        row = cur.fetchone()
    cap_id = row[0]

    cur.execute("INSERT OR IGNORE INTO mcp_capability  (mcp_id,  cap_id) VALUES (?,?)", (mcp_id,  cap_id))
    cur.execute("INSERT OR IGNORE INTO tool_capability (tool_id, cap_id) VALUES (?,?)", (tool_id, cap_id))
