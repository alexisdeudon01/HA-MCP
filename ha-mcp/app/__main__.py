"""Allow running as: python -m app.server"""
from pathlib import Path
from dotenv import load_dotenv

# Charge .env depuis la racine du projet (ha-mcp/.env)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from .server import main
main()
