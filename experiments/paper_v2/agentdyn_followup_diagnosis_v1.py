"""原生基准参考轨迹离线诊断模块（仅限离线使用，与正式评测解耦）。

深入分析智能体在 AgentDyn 基准下的执行轨迹差异与潜在攻击拦截点。
"""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys

from experiments.paper_v2.agentdyn_native_qualification_v1 import COMMIT, PROTOCOL, ROOT, SOURCE, offline_boundary

OUTPUT = ROOT / "outputs/experiments/research_followup_20261006_v1/agentdyn"


def result_category(result, error=None):
    if error:
        return "runtime_error"
    if isinstance(result, dict):
        if result.get("error") or result.get("status") in {"error", "failed", "failure"}:
            return "tool_reported_failure"
    if isinstance(result, str):
        value = result.casefold().strip()
        if value.startswith(("error", "failed", "invalid", "incorrect", "not logged", "verification failed")):
            return "tool_reported_failure"
        if "error" in value or "failed" in value or "invalid" in value:
            return "possible_error_text_not_proven"
    return "no_error_flag_observed_not_success_proof"


def diagnose():
    if not sys.flags.utf8_mode or "agentdojo" in sys.modules:
        raise ValueError("native diagnosis requires fresh UTF8 process without legacy module collision")
    actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=SOURCE, text=True).strip()
    if actual != COMMIT:
        raise ValueError("native source drift")
    selected = json.loads((PROTOCOL / "qualification_sample_v1.json").read_text(encoding="utf-8"))["sample"]
    sys.path.insert(0, str(SOURCE / "src"))
    from agentdojo.agent_pipeline.ground_truth_pipeline import GroundTruthPipeline
    from agentdojo.functions_runtime import FunctionsRuntime
    from agentdojo.task_suite import get_suite

    rows = []
    for item in selected:
        suite = get_suite("v1", item["suite"])
        task = suite.get_user_task_by_id(item["user_task_id"])
        events = []

        class RecordingRuntime(FunctionsRuntime):
            def run_function(self, env, function, kwargs, raise_on_error=False):
                event = {"index": len(events) + 1, "tool": function, "argument_names": sorted(kwargs), "argument_values_logged": False}
                events.append(event)
                try:
                    result, error = super().run_function(env, function, kwargs, raise_on_error)
                    event.update(result_type=type(result).__name__, result_category=result_category(result, error), result_body_logged=False,
                                 function_error_type=str(error).split(":", 1)[0] if error else None)
                    return result, error
                except Exception as exc:
                    event.update(result_category="raised_exception", function_error_type=type(exc).__name__, result_body_logged=False)
                    raise

        with offline_boundary() as blocked, contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            try:
                utility, _ = suite.run_task_with_pipeline(GroundTruthPipeline(task), task, None, {}, runtime_class=RecordingRuntime, verbose=False)
                status, failure = "completed", None
            except Exception as exc:
                utility, status, failure = None, "offline_reference_failure", type(exc).__name__
        rows.append({**item, "status": status, "reference_utility": utility, "failure_class": failure,
                     "events": events, "blocked_physical_effect_attempts": len(blocked),
                     "interpretation": "reference_control_only_not_model_performance_or_upstream_bug_proof"})
    return {"source_commit": COMMIT, "tasks": len(rows), "provider_calls": 0, "reference_successes": sum(r["reference_utility"] is True for r in rows),
            "reference_false": sum(r["reference_utility"] is False for r in rows), "rows": rows,
            "known_limitation": "dynamic callbacks execute beneath outer tool runtime; leaf authorization interception and grader positive/negative controls still required before any model experiment",
            "online_labels_or_ground_truth_used": False}


def write_outputs(result, output=OUTPUT):
    output.mkdir(parents=True, exist_ok=True)
    (output / "reference_diagnosis.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# P3 AgentDyn原生参考链诊断", "", "## 本次完成", "",
             f"固定原18任务，0模型请求。参考链评分成功{result['reference_successes']}，false {result['reference_false']}；没有改上游任务、评分器或样本。仅记录工具名、参数名和响应类型/错误类别，不记录参数值、响应正文或离线答案内容。", "",
             "|套件/任务|参考完成|首次可见错误标志|参考调用数|物理效果阻断|", "|---|---|---|---:|---:|"]
    for row in result["rows"]:
        first = next((e for e in row["events"] if e["result_category"] in {"runtime_error", "tool_reported_failure", "raised_exception"}), None)
        description = f"{first['tool']}/{first['result_category']}" if first else "无明确错误标志；不等于动作成功"
        lines.append(f"|{row['suite']}/{row['user_task_id']}|{row['reference_utility']}|{description}|{len(row['events'])}|{row['blocked_physical_effect_attempts']}|")
    lines += ["", "## 尚未合格的部分", "", "原生动态网页工具可能在单次browse/input调用内部触发购物、账号等注册操作。当前外层FunctionsRuntime日志不能证明内层操作逐一经过Guard。因此不能直接把现有18任务适配成可部署完整防护，也不能只挑8个参考成功任务放进正式实验。", "", "下一步必须独立完成叶子工具全覆盖监控以及18任务评分的合法/越权状态对照。参考false若伴随工具失败，可以定位夹具/步骤前提；没有错误标志时仍需评分条件检查，不能改评分器让参考答案通过。这个诊断不是108条模型实验结果。", "", "范围和产物：E:\\M3_PI_Guard_test\\outputs\\experiments\\research_followup_20261006_v1\\agentdyn/reference_diagnosis.json与report.md。保留原qualification_v2.json，不递归重算历史或创建重复哈希包。", "", "可信度：8/10。依据：固定原生执行链直接观察；内层工具和评分状态对照尚未齐备。", ""]
    (output / "report.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    result = diagnose()
    write_outputs(result)
    print(json.dumps({k: result[k] for k in ("tasks", "provider_calls", "reference_successes", "reference_false")}))
