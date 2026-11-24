"""Vercel loads this module and routes every request to the ledger app."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from ledger.api.app import app

__all__ = ["app"]
