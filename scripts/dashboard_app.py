"""Streamlit-safe entry point for the M3 evidence dashboard.

Running a module inside ``m3_eval`` directly puts that directory
ahead of the standard library on ``sys.path``.  Its local ``statistics.py``
can then shadow Python's standard-library ``statistics`` module.  Keeping the
Streamlit entry point under ``scripts`` and importing the dashboard as a
package preserves normal import resolution.  The enhanced dashboard lives in
``m3_eval.evidence_dashboard`` so the exact blind-frozen
``m3_eval.dashboard`` source remains byte-identical for provenance audits.
"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from m3_eval.evidence_dashboard import main


if __name__ == "__main__":
    # Streamlit owns the script lifecycle. Raising ``SystemExit(0)`` after a
    # successful render leaves its front-end status widget stuck on RUNNING.
    main()
