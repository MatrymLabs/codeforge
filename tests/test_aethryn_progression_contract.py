"""The Aethryn Seed declares a player curve that reaches its level-300 campaign summit."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_aethryn_player_progression_reaches_its_level_300_campaign_cap() -> None:
    """Probe in a child process so the Aethryn import-time binding cannot pollute other Seeds."""
    repo = Path(__file__).resolve().parent.parent
    probe = (
        "from kernel.world.progression import get_next_level_threshold, "
        "get_player_level_cap, marginal_xp_for_level; "
        "assert get_player_level_cap() == 300; "
        "assert marginal_xp_for_level(300) > 0; "
        "assert get_next_level_threshold(300) is None"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=repo,
        env={**os.environ, "FORGE_SEED": "aethryn"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"Aethryn progression probe failed:\n{result.stderr}"
