"""Revise the Word reports to use paper-only citations and direct explanations."""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import re
import shutil
import subprocess
from zipfile import ZipFile

from lxml import etree as E

import build_teacher_documents_20261014 as previous

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "harness/workspaces/teacher-documents-editorial-20261014"
FULL = ROOT / "docs/M3_PI_Guard_研究介绍_2026-10-14.docx"
BRIEF = ROOT / "docs/M3_PI_Guard_研究介绍_教师交流两页版_2026-10-14.docx"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
NS = {"w": W[1:-1]}
REFERENCES = [
    "[1] Debenedetti E, Zhang J, Balunović M, et al. AgentDojo: A Dynamic Environment to Evaluate Prompt Injection Attacks and Defenses for LLM Agents. NeurIPS 37, 2024. DOI: 10.52202/079017-2636.",
    "[2] Shi T, He J, Wang Z, et al. Progent: Programmable Privilege Control for LLM Agents. 2025, arXiv预印本2504.11703v1. https://arxiv.org/abs/2504.11703v1",
    "[3] Debenedetti E, Shumailov I, Fan T, et al. Defeating Prompt Injections by Design. 2025, arXiv预印本2503.18813v1. https://arxiv.org/abs/2503.18813v1",
]
PAPER_LINKS = [
    "https://proceedings.neurips.cc/paper_files/paper/2024/hash/97091a5177d8dc64b1da8bf3e1f6fb54-Abstract-Datasets_and_Benchmarks_Track.html",
    "https://arxiv.org/abs/2504.11703v1", "https://arxiv.org/abs/2503.18813v1",
]

EARLY = [
    "E1 主防护效果。在相同提示条件下比较无Guard与完整Guard。gemma3:4b普通提示子集的攻击判定阳性分别为126/189与0/189。固定提示因素使该比较直接对应运行时检查的变化，为后续组件分析建立参照。",
    "E2 提示词强化。关闭Guard，比较普通提示与强化提示，观察模型对任务指令及外部内容的处理。它给出提示层干预的单独作用，并与后续执行检查的实验形成连续对照。",
    "E3 强化提示后的增量。使用相同强化提示，再比较有无Guard，分析提示层和执行层的互补关系。联合观察攻击结果与正常任务完成，可以定位新增检查改变了哪些动作。",
    "E4 组件消融。分别移除或单独启用检测、任务动作、数据流等组件，比较完整配置和简化配置。消融把整体结果拆成具体机制，便于查看某类规则触发的场景和正常任务代价。",
    "E5 跨模型比较。在不同本地模型上复用任务与配置，观察模型能力、输出格式及工具选择对防护结果的影响。各模型分别报告攻击、完成和解析状态，用于分析效果随模型变化的规律。",
    "E6 攻击家族分析。按攻击家族分层统计，定位残余风险及规则触发差异。家族层面的结果帮助选择后续反例，并将模型提出的动作与检查器的响应联系起来。",
    "E7 多语言鲁棒性。保持攻击目标，改变语言和表达形式，观察模型与防护链的变化。该设计检验系统对表面措辞的依赖，并比较各语言的调用、判定和完成情况。",
    "E8 编码与隐藏变体。使用编码、字符拆分、混淆和隐藏等变体，考察攻击表面变化与实际工具动作之间的关系。它补充多语言覆盖，并帮助比较文本检测和运行时约束的作用位置。",
    "E9 长上下文与位置。改变上下文负载和恶意内容的位置，观察任务约束在不同输入条件下的表现。校准上下文批次完成120条正式首步记录，无Guard与完整Guard的攻击判定阳性为36/60和0/60；长度和位置单元用于进一步分析差异分布。",
    "E10 多轮攻击。让攻击延迟出现、逐轮累积或分阶段铺垫，考察前文怎样影响后续工具选择。该实验把攻击从单次文本扩展到对话过程，并检验执行历史与确认状态的持续作用。",
    "E11 跨工具链传播。研究读取后发送、检索后调用API、记忆写入文件等链式任务。每一步分别核对动作目标和传送范围，分析恶意内容沿工具链传播的路径；原实验及48条后续补充执行分别呈现。",
    "E12 正常任务效用。通过正常任务测量完成率和误拦截。gemma3:4b普通提示下，无Guard完成48/81，完整Guard完成42/81。结合E1同模型的攻击观察，可以同时讨论保护作用与合法任务的可用性。",
    "E13 阈值校准。在验证集上扫描ASK与DENY阈值，比较恶意放行、正常误拦截和确认负担，再固定参数。该实验把不同错误的代价转为可比较的选择依据，为运行时决定提供校准。",
    "E14 性能与资源。校准性能批次包含432条正式记录和144对相同正常调用路径。Guard自身p95延迟约0.45毫秒，正常路径端到端开销中位数约0.20%；同时记录并发吞吐和设备显存，观察检查开销与系统负载的关系。",
    "E15 随机稳定性。改变随机种子和温度，重复观察同一配置。按任务保留重复结构，比较结果波动、解析状态与运行失败，用于判断现象在不同采样条件下的稳定程度。",
    "E16 自适应红队。根据前轮响应，从固定变体目录构造后续攻击。42条规范攻击谱系在三个轮次中观察到的成功率均为0，另保留一个未解决轮次；轮次变化用于分析模型响应怎样影响后续尝试。",
    "E17 人工失败复核。两位评审完成360条分层样本：300条代表性记录、40条自动分歧及20条稀有复杂记录。复核将泄露标签、误拦截、等待确认和解析失败分类，代表性层用于总体估计，诊断层用于解释具体失败。",
]

REWRITES = {
    8: "实验将授权信息作为影响任务完成的重要因素：复杂公开任务在自动权限下完成较低，增加精确目标信息后部分任务恢复完成。下文从早期实验、v1—v4方法演进和后续验证三个阶段介绍研究。",
    18: "早期E1—E17覆盖防护效果、攻击形式、效用与性能、稳定性和人工解释。后续五项增量研究使用另一套E1—E5编号；本节以早期系列为主，下一节单独介绍增量系列。",
    39: "2026年8月开展五项增量研究：提示词与模块的同期因子比较720条执行；来源对照240条端到端执行及480次离线判定；困难攻击复查240条执行；Flash复核360条执行。来源对照中，离线Guard产生来源相关的判定差异，端到端实际动作均为零，显示任务推进和组件触发处于不同环节。",
    40: "自适应尾部研究对预先选定、前200次查询未出现成功的12个任务，继续执行第201至500次查询，共3,600个终态查询，新增事件为零。连续查询的变化与同期攻击活性一起，用于分析模型响应、任务选择和持续尝试的关系。",
    45: "四次迭代围绕权限表达展开：v1修正动作、资源和执行记录的对应；v2区分需要限制的操作目标与允许生成的正文；v3表达多步骤任务契约和动态对象；v4提取任务意图，再由程序生成规则。每次迭代都针对前一阶段暴露的具体问题。",
    47: "本节v1—v4表示权限编译与任务契约链的版本。模型名称中的V4 Pro和V4.1 Flash分别表示所用模型，实验结果按编译链和模型两个维度呈现。",
    52: "这组实验同时设置攻击与正常任务。攻击子集观察模型是否偏离用户目标，正常子集观察防护条件下能完成多少合法工作。两类结果共同定位规则作用：哪些动作被阻止，哪些正常流程在权限或确认环节停止。",
    54: "v1将动作提出、Guard决定、隔离拒绝、实际模拟执行、任务完成和运行失败分别登记。执行日志说明动作发生在哪一步，独立评分说明它是否满足任务和安全要求。",
    56: "5 v2 授权研究与主要结果",
    57: "v2完成900条授权条件执行、480条同期校准和16条合成控制。授权研究包含180案例、153个底层任务；同期校准使用其中120案例。另对60个正常任务联结240份既有条件记录，分析任务意图与生成权限的对应。",
    60: "组成图统计任务在不同条件下的执行记录。同一任务分别使用不同模块和授权范围，形成多条配对记录。同期校准补充无防护参照，合成控制则设置明确的数据分类和传送目标，分别回答整体比较与规则机制的问题。",
    63: "v2把发送目标与生成内容分开处理：目标由权限约束，摘要正文由模型生成，并接受数据流检查。精确目标条件向Guard提供离线派生范围，用来观察目标信息充分时的完成变化；这一比较帮助定位自动编译缺失或绑定错误的目标。",
    64: "AgentDojo的30个正常任务中，policy从自动权限2/30提高到精确目标13/30，full从2/30提高到11/30。M3-v2的变化较小且方向不同，提示授权信息的作用与任务结构有关。",
    68: "AgentDojo正常完成的配对差为−50个百分点，95%区间为−66.83至−26.80；攻击判定差为−10个百分点，区间为−25.62至+3.10。效用差异把后续分析引向正常任务为何停止，以及哪些授权信息能恢复执行。",
    77: "五条件在同一任务上改变模块与授权信息。AgentDojo自动授权下两个模块各完成8项，明确目标后完成数回升。结果支持继续检查用户要求的工具、目标和约束怎样进入权限，M3-v2则结合确认任务的分层结果解释。",
    82: "Flash使用预先选定的任务子集，复核Pro上观察到的方向。AgentDojo再次出现自动权限完成较低、精确目标改善部分任务的模式；M3-v2五条件相同。各模型在自身任务分母内比较条件，再对照共同现象。",
    88: "配对比较追踪同一任务的变化：未完成转为完成计为改善，反向变化计为损失。图中的点表示净完成差，横线为95%区间。AgentDojo两项主比较显示明确改善，下一步可优先检查自动编译中的目标缺失、约束过窄与绑定错误。",
    94: "攻击比较将无防护条件作为活性参照，再观察policy与full的变化。Pro/AgentDojo无防护出现7个事件，防护条件为零；正常任务完成则反映同一套约束能否继续支持合法工作。联合观察两项结果，有助于定位规则改变了哪些动作。",
    97: "AgentDojo使用原生攻击安全评分，M3-v2使用成功执行的模拟越权效果。模型、条件、已知结局和未知结局分别列出，便于对应不同基准的任务定义。",
    101: "ASK表示需要补充授权或可信信息。在当前自动运行流程中，任务会停在等待环节。将ASK次数与正常完成一起观察，可以定位确认发生在哪里，并为设计澄清内容、批准方式和恢复执行流程提供依据。",
    110: "受控夹具主动提供能触发来源、顺序、保密和确认规则的提案，用于定位机制作用。自然提案回放则观察模型实际提出的动作；358对中3对改变决定，其余355对一致。两组结果将后续问题具体化为规则的触发机会与提案分布。",
    116: "编译通过表示草稿形成了可供运行时检查的任务契约。44次开发响应中40条编译失败，问题主要位于自然语言任务到结构化表达的转换。按任务来源和提示阶段分析参数角色、谓词及证据引用，可以定位应简化的表达和需要补齐的字段。",
    118: "开发记录的主要问题包括参数角色、有限谓词、来源引用及必要字段与运行契约不一致。已有反例用于修正检查链，下一步重点是让用户要求、契约字段和工具能力准确对应。",
    123: "v4让模型提取任务事实，由程序生成规则。32任务开发比较将下一步工作定位到三处接口：原文证据怎样支持参数，对象选择怎样交给后端验证，以及动态查询关系怎样表达为有限条件。",
    126: "覆盖图将计划与运行状态放在同一视图中：Pro320项记录、Flash20项前缀和300项未执行。已有记录包含编译失败、需要澄清与实际调用等状态，读图时可对应到各阶段的任务数量。",
    130: "第一，授权信息直接影响正常任务完成。v2和强化实证共同观察到，复杂公开任务在自动权限下完成较低，增加精确目标信息可以恢复一部分任务。",
    131: "第二，规则触发与模型提案共同决定系统结果。受控夹具展示来源、保密、顺序和确认机制，自然提案回放显示其在实际动作中产生判定变化的频率。",
    132: "第三，v3/v4将改进方向推进到任务理解、参数角色、动态对象和原文证据。开发结果使研究问题集中到可信任务表达与实际工具能力的衔接。",
    135: "15 3 局限性",
    136: "本研究的局限性集中在实验覆盖与结论范围：现有安全事件较少，部分无防护单元为零；精确目标条件使用离线派生范围；Pro与Flash来自同一服务提供方，结果对应隔离环境和指定任务窗口。历史与修正版各自使用当时的评价定义，v3/v4当前属于开发验证，完整模块相对仅权限的自然任务增益仍待进一步检验。图集中的历史、诊断和停用版本用于说明研究过程；E17人工复核覆盖360条分层样本。后续重点是扩大独立任务覆盖，改善自动授权并检验交互确认后的完成情况。",
    137: "15 4 后续研究安排",
    138: "后续首先梳理正常任务在目标绑定、工具选择和确认环节的停止原因，再以对象明确的场景改进契约表达。验证时固定任务与模型，分别改变授权信息和运行时模块，以配对结果评价正常完成、越权效果和交互负担。",
}

CAPTIONS = {
    "N02": "v1至v4的权限编译与任务契约演进。v1修正动作资源对应，v2区分目标与内容，v3/v4表达任务结构和动态对象授权。",
    "N03": "v2研究的条件执行组成。720条主授权执行与180条压力条件执行构成900条授权研究，另有480条同期校准与16条合成控制；120个校准案例来自180个主研究案例。",
    "N06": "授权信息的配对完成差及95%区间。Pro的两项AgentDojo主比较通过预定Holm校正，Flash用于对照变化方向。",
    "N07": "Pro/AgentDojo攻击观察。无防护7/40、Policy与Full各0/40；两项对无防护比较的Holm校正p值均为0.078125。VIGIL适配配置有36项已知结果、4项未知。",
    "N11": "v3开发编译。44次响应中4条通过、40条失败；按任务来源和开发提示阶段分别展示。",
    "N12": "同一32个任务的v3与v4最终编译状态，分为16个调试任务和16个资格任务。v3可运行5/32，v4为0/32。",
    "N13": "v4开发覆盖。640个计划条件项中，Pro产生320项记录，Flash产生20项前缀记录，另300项未执行。",
    "N14": "v1开发研究的Pro/AgentDojo普通提示子集。正常任务8个，攻击任务12个；每模型完整开发研究包含48任务、六配置、288条执行。",
}

TITLES = {
    "ablation_contribution_forest":"组件消融的配对差异", "acceptance_before_after":"修正前后指标对照",
    "activity_conditions_v2":"攻击条件与运行失败", "activity_observed_rates_v1":"各条件攻击观察",
    "adaptive_asr_budget_curve":"查询预算与攻击结果", "adaptive_asr_by_family":"各攻击家族的自适应结果",
    "adaptive_asr_by_round":"自适应攻击轮次", "adaptive_canary_asr":"小批次自适应攻击",
    "agentdojo_four_suite_screen":"四类任务的配置比较", "asr_by_suite":"各任务域的攻击结果",
    "attack_success_by_bucket":"攻击类别与结果", "attack_success_by_defense":"各防护配置的攻击结果",
    "benchmark_recall_fpr":"检测召回与误报", "case_latency_vs_comparator":"任务延迟对照",
    "compilation_status":"任务契约编译状态", "completion_by_regime":"各授权条件的任务完成",
    "contemporaneous_endpoints":"同期安全与正常完成", "context_position_trends":"上下文长度与注入位置",
    "corrected_safety_utility":"修正后的安全与效用", "coverage":"开发任务覆盖",
    "cross_model_heatmap":"不同模型的结果比较", "cross_tool_chain_patterns":"跨工具链的攻击传播",
    "current_01_boundaries":"任务授权与执行评分流程", "current_02_authorization":"自动授权与精确目标",
    "current_03_calibration":"同期攻击与任务完成", "current_04_restrictions":"首次限制与流程终态",
    "diagnostic_comparison":"配置诊断比较", "failure_taxonomy":"失败类型分布",
    "family_robustness":"各攻击家族的配置结果", "figure_1_authority_boundary":"内容来源与授权范围",
    "figure_1_online_field_isolation":"在线任务信息与离线评分", "figure_2_factorial_interactions":"提示词与模块的因子比较",
    "figure_2_safety_utility_pareto":"安全与正常完成的联合结果", "figure_3_authorization_forest":"授权条件的配对效应",
    "figure_3_provenance_counterfactual":"可信与不可信来源对照", "figure_4_factor_effect_forest":"不同队列的因子效应",
    "figure_4_runtime_burden":"确认拒绝与运行负担", "figure_5_adaptive_first_success":"预算增加时的首次成功",
    "figure_5_adaptive_tail":"预选任务的自适应尾部", "g3_gate_checks":"运行条件核验",
    "gpu_memory_by_context":"上下文负载与设备显存", "guard_ablation":"Guard组件贡献",
    "historical_diagnostic_metrics":"早期配置诊断指标", "language_evasion":"多语言及编码变体",
    "latency_by_context":"上下文负载与任务延迟", "latency_ecdf":"任务延迟累计分布",
    "legacy_vs_corrected_asr":"评价口径修正前后对照", "m3_attack_family_recall":"各攻击家族的检测召回",
    "m3_language_performance":"不同语言的检测表现", "main_defense_effect":"主要配置的安全与效用",
    "model_effects":"不同模型的修正结果", "multiturn_adaptive_trends":"多轮及自适应攻击变化",
    "nested_provider_diagnostic_v2":"第二提供方的覆盖诊断", "observed_endpoints":"攻击与正常完成观察",
    "paired_outcomes":"同任务的配对结局", "performance_overhead":"Guard检查开销",
    "performance_profile":"延迟与吞吐概况", "policy_regime_smoke":"授权条件的功能诊断",
    "pr_curve":"精确率与召回率", "primary_chart":"主要条件比较", "prompt_baseline_comparison":"提示词基线对照",
    "prompt_guard_increment":"强化提示与Guard增量", "public_primary_diagnostics_v1":"公开基准运行负担",
    "public_primary_security_v1":"公开基准攻击结果", "public_primary_utility_v1":"公开基准正常完成",
    "random_stability":"随机种子与温度稳定性", "recovery_profile":"运行恢复类型",
    "redaction_rate_by_suite":"各任务域的检测修改", "representative_failure_counts":"代表性样本的失败类型",
    "roc_curve":"真阳性与假阳性关系", "roc_pr_curves":"检测分类曲线",
    "sample_group_composition":"人工复核各层组成", "score_distributions":"检测分数分布",
    "selected_cluster_repeat":"预选任务的重复运行", "smoke_completion_status":"功能诊断的运行状态",
    "smoke_effects":"功能诊断的执行效果", "tcr_by_suite":"各任务域的正常完成",
    "threshold_calibration":"阈值选择与分类指标", "threshold_heatmap":"阈值组合与错误代价",
    "throughput_by_concurrency":"并发负载与系统吞吐", "utility_observed_rates_v1":"正常任务完成比例",
    "verifier_contract_pressure":"契约生成与检查负担", "weighted_population_estimates":"分层加权的失败类型估计",
}
STUDIES = {
    "final_analysis":"早期综合分析", "incremental_empirical_v1":"后续增量研究", "lean_empirical":"授权制度研究",
    "research_followup_20261006_v1":"同期校准研究", "e6_cross_provider_calibration_v2":"跨提供方校准",
    "empirical_reinforcement_v1":"强化实证研究", "correctness_repair_v1":"v1修复开发研究",
    "E17_human_stratified_360_v1":"E17人工复核", "task_contract_compiler_v4_development_v1":"v4任务契约开发",
    "acceptance_remediation_v2":"规则修正研究", "claude_revision_v1":"v2授权研究", "formal_public":"公开基准研究",
}


def text(p):
    return "".join(p.xpath(".//w:t/text()", namespaces=NS))


def replace_text(p, value):
    props = p.find(W + "pPr")
    runprops = p.find(".//w:r/w:rPr", NS)
    rpr = deepcopy(runprops) if runprops is not None else E.Element(W + "rPr")
    for child in list(p):
        if child is not props:
            p.remove(child)
    run = E.SubElement(p, W + "r")
    run.append(rpr)
    t = E.SubElement(run, W + "t")
    t.text = value


def make_p(value, prototype, small=False, heading=False):
    p = E.Element(W + "p")
    props = prototype.find(W + "pPr")
    if props is not None:
        p.append(deepcopy(props))
    r = E.SubElement(p, W + "r")
    rpr = E.SubElement(r, W + "rPr")
    fonts = E.SubElement(rpr, W + "rFonts")
    for name in ("ascii", "hAnsi", "eastAsia", "cs"):
        fonts.set(W + name, "黑体" if heading else "宋体")
    E.SubElement(rpr, W + "color").set(W + "val", "000000")
    E.SubElement(rpr, W + "sz").set(W + "val", "18" if small else "24")
    if heading:
        E.SubElement(rpr, W + "b")
    E.SubElement(r, W + "t").text = value
    if small:
        props = p.find(W + "pPr")
        if props is None:
            props = E.Element(W + "pPr")
            p.insert(0, props)
        for child in list(props):
            if child.tag in {W + "pStyle", W + "ind", W + "spacing", W + "keepNext"}:
                props.remove(child)
        E.SubElement(props, W + "spacing", {W + "after":"80", W + "line":"260", W + "lineRule":"auto"})
    return p


def caption(stem):
    name = Path(stem).name
    assert name in TITLES, name
    study = next((v for k, v in STUDIES.items() if "/" + k + "/" in stem), "")
    early = re.search(r"/(E\d+)(?:/|_)", stem)
    if early:
        study = early.group(1) + "实验"
    if "/baselines/" in stem:
        study = ("工具过滤" if "tool_filter" in stem else "CaMeL" if "camel_" in stem
                 else "IPIGuard" if "ipiguard" in stem else "检测器") + "基线"
        study += "资格批次" if "qualification" in stem else "正式批次"
    if "/injecagent_stage/" in stem:
        study = "InjecAgent工具交互"
    if not study:
        study = "配置与运行诊断" if any(x in stem for x in ("diagnostic", "smoke", "preflight")) else "工具智能体实验"
    return study + "  " + TITLES[name]


def revise_full():
    source = WORK / "before_detailed.docx"
    data = json.loads((ROOT / "harness/workspaces/research-introduction-20261014/research_data.json").read_text(encoding="utf-8"))
    gallery = {x["source_stem"].removeprefix("outputs/"): caption(x["source_stem"]) for x in data["history_gallery"]}
    with ZipFile(source) as z:
        root = E.fromstring(z.read("word/document.xml"))
        body = root.find("w:body", NS)
        ps = list(body.findall("w:p", NS))
        assert text(ps[17]).startswith("2 2 早期") and text(ps[135]).startswith("15 3")
        prototype, head = ps[3], ps[133]
        removed, rewrites = 0, 0
        for i, p in enumerate(ps):
            old = text(p)
            if not old:
                continue
            if re.match(r"^(来源\s*\[|机制来源|资料依据|上述历史过程依据|本节来源)", old):
                body.remove(p)
                removed += 1
                continue
            if old.startswith("图集为缩略导航"):
                if i == 141:
                    replace_text(p, "下列图表按研究阶段汇总，H编号用于查找同一实验的不同视图。")
                else:
                    body.remove(p)
                    removed += 1
                continue
            value = re.sub(r"\[\d+(?:[;,，、\-]\d+)*\]", "", old).strip()
            if 19 <= i <= 35:
                value = EARLY[i - 19]
            if i in REWRITES:
                value = REWRITES[i]
            m = re.match(r"图\s+(N\d+)\s", old)
            if m and m.group(1) in CAPTIONS:
                value = "图 " + m.group(1) + "  " + CAPTIONS[m.group(1)]
            value = value.replace("原生安全判定阳性", "原生攻击判定阳性")
            if value != old:
                replace_text(p, value)
                rewrites += 1
        # Literature supports the conceptual context, while all experiment numbers
        # remain the project's own results, identified by cohort/model/condition.
        related = "相关工作提供了三条参照：AgentDojo用动态工具环境同时评价任务完成与提示注入[1]；Progent以工具名称和参数表达权限规则[2]；CaMeL分离控制流与数据流，并用能力约束数据传送[3]。本项目围绕授权信息、运行时模块和正常完成设计比较实验。"
        ps[4].addnext(make_p(related, prototype))
        first_appendix = next(p for p in body.findall("w:p", NS) if text(p).startswith("附录 A"))
        first_appendix.addprevious(make_p("参考文献", head, heading=True))
        for ref in REFERENCES:
            first_appendix.addprevious(make_p(ref, prototype, small=True))
        for p in root.findall(".//w:tc/w:p", NS):
            old = text(p)
            if old in gallery:
                replace_text(p, gallery[old])
            elif any(x in old for x in ("experiments/", "paper_upgrade_", "outputs/", "docs/")):
                raise ValueError("Unmapped gallery path: " + old)
        previous.drop_forced_pages(root)
        previous.blacken(root)
        tmp = WORK / "detailed_report.docx"
        with ZipFile(tmp, "w") as out:
            for info in z.infolist():
                data = E.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True) if info.filename == "word/document.xml" else z.read(info.filename)
                out.writestr(info, data)
    shutil.copy2(tmp, FULL)
    return {"removed_source_or_repeat_paragraphs": removed, "rewritten_body_paragraphs": rewrites,
            "gallery_captions_named": len(gallery)}


def revise_brief():
    original = previous.BRIEF_CONTENT
    content = []
    for kind, old in original:
        if kind == "source":
            continue
        value = re.sub(r"\[\d+\]", "", old).strip()
        if kind == "body" and old.startswith("用户请求和可信应用声明"):
            value += "相关工作中，AgentDojo评价工具任务[1]，Progent用规则约束调用[2]，CaMeL以控制流和数据流隔离处理注入[3]。"
        if kind == "body" and old.startswith("历史结果同时"):
            value = "早期E1的gemma3:4b普通提示子集中，攻击判定阳性由无Guard的126/189降至完整Guard的0/189；E12同模型正常完成由48/81降至42/81。两类任务共同呈现保护作用与正常完成的变化。"
        elif kind == "body" and old.startswith("E9 的校准"):
            value = "E9校准上下文实验记录无Guard与完整Guard攻击判定阳性36/60、0/60。E14记录Guard自身p95延迟约0.45毫秒、相同正常路径的端到端开销中位数约0.20%。E17两位评审复核360条分层样本，其中300条为代表性样本。"
        elif kind == "body" and old.startswith("这些结果把研究重点"):
            value = "这些结果将研究重点推进到权限表达和执行过程：操作目标、数据范围和确认规则怎样支持合法任务，又在哪一步改变了越权动作。实验分别登记提案、Guard决定、实际执行、完成与失败，以定位差异发生的环节。"
        elif kind == "body" and old.startswith("此后另开展"):
            value = "后续五项增量研究补充提示词与模块因子比较、来源对照、困难攻击复查、Flash复核及自适应尾部观察。来源对照中，检查器产生来源相关的判定差异，任务实际动作却为零；这一现象使后续分析进一步关注任务推进、确认交互和攻击活性。"
        content.append((kind, value))
    content += [
        ("source", "研究局限性：历史与修正版使用各自评价定义，安全事件较少；当前结果对应所选模型、任务与隔离环境。后续需扩大独立任务覆盖，并检验真实确认交互对任务完成的影响。"),
        ("heading", "参考文献"),
        *(("source", ref) for ref in REFERENCES),
    ]
    previous.WORK = WORK
    previous.BRIEF_CONTENT = content
    previous.create_brief()


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    for path, name in ((FULL, "before_detailed.docx"), (BRIEF, "before_brief.docx")):
        if not (WORK / name).exists():
            shutil.copy2(path, WORK / name)
    snapshot = WORK / "before.json"
    if not snapshot.exists():
        staged = subprocess.run(["git", "diff", "--cached", "--binary"], cwd=ROOT, capture_output=True, check=True).stdout
        snapshot.write_text(json.dumps({"staged_diff_sha256":sha256(staged).hexdigest(), "paper_links":PAPER_LINKS}, indent=2), encoding="utf-8")
    changes = revise_full()
    revise_brief()
    (WORK / "editorial_changes.json").write_text(json.dumps(changes, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(changes, ensure_ascii=False))


if __name__ == "__main__":
    main()
