"""
MCP Discovery — utilise le SDK officiel pour découvrir les outils réels.

Au lieu de recevoir une liste hardcodée, Discovery peut maintenant :
1. Appeler tools/list sur chaque serveur via ClientSession
2. Classifier les capabilities depuis les vrais schemas retournés
"""

import logging
from pathlib import Path
from typing import Any
import json

from .capability import Capability, CapabilityCategory, CapabilityMap, MCPInfo

logger = logging.getLogger(__name__)

# Mots-clés pour classifier capability depuis nom/description d'un tool
CAPABILITY_KEYWORDS: dict[str, list[str]] = {
    # Ordre : du plus spécifique au plus générique
    "web_search":     ["web_search", "search_web", "duckduckgo", "search_jobs", "search_docs", "search_documentation"],
    "web_scrape":     ["browser_navigate", "browser_click", "browser_snapshot", "browser_screenshot", "scrape", "browser"],
    "file_read":      ["read_file", "read_text_file", "read_media", "list_directory", "directory_tree", "get_file_info"],
    "file_write":     ["write_file", "edit_file", "create_directory", "move_file"],
    "storage":        ["storage", "bucket", "database", "notion", "save_dive", "store", "persist"],
    "nlp":            ["nlp", "sentiment", "summarize", "ner_extraction", "extract_entities", "classify_text"],
    "validation":     ["validate", "verify", "schema", "conform", "lint"],
    "ingestion":      ["read", "file", "parse", "pdf", "extract", "download", "ingest"],
    "structuration":  ["segment", "entity", "normalize", "structure", "transform", "split"],
    "raisonnement":   ["reason", "reasoning", "thinking", "analyze", "evaluate", "sequential", "problem_solving", "chat_completion", "compare", "sequential_thinking"],
    "generation":     ["generate", "create", "produce", "render", "deploy", "apply_migration", "write"],
    "enrichissement": ["search", "lookup", "web", "enrich", "fetch", "get", "list"],
}


class MCPDiscovery:
    """
    Découverte et classification des MCPs.

    Deux modes :
    - discover(mcp_tool_lists) : reçoit les tools déjà récupérés (mode actuel du pipeline)
    - discover_from_server()   : appelle tools/list via le SDK (nouvelle capacité)
    """

    def __init__(self, config_path: Path | None = None):
        if config_path and config_path.exists():
            with open(config_path) as f:
                data = json.load(f)
                # Merge avec nos keywords par défaut
                CAPABILITY_KEYWORDS.update(data.get("capability_keywords", {}))

    # ── Mode 1 : à partir d'une liste de tools déjà connue ────────────────────

    def discover(self, mcp_tool_lists: dict[str, list[dict[str, Any]]]) -> CapabilityMap:
        """Classifie les MCPs depuis une liste tools déjà récupérée."""
        cap_map = CapabilityMap()
        for mcp_id, tools in mcp_tool_lists.items():
            mcp_info = self._build_mcp_info(mcp_id, tools)
            cap_map.register_mcp(mcp_info)
            logger.info("MCP '%s': status=%s, capabilities=%d", mcp_id, mcp_info.status, len(mcp_info.capabilities))
        return cap_map

    # ── Mode 2 : découverte réelle via SDK ────────────────────────────────────

    async def discover_from_stdio(self, mcp_id: str, command: str, args: list[str]) -> MCPInfo:
        """Appelle tools/list sur un serveur stdio et classifie le résultat."""
        from .mcp_client import MCPClient
        async with MCPClient.stdio(command, args) as client:
            tools = await client.list_tools_as_dict()
            logger.info("Discovered %d tools from %s (stdio)", len(tools), mcp_id)
            return self._build_mcp_info(mcp_id, tools)

    async def discover_from_http(self, mcp_id: str, url: str, headers: dict | None = None) -> MCPInfo:
        """Appelle tools/list sur un serveur HTTP distant et classifie le résultat."""
        from .mcp_client import MCPClient
        async with MCPClient.http(url, headers) as client:
            tools = await client.list_tools_as_dict()
            logger.info("Discovered %d tools from %s (http)", len(tools), mcp_id)
            return self._build_mcp_info(mcp_id, tools)

    # ── Classification ────────────────────────────────────────────────────────

    def _build_mcp_info(self, mcp_id: str, tools: list[dict[str, Any]]) -> MCPInfo:
        requires_auth = self._check_requires_auth(tools)
        mcp = MCPInfo(
            mcp_id=mcp_id,
            name=mcp_id,
            tools=tools,
            requires_auth=requires_auth,
            exclusion_reason="requires_authentication" if requires_auth else None,
        )
        if not requires_auth:
            mcp.capabilities = self._classify_capabilities(mcp_id, tools)
        return mcp

    def _check_requires_auth(self, tools: list[dict[str, Any]]) -> bool:
        """Si un outil s'appelle 'authenticate' ou similaire → auth requise."""
        auth_indicators = {"authenticate", "auth", "login", "complete_authentication", "sign_in"}
        return any(
            any(ind in tool.get("name", "").lower() for ind in auth_indicators)
            for tool in tools
        )

    def _classify_capabilities(self, mcp_id: str, tools: list[dict[str, Any]]) -> list[Capability]:
        """Classifie chaque tool en capability via keyword matching."""
        capabilities = []
        for tool in tools:
            combined = f"{tool.get('name', '')} {tool.get('description', '')}".lower()
            for cap_name, keywords in CAPABILITY_KEYWORDS.items():
                if any(kw in combined for kw in keywords):
                    try:
                        category = CapabilityCategory(cap_name) if cap_name in CapabilityCategory._value2member_map_ else CapabilityCategory.ENRICHISSEMENT
                    except ValueError:
                        category = CapabilityCategory.ENRICHISSEMENT
                    capabilities.append(Capability(
                        name=f"{mcp_id}:{tool.get('name', '')}",
                        category=category,
                        mcp_id=mcp_id,
                        tool_name=tool.get("name", ""),
                        description=tool.get("description", ""),
                        parameters=tool.get("inputSchema", {}).get("properties", {}),
                    ))
                    break  # une seule capability par tool
        return capabilities
