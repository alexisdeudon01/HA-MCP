"""
MCP Manager — lifecycle dynamique des MCPs via SDK officiel.

Remplace l'ancien système basé sur pattern matching par :
- probe réel via ClientSession.initialize() + list_tools()
- tools/list pour alimenter la DB
- gestion stdio (local) et HTTP (distant)
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# Commandes de lancement pour les serveurs stdio connus
STDIO_COMMANDS: dict[str, dict[str, Any]] = {
    "duckduckgo":         {"command": "npx", "args": ["-y", "duckduckgo-mcp-server"]},
    "sequential-thinking":{"command": "npx", "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"]},
    "playwright":         {"command": "npx", "args": ["-y", "@playwright/mcp"]},
    "filesystem-pipeline":{"command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "/"]},
}


class MCPManager:
    """Gère le cycle de vie des MCPs : suggest → add → probe → active/remove."""

    def __init__(self, storage_path: Path, api_keys: dict[str, str] | None = None):
        self._storage_path = storage_path
        self._api_keys = api_keys or {}
        self._config_file = storage_path / "mcp_config.json"
        self._config: dict[str, Any] = self._load_config()
        self._event_log: list[dict[str, Any]] = []

    # ── Config ────────────────────────────────────────────────────────────────

    def _load_config(self) -> dict[str, Any]:
        if self._config_file.exists():
            with open(self._config_file) as f:
                return json.load(f)
        return {"config_id": str(uuid.uuid4()), "mcps": [], "last_updated": None}

    def _save_config(self) -> None:
        self._config["last_updated"] = datetime.now(timezone.utc).isoformat()
        self._config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self._config_file, "w") as f:
            json.dump(self._config, f, indent=2, ensure_ascii=False)

    # ── CRUD MCPs ─────────────────────────────────────────────────────────────

    def add_mcp(self, mcp_id: str, name: str, capabilities: list[str],
                tools: list[dict], source: str = "claude_suggested",
                requires_auth: bool = False, auth_key_name: str = "",
                mcp_url: str = "") -> dict[str, Any]:

        for mcp in self._config["mcps"]:
            if mcp["mcp_id"] == mcp_id:
                mcp["status"] = "testing"
                self._save_config()
                return mcp

        entry = {
            "mcp_id": mcp_id, "name": name, "source": source,
            "status": "testing", "requires_auth": requires_auth,
            "auth_key_name": auth_key_name, "mcp_url": mcp_url,
            "capabilities": capabilities,
            "tools": [{"name": t.get("name",""), "description": t.get("description",""), "tested": False, "test_result": "untested"} for t in tools],
            "added_at": datetime.now(timezone.utc).isoformat(),
            "added_by": "claude" if source == "claude_suggested" else "system",
            "test_log": [],
        }
        self._config["mcps"].append(entry)
        self._save_config()
        self._log("mcp_added", mcp_id, f"Added {name}")
        return entry

    def remove_mcp(self, mcp_id: str) -> None:
        self._config["mcps"] = [m for m in self._config["mcps"] if m["mcp_id"] != mcp_id]
        self._save_config()
        self._log("mcp_removed", mcp_id, f"Removed {mcp_id}")

    def set_status(self, mcp_id: str, status: str) -> None:
        for mcp in self._config["mcps"]:
            if mcp["mcp_id"] == mcp_id:
                mcp["status"] = status
                break
        self._save_config()

    def get_active_mcps(self)  -> list[dict]: return [m for m in self._config["mcps"] if m["status"] == "active"]
    def get_all_mcps(self)     -> list[dict]: return list(self._config["mcps"])
    def get_config(self)       -> dict:       return dict(self._config)

    # ── Probe réel via SDK ────────────────────────────────────────────────────

    def test_mcp(self, mcp_id: str) -> dict[str, Any]:
        """
        Teste un MCP via le SDK officiel :
        - stdio  → StdioServerParameters + stdio_client + session.initialize()
        - http   → streamable_http_client + session.initialize()
        Remplace l'ancien _probe_tool() basé sur pattern matching.
        """
        mcp_entry = next((m for m in self._config["mcps"] if m["mcp_id"] == mcp_id), None)
        if not mcp_entry:
            return {"mcp_id": mcp_id, "result": "not_found"}

        # Vérification auth
        if mcp_entry.get("requires_auth"):
            key = mcp_entry.get("auth_key_name", "")
            if key and not self._api_keys.get(key):
                mcp_entry["status"] = "excluded"
                self._save_config()
                self._log("mcp_test", mcp_id, "Excluded: missing API key")
                return {"mcp_id": mcp_id, "result": "excluded", "reason": "missing_api_key"}

        # Probe selon transport
        passed, tools_found, error = self._probe(mcp_id, mcp_entry)

        mcp_entry["status"] = "active" if passed else "failed"
        if tools_found:
            # Mise à jour des tools avec ceux découverts réellement
            mcp_entry["tools"] = [
                {"name": t["name"], "description": t.get("description",""), "tested": True, "test_result": "pass"}
                for t in tools_found
            ]
        mcp_entry["test_log"].append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "result": "pass" if passed else "fail",
            "tools_discovered": len(tools_found) if tools_found else 0,
            "error": error,
        })
        self._save_config()
        self._log("mcp_test", mcp_id, f"{'PASS' if passed else 'FAIL'} — {len(tools_found or [])} tools")

        return {"mcp_id": mcp_id, "result": "pass" if passed else "fail",
                "status": mcp_entry["status"], "tools": tools_found or []}

    def _probe(self, mcp_id: str, mcp_entry: dict) -> tuple[bool, list | None, str | None]:
        """Effectue le probe réel selon le transport disponible."""
        from .mcp_client import probe_stdio_sync, probe_sse_sync, get_stdio_tools_sync

        # 1. Serveur distant → SSE (Server-Sent Events)
        mcp_url = mcp_entry.get("mcp_url", "")
        if mcp_url and mcp_url.startswith("http"):
            try:
                ok = probe_sse_sync(mcp_url)
                return ok, None, None if ok else "SSE probe failed"
            except Exception as e:
                return False, None, str(e)

        # 2. Serveur stdio local avec commande connue
        if mcp_id in STDIO_COMMANDS:
            cmd = STDIO_COMMANDS[mcp_id]
            try:
                tools = get_stdio_tools_sync(cmd["command"], cmd["args"])
                return True, tools, None
            except Exception as e:
                return False, None, str(e)

        # 3. local_* → toujours disponible (pas de serveur externe)
        if mcp_id.startswith("local_"):
            return True, mcp_entry.get("tools", []), None

        # 4. Inconnu → assume OK mais log
        logger.warning("No probe strategy for %s — assuming available", mcp_id)
        return True, None, None

    def test_all_pending(self) -> list[dict[str, Any]]:
        return [self.test_mcp(m["mcp_id"]) for m in self._config["mcps"] if m["status"] == "testing"]

    # ── Sélection Claude ──────────────────────────────────────────────────────

    def ask_claude_for_mcps(self, job_data: dict, candidate_data: dict,
                             stage: str, available_mcps: list[dict]) -> list[dict]:
        from ..pipeline.llm import call_claude

        stage_goal = "TROUVER DES RESSOURCES (infos entreprise, compétences, marché)" \
                     if stage == "stage_1" else "ANALYSER EN PROFONDEUR la candidature"

        prompt = f"""Tu es un orchestrateur MCP. Étant donné cette offre et ce CV, \
détermine quels MCPs seraient utiles pour {stage_goal}.

OFFRE: {json.dumps(job_data, ensure_ascii=False)[:1000]}
CV: {json.dumps(candidate_data, ensure_ascii=False)[:1000]}
MCPs DISPONIBLES: {json.dumps(available_mcps, ensure_ascii=False)}

Pour chaque MCP utile: mcp_id, reason, priority (high/medium/low).
Réponds en JSON: {{"selected_mcps": [...]}}"""

        result = call_claude(self._api_keys, "Tu es un expert MCP. Réponds UNIQUEMENT en JSON.", prompt)
        if isinstance(result, dict) and "selected_mcps" in result:
            selected = result["selected_mcps"]
            self._log("claude_mcp_selection", stage, f"Claude selected {len(selected)} MCPs")
            return selected
        return []

    # ── Resources ─────────────────────────────────────────────────────────────

    def register_resources(self, resources: list[dict]) -> None:
        resources_file = self._storage_path / "resources.json"
        existing = json.loads(resources_file.read_text()) if resources_file.exists() else []
        existing.extend(resources)
        resources_file.write_text(json.dumps(existing, indent=2, ensure_ascii=False))
        self._log("resources_registered", "system", f"Registered {len(resources)} resources")

    def get_resources(self) -> list[dict]:
        resources_file = self._storage_path / "resources.json"
        return json.loads(resources_file.read_text()) if resources_file.exists() else []

    # ── Events ────────────────────────────────────────────────────────────────

    def _log(self, event_type: str, target: str, message: str) -> None:
        entry = {"type": event_type, "target": target, "message": message,
                 "timestamp": datetime.now(timezone.utc).isoformat()}
        self._event_log.append(entry)
        logger.info("[MCPManager] %s: %s — %s", event_type, target, message)

    def get_event_log(self) -> list[dict]: return list(self._event_log)
