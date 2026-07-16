import fs from "node:fs/promises";
import path from "node:path";
import crypto from "node:crypto";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const EXPERIMENT_IDS = Array.from({ length: 18 }, (_, index) => `E${index}`);
const FIGURE_SLOTS = [
  [6, "main_defense_effect", "prompt_guard_increment"],
  [7, "guard_ablation", "threshold_calibration"],
  [8, "cross_model_heatmap", "family_robustness"],
  [9, "language_evasion", "multiturn_adaptive_trends"],
  [10, "performance_profile", "failure_taxonomy"],
];
const TRUTHFULNESS_ARTIFACTS = [
  "result_integrity_audit.json",
  "main_parse_quality.json",
  "e16_provenance.json",
];
const LEFT_FIGURE_FRAME = { left: 66, top: 148, width: 548, height: 438 };
const RIGHT_FIGURE_FRAME = { left: 666, top: 148, width: 548, height: 438 };

function parseArgs(argv) {
  const result = {};
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (!token.startsWith("--")) throw new Error(`Unexpected positional argument: ${token}`);
    const next = argv[index + 1];
    if (!next || next.startsWith("--")) {
      result[token.slice(2)] = true;
    } else {
      result[token.slice(2)] = next;
      index += 1;
    }
  }
  return result;
}

function requireArg(args, name) {
  const value = args[name];
  if (typeof value !== "string" || !value.trim()) throw new Error(`Missing --${name}`);
  return path.resolve(value);
}

async function readJson(filePath, label) {
  try {
    return JSON.parse(await fs.readFile(filePath, "utf8"));
  } catch (error) {
    throw new Error(`Cannot read ${label} JSON at ${filePath}: ${error.message}`);
  }
}

async function sha256(filePath) {
  const bytes = await fs.readFile(filePath);
  return crypto.createHash("sha256").update(bytes).digest("hex");
}

async function verifyLedgerEntry(root, entry, label) {
  if (!entry || typeof entry !== "object") throw new Error(`${label} is not an object`);
  const relative = String(entry.path || "");
  if (!relative || path.isAbsolute(relative) || relative.split(/[\\/]+/).includes("..")) {
    throw new Error(`${label} has unsafe relative path: ${relative}`);
  }
  const target = path.resolve(root, relative);
  if (path.relative(root, target).startsWith("..")) throw new Error(`${label} escapes its root`);
  const stat = await fs.stat(target).catch(() => undefined);
  if (!stat?.isFile()) throw new Error(`${label} is missing: ${relative}`);
  if (stat.size !== entry.bytes) throw new Error(`${label} byte-size drift: ${relative}`);
  const digest = await sha256(target);
  if (digest !== entry.sha256) throw new Error(`${label} SHA-256 drift: ${relative}`);
  return target;
}

function targetById(executive, targetId) {
  const target = (executive.targets || []).find((item) => item.target_id === targetId);
  if (!target) throw new Error(`executive_summary.json is missing target ${targetId}`);
  return target;
}

function formatPercent(value) {
  return typeof value === "number" && Number.isFinite(value) ? `${(value * 100).toFixed(1)}%` : "NA";
}

function validateParseQuality(parseQuality, auditAnchor) {
  if (!parseQuality || typeof parseQuality !== "object") throw new Error("main_parse_quality.json is not an object");
  if (parseQuality.source_audit_sha256 !== auditAnchor.source_sha256) {
    throw new Error("main parse quality is bound to a different integrity audit");
  }
  const threshold = parseQuality.reference?.threshold;
  if (typeof threshold !== "number" || !Number.isFinite(threshold) || threshold < 0 || threshold > 1) {
    throw new Error("main parse quality has an invalid reference threshold");
  }
  for (const [label, metric] of [
    ["overall.step_row", parseQuality.overall?.step_row],
    ["overall.run", parseQuality.overall?.run],
  ]) {
    if (!metric || !Number.isInteger(metric.successes) || !Number.isInteger(metric.denominator) || metric.denominator <= 0) {
      throw new Error(`main parse quality ${label} has invalid counts`);
    }
    if (typeof metric.estimate !== "number" || !["pass", "fail"].includes(metric.status_against_reference)) {
      throw new Error(`main parse quality ${label} has invalid estimate/status`);
    }
  }
  if (!Array.isArray(parseQuality.by_model) || !parseQuality.by_model.length) {
    throw new Error("main parse quality has no model diagnostics");
  }
  if (!Array.isArray(parseQuality.models_below_reference?.step_row) || !Array.isArray(parseQuality.models_below_reference?.run)) {
    throw new Error("main parse quality lacks below-reference model lists");
  }
}

function validateE16Provenance(provenance) {
  if (!provenance || typeof provenance !== "object" || provenance.experiment_id !== "E16") {
    throw new Error("e16_provenance.json has the wrong identity");
  }
  if (provenance.evidence_tier !== "formal_dedicated" || provenance.excluded_from_main_matrix !== true) {
    throw new Error("E16 provenance does not preserve its dedicated/excluded evidence scope");
  }
  const runtime = provenance.runtime_observation;
  const version = String(runtime?.sandbox_runtime_version || "").trim();
  if (!version || runtime?.missing_runtime_field_rows !== 0 || runtime?.mismatch_rows !== 0) {
    throw new Error("E16 sandbox runtime provenance is incomplete or inconsistent");
  }
  if (JSON.stringify(runtime.direct_field_versions) !== JSON.stringify([version])
      || JSON.stringify(runtime.model_config_field_versions) !== JSON.stringify([version])) {
    throw new Error("E16 sandbox runtime provenance is not a singleton in both log fields");
  }
  if (typeof provenance.denominator_scope !== "string" || !provenance.denominator_scope.trim()) {
    throw new Error("E16 provenance lacks its dedicated denominator scope");
  }
}

function formatQualityMetric(metric) {
  return `${metric.successes}/${metric.denominator}=${formatPercent(metric.estimate)}（${String(metric.status_against_reference).toUpperCase()}）`;
}

async function loadFormalEvidence(analysisDir, registryPath) {
  const manifestPath = path.join(analysisDir, "manifest.json");
  const manifest = await readJson(manifestPath, "final_analysis manifest");
  if (manifest.artifact_type !== "final_analysis_synthesis" || manifest.status !== "completed") {
    throw new Error("final_analysis manifest is not a completed formal synthesis");
  }
  if (manifest.synthesis_id !== "E18") throw new Error("final_analysis synthesis_id must be E18");
  if (JSON.stringify(manifest.registry_experiments) !== JSON.stringify(EXPERIMENT_IDS)) {
    throw new Error("final_analysis does not declare the exact E0-E17 sequence");
  }

  const registry = await readJson(registryPath, "experiment registry");
  const ids = (registry.experiments || []).map((item) => item.id);
  if (JSON.stringify(ids) !== JSON.stringify(EXPERIMENT_IDS)) {
    throw new Error("registry does not contain the exact ordered E0-E17 sequence");
  }
  const incomplete = registry.experiments.filter((item) => item.status !== "completed").map((item) => item.id);
  if (incomplete.length) throw new Error(`registry experiments are not completed: ${incomplete.join(", ")}`);
  if ((await sha256(registryPath)) !== manifest.registry_sha256) {
    throw new Error("registry SHA-256 differs from the final_analysis admission hash");
  }

  const artifactMap = new Map();
  for (const [index, entry] of (manifest.artifacts || []).entries()) {
    if (artifactMap.has(entry.path)) throw new Error(`duplicate final_analysis artifact path: ${entry.path}`);
    artifactMap.set(entry.path, await verifyLedgerEntry(analysisDir, entry, `manifest.artifacts[${index}]`));
  }
  for (const required of [
    "executive_summary.json",
    "acceptance_matrix.csv",
    "chart_map.csv",
    "figure_manifest.json",
    "input_artifact_ledger.csv",
    ...TRUTHFULNESS_ARTIFACTS,
  ]) {
    if (!artifactMap.has(required)) throw new Error(`final_analysis manifest omits ${required}`);
  }

  const figureManifest = await readJson(artifactMap.get("figure_manifest.json"), "figure manifest");
  if (figureManifest.experiment_id !== "E18" || figureManifest.evidence_tier !== "formal_synthesis") {
    throw new Error("figure manifest is not E18 formal_synthesis evidence");
  }
  const figures = new Map();
  for (const [index, figure] of (figureManifest.figures || []).entries()) {
    if (figures.has(figure.id)) throw new Error(`duplicate figure id: ${figure.id}`);
    const png = await verifyLedgerEntry(analysisDir, figure.files?.png, `figures[${index}].files.png`);
    await verifyLedgerEntry(analysisDir, figure.files?.data, `figures[${index}].files.data`);
    await verifyLedgerEntry(analysisDir, figure.files?.svg, `figures[${index}].files.svg`);
    if (!artifactMap.has(figure.files.png.path)) {
      throw new Error(`final_analysis artifact ledger omits figure PNG ${figure.files.png.path}`);
    }
    figures.set(figure.id, { ...figure, png });
  }
  for (const [, left, right] of FIGURE_SLOTS) {
    for (const figureId of [left, right]) {
      if (!figures.has(figureId)) throw new Error(`formal figure is missing: ${figureId}`);
    }
  }

  const executive = await readJson(artifactMap.get("executive_summary.json"), "executive summary");
  if (executive.overall_acceptance_status !== manifest.acceptance_status) {
    throw new Error("executive and final_analysis acceptance statuses disagree");
  }
  const asrReduction = targetById(executive, "A01");
  const dsr = targetById(executive, "A02");
  const fpr = targetById(executive, "A05");
  const auditAnchor = manifest.result_integrity_audit;
  if (!auditAnchor || auditAnchor.snapshot_path !== "result_integrity_audit.json"
      || auditAnchor.source_sha256 !== auditAnchor.snapshot_sha256
      || JSON.stringify(auditAnchor.stages) !== JSON.stringify(["main", "derived", "stability"])) {
    throw new Error("final_analysis has an invalid final result-integrity audit anchor");
  }
  if ((await sha256(artifactMap.get("result_integrity_audit.json"))) !== auditAnchor.source_sha256) {
    throw new Error("result-integrity audit snapshot differs from its manifest anchor");
  }
  const audit = await readJson(artifactMap.get("result_integrity_audit.json"), "result-integrity audit snapshot");
  if (audit.status !== "pass" || JSON.stringify(audit.scope?.stages) !== JSON.stringify(["main", "derived", "stability"])) {
    throw new Error("result-integrity audit snapshot is not a final three-stage pass");
  }
  const parseQuality = await readJson(artifactMap.get("main_parse_quality.json"), "main parse quality");
  validateParseQuality(parseQuality, auditAnchor);
  const e16Provenance = await readJson(artifactMap.get("e16_provenance.json"), "E16 provenance");
  validateE16Provenance(e16Provenance);
  return {
    mode: "formal",
    source: "completed E0-E17 and final_analysis/E18",
    cards: [
      { label: "核心模型 · ASR 相对下降", value: formatPercent(asrReduction.estimate) },
      { label: "full Guard · DSR", value: formatPercent(dsr.estimate) },
      { label: "正常调用 · FPR", value: formatPercent(fpr.estimate) },
    ],
    executive,
    parseQuality,
    e16Provenance,
    figures,
    evidence: {
      registryPath,
      registrySha256: manifest.registry_sha256,
      analysisManifestPath: manifestPath,
      analysisManifestSha256: await sha256(manifestPath),
      inputArtifactCount: manifest.input_artifact_count,
      chartCount: manifest.chart_count,
      resultIntegrityAuditSha256: auditAnchor.source_sha256,
      mainParseQualitySha256: await sha256(artifactMap.get("main_parse_quality.json")),
      e16ProvenanceSha256: await sha256(artifactMap.get("e16_provenance.json")),
    },
  };
}

async function loadFixtureEvidence(fixturePath, fixtureAssets) {
  const fixture = await readJson(fixturePath, "synthetic fixture");
  if (fixture.synthetic !== true) throw new Error("fixture mode requires synthetic=true");
  const figures = new Map();
  for (const [, left, right] of FIGURE_SLOTS) {
    for (const figureId of [left, right]) {
      const png = path.join(fixtureAssets, `${figureId}.png`);
      const stat = await fs.stat(png).catch(() => undefined);
      if (!stat?.isFile() || stat.size <= 0) throw new Error(`synthetic figure is missing: ${png}`);
      figures.set(figureId, { id: figureId, title: `SYNTHETIC ${figureId}`, png });
    }
  }
  const fixtureAnchor = { source_sha256: fixture.main_parse_quality?.source_audit_sha256 };
  validateParseQuality(fixture.main_parse_quality, fixtureAnchor);
  validateE16Provenance(fixture.e16_provenance);
  return {
    mode: "fixture",
    source: "synthetic fixture for layout QA only",
    cards: fixture.cards,
    executive: fixture.executive,
    parseQuality: fixture.main_parse_quality,
    e16Provenance: fixture.e16_provenance,
    figures,
    evidence: { fixturePath, fixtureSha256: await sha256(fixturePath) },
  };
}

function slideAt(presentation, slideNumber) {
  const slide = presentation.slides.getItem(slideNumber - 1);
  if (!slide) throw new Error(`Missing slide ${slideNumber}`);
  return slide;
}

function shapeById(slide, id) {
  const shape = slide.shapes.getById(String(id));
  if (!shape) throw new Error(`Missing inherited shape id=${id}`);
  return shape;
}

function rewrite(slide, id, value) {
  shapeById(slide, id).text.set(String(value));
}

function deleteIds(slide, ids) {
  for (const id of ids) shapeById(slide, id).delete();
}

function range(start, end) {
  return Array.from({ length: end - start + 1 }, (_, index) => start + index);
}

async function addFigure(slide, figure, frame) {
  const bytes = await fs.readFile(figure.png);
  slide.images.add({
    blob: bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength),
    contentType: "image/png",
    name: `formal-${figure.id}`,
    alt: `${figure.title}; source ${figure.id}`,
    fit: "contain",
    position: frame,
  });
}

function applyStaticText(presentation) {
  const slide4 = slideAt(presentation, 4);
  rewrite(slide4, 5, "可信实验闭环：冻结、运行、统计、交付");
  rewrite(slide4, 8, "300 条 canonical 数据先做模板级切分审计，阈值只在 validation 冻结；四个核心模型在 blind test 顺序运行，失败保留在原分母，最终由 registry 与哈希链发布证据。");
  for (const [id, text] of [[10, "300-case Data"], [13, "Blind Freeze"], [16, "4-model Matrix"], [19, "Paired Stats"], [22, "E0–E17 Bundle"], [25, "Report / PPT"]]) rewrite(slide4, id, text);
  rewrite(slide4, 28, "证据门禁");
  rewrite(slide4, 29, "• 同 case / model / prompt / seed 配对；解析失败、拒答、超时不丢分母\n• Stub 仅做确定性回归；正式结论只使用本地真实模型\n• manifest 绑定 Git、数据、阈值、模型 digest 与 artifact SHA-256");

  const slide5 = slideAt(presentation, 5);
  rewrite(slide5, 5, "数据设计：300 条样本覆盖攻击与正常工具任务");
  const cards = [
    [10, "核心注入", 11, "RAG、直注、RPC、工具输出"],
    [14, "状态污染", 15, "记忆与环境上下文污染"],
    [18, "跨工具链", 19, "读发链、检索 API、记忆→文件"],
    [22, "语言变化", 23, "中/英/混合、拼音、繁体、跨语种混淆"],
    [26, "编码规避", 27, "零宽、同形、Base64、拆分与隐藏结构"],
    [30, "正常任务", 31, "45 无工具 + 45 合法工具任务"],
  ];
  for (const [titleId, title, bodyId, body] of cards) {
    rewrite(slide5, titleId, title);
    rewrite(slide5, bodyId, body);
  }
  rewrite(slide5, 32, "210 攻击 + 90 正常；dev 150 / validation 60 / blind 90，同一 template 不跨 split。");
}

async function applyEvidenceSlides(presentation, evidence) {
  const slide1 = slideAt(presentation, 1);
  for (const [labelId, valueId, card] of [[9, 10, evidence.cards[0]], [13, 14, evidence.cards[1]], [17, 18, evidence.cards[2]]]) {
    rewrite(slide1, labelId, card.label);
    rewrite(slide1, valueId, card.value);
  }
  rewrite(slide1, 19, evidence.mode === "formal" ? "完成态 E0–E17 · 冻结盲测 · 真实模型证据" : "SYNTHETIC PREVIEW · 非正式结果 · 仅用于版式 QA");

  const titles = {
    6: "主结果：Guard 与提示加固的增量被独立测量",
    7: "组件与阈值：贡献可消融，操作点在盲测前冻结",
    8: "泛化：跨模型与九类攻击的效果可直接比较",
    9: "鲁棒性：语言规避与自适应多轮趋势单独计量",
    10: "工程与失败：性能边界和人工裁决同时报告",
  };
  const deletionRanges = { 6: [8, 15], 7: [8, 29], 8: [8, 26], 9: [8, 59], 10: [8, 41] };
  for (const [slideNumber, leftId, rightId] of FIGURE_SLOTS) {
    const slide = slideAt(presentation, slideNumber);
    rewrite(slide, 5, titles[slideNumber]);
    const [start, end] = deletionRanges[slideNumber];
    deleteIds(slide, range(start, end));
    await addFigure(slide, evidence.figures.get(leftId), LEFT_FIGURE_FRAME);
    await addFigure(slide, evidence.figures.get(rightId), RIGHT_FIGURE_FRAME);
  }

  const executive = evidence.executive;
  const counts = executive.acceptance_status_counts || { pass: 0, fail: 0, not_evaluable: 0 };
  const failed = (executive.failed_target_ids || []).join("、") || "无";
  const unavailable = (executive.not_evaluable_target_ids || []).join("、") || "无";
  const stepParse = evidence.parseQuality.overall.step_row;
  const runParse = evidence.parseQuality.overall.run;
  const reference = formatPercent(evidence.parseQuality.reference.threshold);
  const belowStep = evidence.parseQuality.models_below_reference.step_row.join("、") || "无";
  const belowRun = evidence.parseQuality.models_below_reference.run.join("、") || "无";
  const e16Runtime = evidence.e16Provenance.runtime_observation.sandbox_runtime_version;
  const slide12 = slideAt(presentation, 12);
  const acceptanceStatus = String(executive.overall_acceptance_status || "unknown").toLowerCase();
  const acceptanceColor = acceptanceStatus === "pass" ? "#2E9E67" : acceptanceStatus === "fail" ? "#E5484D" : "#E58A13";
  rewrite(slide12, 5, "结论：E0–E17 形成可审查的防御证据链");
  rewrite(slide12, 10, `验收结论：${acceptanceStatus.toUpperCase()}`);
  shapeById(slide12, 10).text.color = acceptanceColor;
  rewrite(slide12, 11, `• E0–E17 完成态，主表和 13 组正式图可一键重建（PPT 精选 10 图）\n• 验收：pass=${counts.pass || 0}，fail=${counts.fail || 0}，NA=${counts.not_evaluable || 0}\n• A11 仍为 E1 regular_full；全条件解析完整性在右侧单列`);
  rewrite(slide12, 14, "必须诚实说明");
  rewrite(slide12, 15, `• 全条件 step-row：${formatQualityMetric(stepParse)}\n• 全条件 run-level：${formatQualityMetric(runParse)}\n• 低于 ${reference}（step/run）：${belowStep} / ${belowRun}\n• E16 runtime=${e16Runtime}；独立 validation 分母；排除主矩阵/性能/延迟\n• 零事件报 Wilson 上界；旧 FPR=0/Stub 仅原型\n• fail：${failed}；NA：${unavailable}`);
  rewrite(slide12, 16, "一句话收束：M3-PI Guard 把提示注入风险转化为经过冻结盲测、配对统计和失败复核的可量化、可阻断、可回放工具行为。");
}

async function saveBlob(filePath, blob) {
  await fs.mkdir(path.dirname(filePath), { recursive: true });
  await fs.writeFile(filePath, Buffer.from(await blob.arrayBuffer()));
}

async function exportQa(presentation, previewDir, layoutDir, montagePath) {
  await fs.mkdir(previewDir, { recursive: true });
  await fs.mkdir(layoutDir, { recursive: true });
  for (let index = 0; index < presentation.slides.items.length; index += 1) {
    const slide = presentation.slides.getItem(index);
    const stem = `slide-${String(index + 1).padStart(2, "0")}`;
    await saveBlob(path.join(previewDir, `${stem}.png`), await presentation.export({ slide, format: "png", scale: 1 }));
    const layout = await slide.export({ format: "layout" });
    await fs.writeFile(path.join(layoutDir, `${stem}.layout.json`), await layout.text(), "utf8");
  }
  await saveBlob(montagePath, await presentation.export({ format: "webp", montage: true, scale: 1 }));
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const mode = args.mode || "formal";
  if (!new Set(["formal", "fixture"]).has(mode)) throw new Error(`Unsupported --mode ${mode}`);
  const starterPptxPath = requireArg(args, "starter");
  const templatePptxPath = requireArg(args, "template");
  const outputPptxPath = requireArg(args, "out");
  const previewDir = requireArg(args, "preview-dir");
  const layoutDir = requireArg(args, "layout-dir");
  const montagePath = requireArg(args, "montage");
  const buildManifestPath = requireArg(args, "build-manifest");
  if (outputPptxPath === templatePptxPath || outputPptxPath === starterPptxPath) {
    throw new Error("Output must be a distinct edited copy; refusing in-place template/starter overwrite");
  }

  const evidence = mode === "formal"
    ? await loadFormalEvidence(requireArg(args, "analysis"), requireArg(args, "registry"))
    : await loadFixtureEvidence(requireArg(args, "fixture"), requireArg(args, "fixture-assets"));

  const presentation = await PresentationFile.importPptx(await FileBlob.load(starterPptxPath));
  if (presentation.slides.items.length !== 12) throw new Error(`Expected 12 inherited slides, got ${presentation.slides.items.length}`);
  applyStaticText(presentation);
  await applyEvidenceSlides(presentation, evidence);

  const inspection = await presentation.inspect({ kind: "slide,textbox,shape,image", maxChars: 200000 });
  if (/Qwen2\.5|stub ASR by defense_mode|stub WRS by defense_mode|0\.919/.test(inspection.ndjson)) {
    throw new Error("Legacy Qwen2.5/Stub result copy remains after the targeted edits");
  }
  await fs.writeFile(`${buildManifestPath}.inspect.ndjson`, inspection.ndjson, "utf8");
  await exportQa(presentation, previewDir, layoutDir, montagePath);
  await fs.mkdir(path.dirname(outputPptxPath), { recursive: true });
  const pptx = await PresentationFile.exportPptx(presentation);
  await pptx.save(outputPptxPath);

  const selectedFigures = [];
  for (const [slide, left, right] of FIGURE_SLOTS) {
    for (const figureId of [left, right]) {
      selectedFigures.push({
        slide,
        figure_id: figureId,
        sha256: await sha256(evidence.figures.get(figureId).png),
      });
    }
  }
  const buildManifest = {
    schema_version: "1.0",
    artifact_type: "template_following_presentation_build",
    mode,
    status: "completed",
    generated_at: new Date().toISOString(),
    source: evidence.source,
    template: { path: templatePptxPath, sha256: await sha256(templatePptxPath) },
    starter: { path: starterPptxPath, sha256: await sha256(starterPptxPath) },
    evidence: evidence.evidence,
    selected_figures: selectedFigures,
    output: { path: outputPptxPath, sha256: await sha256(outputPptxPath) },
    qa: { preview_dir: previewDir, layout_dir: layoutDir, montage: montagePath },
  };
  await fs.mkdir(path.dirname(buildManifestPath), { recursive: true });
  await fs.writeFile(buildManifestPath, `${JSON.stringify(buildManifest, null, 2)}\n`, "utf8");
  console.log(JSON.stringify({ status: "completed", mode, output: outputPptxPath, buildManifest: buildManifestPath }, null, 2));
}

main().catch((error) => {
  console.error(error.stack || error.message || String(error));
  process.exitCode = 1;
});
