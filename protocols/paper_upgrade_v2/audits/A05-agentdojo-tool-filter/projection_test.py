"""针对审计单元 [A05-agentdojo-tool-filter] 重新运行源码边界投影检查（Source-Boundary Projection Check）。

验证该基线/防御实现与 M3 审计规范的一致性及边界完整性。"""

import sys
from pathlib import Path

# 项目根目录路径解析
PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 导入在线状态审计规范验证函数
from experiments.paper_v2.source_audit import verify_unit_from_paths


if __name__ == "__main__":
    # 执行该审计单元的路径投影与边界规格校验
    verify_unit_from_paths(
        spec_path='protocols/paper_upgrade_v2/online_state_audit_specs_v1.json',
        audit_id='A05-agentdojo-tool-filter',
    )
