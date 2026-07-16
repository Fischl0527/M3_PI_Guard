import fs from "node:fs/promises";
import path from "node:path";
import { Presentation } from "@oai/artifact-tool";

const FIGURES = [
  "main_defense_effect",
  "prompt_guard_increment",
  "guard_ablation",
  "threshold_calibration",
  "cross_model_heatmap",
  "family_robustness",
  "language_evasion",
  "multiturn_adaptive_trends",
  "performance_profile",
  "failure_taxonomy",
];

function parseArgs(argv) {
  const result = {};
  for (let index = 0; index < argv.length; index += 1) {
    const key = argv[index];
    if (!key.startsWith("--")) throw new Error(`Unexpected argument: ${key}`);
    result[key.slice(2)] = argv[index + 1];
    index += 1;
  }
  return result;
}

function addText(slide, text, position, style) {
  const shape = slide.shapes.add({
    geometry: "textbox",
    position,
    fill: "none",
    line: { style: "solid", fill: "none", width: 0 },
  });
  shape.text = text;
  shape.text.fontSize = style.fontSize;
  shape.text.typeface = "Microsoft YaHei";
  shape.text.color = style.color;
  shape.text.bold = Boolean(style.bold);
  return shape;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const outDir = path.resolve(args["out-dir"] || "fixture-charts");
  await fs.mkdir(outDir, { recursive: true });
  const presentation = Presentation.create({ slideSize: { width: 960, height: 600 } });
  for (let index = 0; index < FIGURES.length; index += 1) {
    const figureId = FIGURES[index];
    const slide = presentation.slides.add();
    slide.background.fill = "#FFFFFF";
    addText(slide, figureId.replaceAll("_", " "), { left: 50, top: 36, width: 840, height: 54 }, { fontSize: 30, color: "#172033", bold: true });
    addText(slide, "SYNTHETIC PREVIEW — values are not experimental evidence", { left: 50, top: 94, width: 840, height: 34 }, { fontSize: 17, color: "#D94C4C", bold: true });
    slide.charts.add(index % 3 === 0 ? "line" : "bar", {
      position: { left: 66, top: 150, width: 828, height: 330 },
      categories: ["A", "B", "C", "D"],
      series: [
        { name: "baseline", values: [72 - index, 58, 43 + (index % 5), 31], fill: "#D94C4C" },
        { name: "full Guard", values: [19, 16 + (index % 4), 12, 8 + (index % 3)], fill: "#2E9D63" },
      ],
      hasLegend: true,
      dataLabels: { showValue: true, position: "outEnd" },
      yAxis: { majorGridlines: { style: "solid", fill: "#D9E1EA", width: 1 } },
    });
    addText(slide, "仅用于模板继承、裁切、字体与重叠检查", { left: 50, top: 530, width: 840, height: 30 }, { fontSize: 16, color: "#5D6978", bold: false });
  }
  for (let index = 0; index < FIGURES.length; index += 1) {
    const slide = presentation.slides.getItem(index);
    const png = await presentation.export({ slide, format: "png", scale: 1 });
    await fs.writeFile(path.join(outDir, `${FIGURES[index]}.png`), Buffer.from(await png.arrayBuffer()));
  }
  console.log(JSON.stringify({ status: "completed", synthetic: true, outDir, count: FIGURES.length }, null, 2));
}

main().catch((error) => {
  console.error(error.stack || error.message || String(error));
  process.exitCode = 1;
});
