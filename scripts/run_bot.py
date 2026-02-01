#!/usr/bin/env python3
"""Run Slack bot."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.bot.slack_bot import run_bot

if __name__ == "__main__":
    asyncio.run(run_bot())
