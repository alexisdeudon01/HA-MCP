"""
MCP Enricher — remplit tool_parameter et génère les prompt_template.

Deux passes :
  1. fill_parameters()  : parse les inputSchema réels de tools/list → tool_parameter
  2. generate_prompts() : Claude génère system_prompt + user_template pour chaque tool
                          Fallback automatique si pas de clé API.
"""

import json
import logging
import os
import re
import sqlite3
from pathlib import Path
from typing import Any
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parent.parent.parent / "database" / "tool_v2.db"

VALID_TYPES = {"string", "integer", "number", "boolean", "array", "object"}

STDIO_COMMANDS = {
    "duckduckgo":          {"command": "npx", "args": ["-y", "duckduckgo-mcp-server"]},
    "sequential-thinking": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"]},
    "playwright":          {"command": "npx", "args": ["-y", "@playwright/mcp"]},
    "filesystem":          {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "/"]},
    "memory":              {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-memory"]},
    "fetch":               {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-fetch"]},
    "puppeteer":           {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-puppeteer"]},
    "everything":          {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-everything"]},
}

SSE_URLS = {
    "blockscout":   "https://mcp.blockscout.com/mcp",
    "mermaid-chart":"https://chatgpt.mermaid.ai/anthropic/mcp",
    "dice":         "https://mcp.dice.com/mcp",
}


# ══════════════════════════════════════════════════════════════════════════════
# PASSE 1 — tool_parameter depuis inputSchema réels
# ══════════════════════════════════════════════════════════════════════════════

async def fill_parameters(db_path: Path = DB_PATH) -> dict[str, int]:
    """
    Connecte chaque MCP connu, récupère list_tools(),
    et insère les paramètres dans tool_parameter.
    Retourne {mcp_id: nb_params_insérés}.
    """
    from .mcp_client import MCPClient

    conn  = sqlite3.connect(db_path)
    stats = {}

    # MCPs stdio
    for mcp_id, cfg in STDIO_COMMANDS.items():
        try:
            async with MCPClient.stdio(cfg["command"], cfg["args"]) as client:
                tools = await client.list_tools()
                n = _insert_params(conn, mcp_id, tools)
                stats[mcp_id] = n
                logger.info("  %s : %d params insérés", mcp_id, n)
        except Exception as e:
            logger.warning("  %s : échec params (%s)", mcp_id, e)

    # MCPs SSE
    for mcp_id, url in SSE_URLS.items():
        try:
            async with MCPClient.sse(url) as client:
                tools = await client.list_tools()
                n = _insert_params(conn, mcp_id, tools)
                stats[mcp_id] = n
                logger.info("  %s : %d params insérés", mcp_id, n)
        except Exception as e:
            logger.warning("  %s : échec params (%s)", mcp_id, e)

    conn.commit()
    conn.close()
    return stats


def _insert_params(conn: sqlite3.Connection, mcp_id: str, tools) -> int:
    """Parse inputSchema de chaque tool et insère dans tool_parameter."""
    cur   = conn.cursor()
    total = 0

    for tool in tools:
        cur.execute("SELECT id FROM tool WHERE mcp_id=? AND name=?", (mcp_id, tool.name))
        row = cur.fetchone()
        if not row:
            continue
        tool_id = row[0]

        schema     = tool.inputSchema
        props      = {}
        required   = []

        if hasattr(schema, "model_dump"):
            d        = schema.model_dump()
            props    = d.get("properties") or {}
            required = d.get("required") or []
        elif isinstance(schema, dict):
            props    = schema.get("properties") or {}
            required = schema.get("required") or []

        for pos, (param_name, param_def) in enumerate(props.items()):
            if not isinstance(param_def, dict):
                continue

            raw_type = param_def.get("type", "string")
            p_type   = raw_type if raw_type in VALID_TYPES else "string"

            cur.execute("""
                INSERT OR IGNORE INTO tool_parameter
                  (tool_id, name, type, description, required,
                   default_value, enum_values, min_value, max_value, max_length, position)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (
                tool_id,
                param_name,
                p_type,
                param_def.get("description", "")[:300],
                1 if param_name in required else 0,
                json.dumps(param_def["default"]) if "default" in param_def else None,
                json.dumps(param_def["enum"])    if "enum"    in param_def else None,
                param_def.get("minimum"),
                param_def.get("maximum"),
                param_def.get("maxLength"),
                pos,
            ))
            total += cur.rowcount

    return total


# ══════════════════════════════════════════════════════════════════════════════
# PASSE 2 — prompt_template via Claude (ou fallback)
# ══════════════════════════════════════════════════════════════════════════════

def generate_prompts(api_keys: dict, db_path: Path = DB_PATH) -> dict[str, int]:
    """
    Génère un prompt_template pour chaque tool sans template existant.
    Utilise Claude si clé dispo, sinon fallback générique.
    Retourne {mcp_id: nb_templates_générés}.
    """
    conn  = sqlite3.connect(db_path)
    cur   = conn.cursor()
    stats: dict[str, int] = {}

    # Récupérer tous les tools sans template
    cur.execute("""
        SELECT t.id, t.mcp_id, t.name, t.description
        FROM tool t
        LEFT JOIN prompt_template pt ON pt.tool_id = t.id
        WHERE pt.id IS NULL
        ORDER BY t.mcp_id, t.name
    """)
    tools_without_prompt = cur.fetchall()
    logger.info("%d tools sans prompt_template", len(tools_without_prompt))

    has_claude = bool(api_keys.get("ANTHROPIC_API_KEY"))
    batch      = []

    for tool_id, mcp_id, tool_name, tool_desc in tools_without_prompt:
        # Récupérer les paramètres de ce tool
        cur.execute("""
            SELECT name, type, description, required, default_value, enum_values
            FROM tool_parameter WHERE tool_id=? ORDER BY position
        """, (tool_id,))
        params = cur.fetchall()

        if has_claude:
            template = _generate_with_claude(api_keys, mcp_id, tool_name, tool_desc, params)
        else:
            template = _generate_fallback(mcp_id, tool_name, tool_desc, params)

        cur.execute("""
            INSERT OR IGNORE INTO prompt_template
              (tool_id, system_prompt, user_template, variables, example_call, generated_by)
            VALUES (?,?,?,?,?,?)
        """, (
            tool_id,
            template["system_prompt"],
            template["user_template"],
            json.dumps(template["variables"]),
            json.dumps(template.get("example_call")),
            "claude" if has_claude else "fallback",
        ))
        stats[mcp_id] = stats.get(mcp_id, 0) + 1

    conn.commit()
    conn.close()
    return stats


def _generate_with_claude(api_keys: dict, mcp_id: str, tool_name: str,
                           tool_desc: str, params: list) -> dict:
    """Claude génère system + user template pour un tool."""
    import anthropic

    params_str = "\n".join(
        f"  - {p[0]} ({p[1]}, {'requis' if p[3] else 'optionnel'}): {p[2][:100]}"
        + (f" [enum: {p[5]}]" if p[5] else "")
        + (f" [default: {p[4]}]"  if p[4] else "")
        for p in params
    )

    prompt = f"""Tu génères un prompt_template pour un outil MCP.

Outil    : {tool_name}
MCP      : {mcp_id}
Description : {tool_desc[:400]}

Paramètres :
{params_str or '  (aucun paramètre)'}

Génère :
1. system_prompt : 2-3 phrases expliquant CE QUE fait cet outil, QUAND l'utiliser, et ses limites. Concis, orienté LLM.
2. user_template : template d'appel avec {{{{variable}}}} pour chaque paramètre requis. Format naturel.
3. variables : liste des noms de variables du template.
4. example_call : un exemple JSON concret des arguments à passer.

Réponds en JSON strict :
{{
  "system_prompt": "...",
  "user_template": "...",
  "variables": ["var1", "var2"],
  "example_call": {{...}}
}}"""

    try:
        client = anthropic.Anthropic(api_key=api_keys["ANTHROPIC_API_KEY"])
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            system="Tu génères des prompt templates pour outils MCP. JSON strict uniquement.",
            messages=[{"role": "user", "content": prompt}],
        )
        text = msg.content[0].text.strip()
        if "```" in text:
            text = text.split("```")[1].lstrip("json").strip()
        return json.loads(text)
    except Exception as e:
        logger.warning("Claude prompt gen failed for %s/%s: %s", mcp_id, tool_name, e)
        return _generate_fallback(mcp_id, tool_name, tool_desc, params)


def _generate_fallback(mcp_id: str, tool_name: str,
                        tool_desc: str, params: list) -> dict:
    """Template générique sans LLM."""
    required = [p[0] for p in params if p[3]]
    optional = [p[0] for p in params if not p[3]]
    variables = required + optional

    parts = []
    for p in params:
        name, ptype, desc, req, default, enum = p
        marker = "{{" + name + "}}"
        parts.append(f"{name}: {marker}")

    user_template = (
        f"Utilise {tool_name}" +
        (f" avec {', '.join(parts)}" if parts else "") + "."
    )

    example_call = {}
    for p in params:
        name, ptype, *_ = p
        example_call[name] = {
            "string":  f"exemple_{name}",
            "integer": 10,
            "number":  1.0,
            "boolean": True,
            "array":   [],
            "object":  {},
        }.get(ptype, f"valeur_{name}")

    return {
        "system_prompt": f"Outil {tool_name} du serveur MCP {mcp_id}. "
                         f"{tool_desc[:200]}",
        "user_template": user_template,
        "variables":     variables,
        "example_call":  example_call if example_call else None,
        "generated_by":  "fallback",
    }


# ══════════════════════════════════════════════════════════════════════════════
# Runner
# ══════════════════════════════════════════════════════════════════════════════

async def enrich_all(api_keys: dict | None = None, db_path: Path = DB_PATH) -> None:
    api_keys = api_keys or {}
    logger.info("=== Passe 1 : tool_parameter ===")
    params_stats = await fill_parameters(db_path)
    logger.info("Paramètres : %s", params_stats)

    logger.info("=== Passe 2 : prompt_template ===")
    prompt_stats = generate_prompts(api_keys, db_path)
    logger.info("Templates  : %s", prompt_stats)

    # Rapport final
    conn = sqlite3.connect(db_path)
    cur  = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM tool_parameter")
    nb_params = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM prompt_template")
    nb_prompts = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM tool")
    nb_tools = cur.fetchone()[0]
    conn.close()

    logger.info("━━ Enrichissement terminé")
    logger.info("   %d tools | %d paramètres | %d templates", nb_tools, nb_params, nb_prompts)
