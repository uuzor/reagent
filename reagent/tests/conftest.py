"""Shared test configuration — adds reagent package to sys.path."""

import sys
from pathlib import Path

# reagent/tests/ -> reagent/  (parent directory contains gitlab_client, file_manager)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
