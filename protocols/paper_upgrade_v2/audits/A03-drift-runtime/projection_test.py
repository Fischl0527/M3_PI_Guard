"""Re-run the source-boundary projection check for this audit unit."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from experiments.paper_v2.source_audit import verify_unit_from_paths


if __name__ == "__main__":
    verify_unit_from_paths(
        spec_path='protocols/paper_upgrade_v2/online_state_audit_specs_v1.json',
        audit_id='A03-drift-runtime',
    )
