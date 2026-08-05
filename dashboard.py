"""
SR6 Multi-Character Dashboard Launcher.
Run with: uv run dashboard.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fasthtml.common import serve
from sr6core.web.app import create_app

app = create_app()

if __name__ == "__main__":
    print("=" * 60)
    print(" LAUNCHING SR6 MULTI-CHARACTER DASHBOARD")
    print(" Open in browser: http://localhost:5001")
    print("=" * 60)
    serve()
