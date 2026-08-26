#!/usr/bin/env node
import { execFile } from "node:child_process";
import { access, cp, mkdtemp, mkdir, readFile, readdir, rm, symlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import process from "node:process";
import { promisify } from "node:util";
import { fileURLToPath } from "node:url";
import { PDFDocument } from "pdf-lib";

const execFileAsync = promisify(execFile);
const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const PDF_PRODUCER = "Open Study Path static SVG PDF renderer v3";
function assert(condition, message) { if (!condition) throw new Error(message); }

async function exists(target) {
  try { await access(target); return true; }
  catch { return false; }
}

async function filesUnder(root) {
  const entries = await readdir(root, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const target = path.join(root, entry.name);
    if (entry.isDirectory()) files.push(...await filesUnder(target));
    else files.push(target);
  }
  return files;
}

async function runRenderer(root, ...args) {
  const renderer = path.join(REPO_ROOT, "scripts", "render_study_slides.mjs");
  const { stdout, stderr } = await execFileAsync(process.execPath, [renderer, "--root", root, "--topic", "TOPIC-000", ...args], {
    cwd: REPO_ROOT, timeout: 180_000, maxBuffer: 8 * 1024 * 1024,
  });
  if (stdout) process.stdout.write(stdout); if (stderr) process.stderr.write(stderr);
}

async function main() {
  const root = await mkdtemp(path.join(tmpdir(), "open-study-path-new-instance-"));
  try {
    const topicDir = path.join(root, "study", "slides", "TOPIC-000");
    const modulePath = path.join(root, "study", "modules", "TOPIC-000.md");
    const instancePath = path.join(root, ".open-study-path", "instance.yml");

    await mkdir(path.dirname(topicDir), { recursive: true });
    await cp(path.join(REPO_ROOT, "templates", "study-slides"), topicDir, { recursive: true });
    await mkdir(path.join(root, "templates"), { recursive: true });
    await cp(path.join(REPO_ROOT, "templates", "study-slides"), path.join(root, "templates", "study-slides"), { recursive: true });
    await mkdir(path.dirname(instancePath), { recursive: true });
    await cp(path.join(REPO_ROOT, "templates", "instance.yml"), instancePath);
    await mkdir(path.dirname(modulePath), { recursive: true });
    await writeFile(modulePath, `# Aula mínima\n\n[Baixe os slides da aula em PDF](https://github.com/example/new-course/raw/HEAD/study/slides/TOPIC-000/slides.pdf).\n`, "utf8");
    await symlink(path.join(REPO_ROOT, "node_modules"), path.join(root, "node_modules"), "dir");

    await runRenderer(root);

    const pdfPath = path.join(topicDir, "slides.pdf");
    const metaPath = path.join(topicDir, "slides.meta.json");
    const svgPath = path.join(topicDir, "diagrams", "flow.svg");
    const pdf = await readFile(pdfPath);
    const meta = JSON.parse(await readFile(metaPath, "utf8"));
    const svg = await readFile(svgPath, "utf8");
    const sourceHtml = await readFile(path.join(topicDir, "index.html"), "utf8");
    const instance = await readFile(instancePath, "utf8");
    const module = await readFile(modulePath, "utf8");
    const document = await PDFDocument.load(pdf, { ignoreEncryption: true });
    const topicFiles = await filesUnder(topicDir);

    assert(instance.includes("contract_version: 3"), "new instances must use slide contract v3");
    assert(instance.includes("learner_format: pdf"), "new instances must expose PDF to learners");
    assert(instance.includes("document_name: slides.pdf"), "new instances must name the learner document slides.pdf");
    assert(instance.includes("html_visibility: internal_only"), "new instances must keep HTML internal");
    assert(instance.includes("diagram_render_format: svg"), "new instances must render diagrams as SVG");
    assert(instance.includes("generated_images_enabled: false"), "new instances must not require generated raster images");
    assert(module.includes("/slides.pdf"), "new-instance lesson link must target slides.pdf");
    assert(!module.includes("slides.zip"), "new-instance lesson link must not target ZIP");
    assert(sourceHtml.includes('data-mermaid-source="diagrams/flow.mmd"'), "slide source must retain Mermaid provenance");
    assert(!sourceHtml.toLowerCase().includes("<script"), "slide source must not require learner-side JavaScript");
    assert(svg.includes("<svg"), "renderer did not produce SVG");
    assert(!svg.toLowerCase().includes("<script"), "renderer SVG contains script");
    assert(pdf.subarray(0, 5).toString("ascii") === "%PDF-", "renderer PDF header is invalid");
    assert(!(await exists(path.join(topicDir, "slides.zip"))), "new instances must not produce slides.zip");
    assert(!(await exists(path.join(topicDir, "slides.js"))), "new instances must not produce slides.js");
    assert(!topicFiles.some((file) => file.toLowerCase().endsWith(".png")), "new instances must not produce PNG diagrams");
    assert(meta.contract_version === 3, "renderer metadata contract mismatch");
    assert(meta.renderer.id === "open-study-path-html-svg-pdf-v3", "renderer id mismatch");
    assert(meta.slide_count === 12, "renderer slide count mismatch");
    assert(meta.diagram_count >= 1, "renderer diagram count mismatch");
    assert(meta.pdf.pages === meta.slide_count, "renderer PDF page count mismatch");
    assert(meta.pdf.producer === PDF_PRODUCER, "renderer PDF producer mismatch");
    assert(document.getTitle() === "TOPIC-000 study slides", "embedded title mismatch");
    assert(document.getSubject().includes(meta.source_digest), "PDF subject is not bound to source digest");
    assert(meta.diagnostics.console_errors.length === 0, "renderer console errors are not clean");
    assert(meta.diagnostics.overflow_slides.length === 0, "renderer overflow diagnostics are not clean");
    await runRenderer(root, "--check");
    console.log("New-instance static Mermaid SVG and deterministic PDF acceptance test passed.");
  } finally { await rm(root, { recursive: true, force: true }); }
}

main().catch((error) => { console.error(`ERROR: ${error?.stack || error}`); process.exit(1); });
