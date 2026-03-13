#!/usr/bin/env python3
"""Convenience script for resources data backfill."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.run_backfill import main

sys.argv = [sys.argv[0], "run", "--type", "resources"] + sys.argv[1:]
sys.exit(main())
