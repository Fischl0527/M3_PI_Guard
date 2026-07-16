import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const [sourcePptx, outputNdjson] = process.argv.slice(2).map((value) => path.resolve(value));
if (!sourcePptx || !outputNdjson) {
  throw new Error("Usage: node expand_template_inspect.mjs <source.pptx> <template-inspect.ndjson>");
}
const presentation = await PresentationFile.importPptx(await FileBlob.load(sourcePptx));
const inspection = await presentation.inspect({
  kind: "slide,textbox,shape,image,table,chart",
  maxChars: 500000,
});
if (inspection.truncated || inspection.metadata?.truncated) {
  throw new Error("Artifact Tool template inspection is still truncated at 500000 characters");
}
const slideRecords = inspection.ndjson.split(/\r?\n/).filter((line) => line.includes('"kind":"slide"')).length;
if (slideRecords !== 12) throw new Error(`Expected 12 slide records, got ${slideRecords}`);
await fs.mkdir(path.dirname(outputNdjson), { recursive: true });
await fs.writeFile(outputNdjson, `${inspection.ndjson.trim()}\n`, "utf8");
console.log(JSON.stringify({ status: "completed", slideRecords, outputNdjson }, null, 2));
