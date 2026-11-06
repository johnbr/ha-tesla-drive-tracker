"""Load the integration's Home Assistant-free modules without importing it.

The package ``__init__`` needs Home Assistant, but the rule modules don't, so
they are loaded from a synthetic package whose path points at the integration.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

_DIR = Path(__file__).resolve().parents[1] / "custom_components" / "tesla_drive_tracker"

package = ModuleType("tesla_drive_tracker_isolated")
package.__path__ = [str(_DIR)]
sys.modules["tesla_drive_tracker_isolated"] = package
