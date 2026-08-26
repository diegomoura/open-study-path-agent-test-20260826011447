#!/usr/bin/env node
import { createHash } from "node:crypto";
import { createServer } from "node:http";
import { promises as fs, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import process from "node:process";
import { PDFDocument } from "pdf-lib";
import puppeteer from "puppeteer";

const TOOL_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function installedPackageVersion(...segments) {
  const packageJson = path.join(TOOL_ROOT, "node_modules", ...segments, "package.json");
  return JSON.parse(readFileSync(packageJson, "utf8")).version;
}

const PUPPETEER_VERSION = installedPackageVersion("puppeteer");
const MERMAID_VERSION = installedPackageVersion("mermaid");
const PDF_LIB_VERSION = installedPackageVersion("pdf-lib");
const RENDERER_ID = "open-study-path-html-svg-pdf-v3";
const PDF_PRODUCER = "Open Study Path static SVG PDF renderer v3";
const FIXED_PDF_DATE = new Date("2000-01-01T00:00:00.000Z");
const DIAGNOSTIC_ROOT = ".open-study-path/rendered-slides";
const PRINT_OVERRIDE = `
@page { size: 1280px 720px; margin: 0; }
html, body { width: 0 !important; height: 0 !important; min-width: 0 !important; min-height: 0 !important; margin: 0 !important; padding: 0 !important; overflow: visible !important; background: #070910 !important; print-color-adjust: exact !important; -webkit-print-color-adjust: exact !important; }
.osp-slide { display: flex !important; position: fixed !important; inset: 0 auto auto 0 !important; flex-direction: column !important; justify-content: center !important; width: 1280px !important; min-width: 1280px !important; max-width: 1280px !important; height: 720px !important; min-height: 720px !important; max-height: 720px !important; margin: 0 !important; break-inside: avoid-page !important; page-break-inside: avoid !important; box-shadow: none !important; }
`;

function parseArgs(argv) {
  const result = { root: process.cwd(), topics: [], check: false };
  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (value === "--root") result.root = argv[++index];
    else if (value === "--topic") result.topics.push(argv[++index]);
    else if (value === "--check") result.check = true;
    else if (value === "--help") {
      console.log("Usage: node scripts/render_study_slides.mjs [--root PATH] [--topic TOPIC-001] [--check]");
      process.exit(0);
    } else throw new Error(`Unknown argument: ${value}`);
  }
  return result;
}

function sha256(value) { return createHash("sha256").update(value).digest("hex"); }
async function fileHash(file) { return sha256(await fs.readFile(file)); }

async function aggregateHash(root, files) {
  const digest = createHash("sha256");
  for (const file of [...files].sort()) {
    const relative = path.relative(root, file).split(path.sep).join("/");
    digest.update(relative); digest.update("\0"); digest.update(await fileHash(file)); digest.update("\n");
  }
  return digest.digest("hex");
}

function contentType(file) {
  return { ".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml", ".mjs": "text/javascript; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".json": "application/json; charset=utf-8" }[path.extname(file).toLowerCase()] || "application/octet-stream";
}

async function startServer(root) {
  const resolvedRoot = path.resolve(root);
  const mermaidRoot = path.resolve(TOOL_ROOT, "node_modules", "mermaid", "dist");
  const server = createServer(async (request, response) => {
    try {
      const requested = decodeURIComponent(new URL(request.url, "http://127.0.0.1").pathname);
      if (requested === "/__osp_tools__/mermaid-renderer.html") {
        response.writeHead(200, { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff" });
        response.end(`<!doctype html><html><head><meta charset="utf-8"></head><body><div id="render-root"></div><script type="module">import mermaid from "/__osp_tools__/mermaid/mermaid.esm.min.mjs"; window.__OSP_MERMAID__ = mermaid; window.__OSP_MERMAID_READY__ = true;</script></body></html>`);
        return;
      }
      let candidate;
      if (requested.startsWith("/__osp_tools__/mermaid/")) {
        const relative = requested.slice("/__osp_tools__/mermaid/".length);
        candidate = path.resolve(mermaidRoot, relative);
        if (candidate !== mermaidRoot && !candidate.startsWith(`${mermaidRoot}${path.sep}`)) return response.writeHead(403).end("Forbidden");
      } else {
        candidate = path.resolve(resolvedRoot, `.${requested}`);
        if (candidate !== resolvedRoot && !candidate.startsWith(`${resolvedRoot}${path.sep}`)) return response.writeHead(403).end("Forbidden");
      }
      const stat = await fs.stat(candidate);
      const file = stat.isDirectory() ? path.join(candidate, "index.html") : candidate;
      response.writeHead(200, { "Content-Type": contentType(file), "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff" });
      response.end(await fs.readFile(file));
    } catch (error) {
      response.writeHead(error?.code === "ENOENT" ? 404 : 500).end(String(error));
    }
  });
  await new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", resolve);
  });
  return { server, origin: `http://127.0.0.1:${server.address().port}` };
}

async function findTopics(root, selected) {
  if (selected.length) return [...new Set(selected)].sort();
  const slidesRoot = path.join(root, "study", "slides");
  try {
    return (await fs.readdir(slidesRoot, { withFileTypes: true }))
      .filter((entry) => entry.isDirectory() && /^TOPIC-\d{3,}$/.test(entry.name))
      .map((entry) => entry.name).sort();
  } catch (error) { if (error?.code === "ENOENT") return []; throw error; }
}

async function copySourceTree(sourceDir, buildDir) {
  await fs.mkdir(path.join(buildDir, "diagrams"), { recursive: true });
  await fs.copyFile(path.join(sourceDir, "index.html"), path.join(buildDir, "index.html"));
  await fs.copyFile(path.join(sourceDir, "slides.css"), path.join(buildDir, "slides.css"));
}

async function diagramSources(sourceDir) {
  const dir = path.join(sourceDir, "diagrams");
  const entries = await fs.readdir(dir, { withFileTypes: true });
  return entries.filter((entry) => entry.isFile() && entry.name.endsWith(".mmd")).map((entry) => path.join(dir, entry.name)).sort();
}

async function renderDiagrams(browser, origin, root, sourceDir, buildDir) {
  const config = JSON.parse(await fs.readFile(path.join(root, "templates", "study-slides", "mermaid-config.json"), "utf8"));
  const sources = await diagramSources(sourceDir);
  if (!sources.length) throw new Error(`${path.basename(sourceDir)}: no Mermaid sources found`);
  const outputs = [];
  const page = await browser.newPage();
  const consoleErrors = [];
  const externalRequests = [];
  page.on("console", (message) => { if (message.type() === "error") consoleErrors.push(message.text()); });
  page.on("pageerror", (error) => consoleErrors.push(String(error?.stack || error)));
  await page.setRequestInterception(true);
  page.on("request", (request) => {
    const requestUrl = new URL(request.url());
    if (requestUrl.origin !== origin) {
      externalRequests.push(request.url());
      request.abort("blockedbyclient");
    } else request.continue();
  });
  try {
    await page.goto(`${origin}/__osp_tools__/mermaid-renderer.html`, { waitUntil: "networkidle0" });
    await page.waitForFunction(() => window.__OSP_MERMAID_READY__ === true, { timeout: 30_000 });
    for (let index = 0; index < sources.length; index += 1) {
      const source = sources[index];
      const sourceText = await fs.readFile(source, "utf8");
      const diagramId = `osp-${sha256(Buffer.from(`${path.basename(sourceDir)}:${index}:${sourceText}`, "utf8")).slice(0, 16)}`;
      const value = await page.evaluate(async ({ sourceText, diagramId, config }) => {
        const mermaid = window.__OSP_MERMAID__;
        mermaid.initialize({ ...config, startOnLoad: false, deterministicIDSeed: `${config.deterministicIDSeed || "open-study-path"}:${diagramId}` });
        const { svg } = await mermaid.render(diagramId, sourceText, document.querySelector("#render-root"));
        document.querySelector("#render-root").replaceChildren();
        return svg;
      }, { sourceText, diagramId, config });
      if (!value.includes("<svg") || value.toLowerCase().includes("<script")) throw new Error(`${path.basename(sourceDir)}: unsafe or invalid Mermaid SVG`);
      const output = path.join(buildDir, "diagrams", `${path.basename(source, ".mmd")}.svg`);
      await fs.writeFile(output, value, "utf8");
      outputs.push(output);
    }
  } finally {
    await page.close();
  }
  if (consoleErrors.length) throw new Error(`${path.basename(sourceDir)}: Mermaid browser errors: ${consoleErrors.join(" | ")}`);
  if (externalRequests.length) throw new Error(`${path.basename(sourceDir)}: Mermaid requested external resources: ${externalRequests.join(" | ")}`);
  return { sources, outputs };
}

async function readMetaTags(page) {
  return page.evaluate(() => ({
    topicId: document.querySelector('meta[name="open-study-path:topic-id"]')?.content || "",
    contentVersion: Number(document.querySelector('meta[name="open-study-path:content-version"]')?.content || ""),
    theme: document.querySelector('meta[name="open-study-path:slide-theme"]')?.content || "",
  }));
}

async function diagnostics(page) {
  return page.evaluate(() => {
    const slides = Array.from(document.querySelectorAll(".osp-slide"));
    const overflowSlides = slides.map((slide, index) => ({ index: index + 1, horizontal: slide.scrollWidth > slide.clientWidth + 1, vertical: slide.scrollHeight > slide.clientHeight + 1 }))
      .filter((item) => item.horizontal || item.vertical).map((item) => item.index);
    const missingDiagrams = Array.from(document.querySelectorAll("img.osp-diagram-image")).map((image, index) => ({ index: index + 1, complete: image.complete, width: image.naturalWidth }))
      .filter((item) => !item.complete || item.width <= 0).map((item) => item.index);
    const outcomeIds = [];
    for (const slide of slides) for (const value of (slide.dataset.outcomeIds || "").split(/\s+/).filter(Boolean)) if (!outcomeIds.includes(value)) outcomeIds.push(value);
    return { slideCount: slides.length, diagramCount: document.querySelectorAll("img.osp-diagram-image").length, overflowSlides, missingDiagrams, outcomeIds };
  });
}

async function snapshotDeck(page) {
  return page.evaluate(async () => ({
    styles: Array.from(document.styleSheets).flatMap((sheet) => { try { return Array.from(sheet.cssRules, (rule) => rule.cssText); } catch { return []; } }).join("\n"),
    slides: await Promise.all(Array.from(document.querySelectorAll(".osp-slide"), async (slide) => {
      const clone = slide.cloneNode(true);
      const originalImages = Array.from(slide.querySelectorAll("img"));
      const clonedImages = Array.from(clone.querySelectorAll("img"));
      for (let index = 0; index < clonedImages.length; index += 1) {
        const response = await fetch(originalImages[index].src);
        if (!response.ok) throw new Error(`Could not load slide image: ${originalImages[index].src}`);
        const svg = await response.text();
        clonedImages[index].setAttribute("src", `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`);
      }
      return clone.outerHTML;
    })),
  }));
}

function normalizeSnapshot(value) {
  return value.replace(/\s+id="[^"]*"/g, "").replace(/url\(#[^)]+\)/g, "url(#normalized)").replace(/\s+(?:aria-labelledby|aria-describedby)="[^"]*"/g, "").replace(/\s+/g, " ").trim();
}
function snapshotHash(snapshot) { return sha256(Buffer.from(JSON.stringify({ styles: snapshot.styles.replace(/\s+/g, " ").trim(), slides: snapshot.slides.map(normalizeSnapshot) }), "utf8")); }
function expectedSubject(sourceDigest, renderedDigest) { return `open-study-path-renderer:${RENDERER_ID};source:${sourceDigest};snapshot:${renderedDigest}`; }

async function renderSinglePage(page, styles, slideHtml, index) {
  await page.setContent(`<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><style>${styles}\n${PRINT_OVERRIDE}</style></head><body>${slideHtml}</body></html>`, { waitUntil: "load" });
  await page.evaluate(async () => { await document.fonts.ready; await Promise.all(Array.from(document.images, (image) => image.decode())); });
  const bytes = await page.pdf({ width: "1280px", height: "720px", printBackground: true, preferCSSPageSize: true, margin: { top: "0", right: "0", bottom: "0", left: "0" } });
  const pdf = await PDFDocument.load(bytes, { ignoreEncryption: true });
  if (pdf.getPageCount() !== 1) throw new Error(`slide ${index + 1} rendered as ${pdf.getPageCount()} PDF pages`);
  return pdf;
}

async function renderDeckPdf(browser, snapshot, topic, sourceDigest, renderedDigest) {
  const printPage = await browser.newPage();
  await printPage.setViewport({ width: 1280, height: 720, deviceScaleFactor: 1 });
  await printPage.emulateMediaType("print");
  const merged = await PDFDocument.create();
  try {
    for (let index = 0; index < snapshot.slides.length; index += 1) {
      const source = await renderSinglePage(printPage, snapshot.styles, snapshot.slides[index], index);
      const [copied] = await merged.copyPages(source, [0]); merged.addPage(copied);
    }
  } finally { await printPage.close(); }
  merged.setProducer(PDF_PRODUCER); merged.setCreator(PDF_PRODUCER); merged.setTitle(`${topic} study slides`);
  merged.setSubject(expectedSubject(sourceDigest, renderedDigest)); merged.setKeywords(["open-study-path", RENDERER_ID, topic, sourceDigest, renderedDigest]);
  merged.setCreationDate(FIXED_PDF_DATE); merged.setModificationDate(FIXED_PDF_DATE);
  return Buffer.from(await merged.save({ useObjectStreams: false }));
}

async function sourceMetadata(root, topicDir, mmdSources) {
  const files = [path.join(topicDir, "index.html"), path.join(topicDir, "slides.css"), ...mmdSources];
  const sourceSha256 = {};
  for (const file of files) sourceSha256[path.relative(root, file).split(path.sep).join("/")] = await fileHash(file);
  return { files, sourceSha256, sourceDigest: await aggregateHash(root, files) };
}

async function inspectPdf(bytes) { const pdf = await PDFDocument.load(bytes, { ignoreEncryption: true }); return { pages: pdf.getPageCount() }; }

async function artifactsMatch(topicDir, buildDir, meta) {
  try {
    const committedMeta = JSON.parse(await fs.readFile(path.join(topicDir, "slides.meta.json"), "utf8"));
    const committedPdf = await fs.readFile(path.join(topicDir, "slides.pdf"));
    if (JSON.stringify(committedMeta) !== JSON.stringify(meta) || sha256(committedPdf) !== meta.pdf.sha256) return false;
    for (const [relative, expected] of Object.entries(meta.svg_sha256)) {
      const committed = path.join(path.dirname(path.dirname(topicDir)), "..", relative);
      if (await fileHash(path.resolve(committed)) !== expected) return false;
    }
    return true;
  } catch { return false; }
}

async function publishArtifacts(topicDir, buildDir) {
  await fs.mkdir(path.join(topicDir, "diagrams"), { recursive: true });
  for (const entry of await fs.readdir(path.join(buildDir, "diagrams"))) if (entry.endsWith(".svg")) await fs.copyFile(path.join(buildDir, "diagrams", entry), path.join(topicDir, "diagrams", entry));
  await fs.copyFile(path.join(buildDir, "slides.pdf"), path.join(topicDir, "slides.pdf"));
  await fs.copyFile(path.join(buildDir, "slides.meta.json"), path.join(topicDir, "slides.meta.json"));
}

async function renderTopic({ browser, root, origin, topic, check }) {
  const topicDir = path.join(root, "study", "slides", topic);
  const buildDir = path.join(root, DIAGNOSTIC_ROOT, topic);
  await fs.rm(buildDir, { recursive: true, force: true }); await copySourceTree(topicDir, buildDir);
  const diagrams = await renderDiagrams(browser, origin, root, topicDir, buildDir);
  const consoleErrors = []; const externalRequests = [];
  const page = await browser.newPage(); await page.setViewport({ width: 1280, height: 720, deviceScaleFactor: 1 });
  page.on("console", (message) => { if (message.type() === "error") consoleErrors.push(message.text()); });
  page.on("pageerror", (error) => consoleErrors.push(String(error?.stack || error)));
  await page.setRequestInterception(true);
  page.on("request", (request) => { const url = new URL(request.url()); if (url.origin !== origin) { externalRequests.push(request.url()); request.abort("blockedbyclient"); } else request.continue(); });
  await page.goto(`${origin}/${topic}/index.html`, { waitUntil: "networkidle0" });
  await page.evaluate(async () => { await document.fonts.ready; await Promise.all(Array.from(document.images, (image) => image.decode())); });
  const tags = await readMetaTags(page);
  if (tags.topicId !== topic || !Number.isInteger(tags.contentVersion) || tags.contentVersion <= 0 || tags.theme !== "canonical-v3") throw new Error(`${topic}: invalid HTML metadata`);
  const browserDiagnostics = await diagnostics(page);
  if (browserDiagnostics.overflowSlides.length) throw new Error(`${topic}: overflowing slides: ${browserDiagnostics.overflowSlides.join(", ")}`);
  if (browserDiagnostics.missingDiagrams.length) throw new Error(`${topic}: missing diagrams: ${browserDiagnostics.missingDiagrams.join(", ")}`);
  if (consoleErrors.length) throw new Error(`${topic}: browser console errors: ${consoleErrors.join(" | ")}`);
  if (externalRequests.length) throw new Error(`${topic}: external requests are forbidden: ${externalRequests.join(" | ")}`);
  const snapshot = await snapshotDeck(page); await page.close();
  const source = await sourceMetadata(root, topicDir, diagrams.sources);
  const renderedSnapshotSha256 = snapshotHash(snapshot);
  const pdfBuffer = await renderDeckPdf(browser, snapshot, topic, source.sourceDigest, renderedSnapshotSha256);
  const pdfInfo = await inspectPdf(pdfBuffer);
  if (pdfInfo.pages !== browserDiagnostics.slideCount) throw new Error(`${topic}: PDF page count does not match slide count`);
  await fs.writeFile(path.join(buildDir, "slides.pdf"), pdfBuffer);
  const svgSha256 = {};
  for (const output of diagrams.outputs) {
    const relative = path.join("study", "slides", topic, "diagrams", path.basename(output)).split(path.sep).join("/");
    svgSha256[relative] = await fileHash(output);
  }
  const meta = {
    contract_version: 3, topic_id: topic, content_version: tags.contentVersion,
    renderer: { id: RENDERER_ID, puppeteer: PUPPETEER_VERSION, mermaid: MERMAID_VERSION, pdf_lib: PDF_LIB_VERSION, strategy: "localhost_static_svg_isolated_page_merge" },
    slide_count: browserDiagnostics.slideCount, diagram_count: browserDiagnostics.diagramCount, outcome_ids: browserDiagnostics.outcomeIds,
    source_sha256: source.sourceSha256, source_digest: source.sourceDigest, svg_sha256: svgSha256, rendered_snapshot_sha256: renderedSnapshotSha256,
    pdf: { pages: pdfInfo.pages, bytes: pdfBuffer.length, sha256: sha256(pdfBuffer), producer: PDF_PRODUCER },
    diagnostics: { console_errors: [], overflow_slides: [], external_requests: [], missing_diagrams: [] },
  };
  await fs.writeFile(path.join(buildDir, "slides.meta.json"), `${JSON.stringify(meta, null, 2)}\n`);
  if (check) {
    if (!(await artifactsMatch(topicDir, buildDir, meta))) throw new Error(`${topic}: committed SVG/PDF artifacts are missing or stale; generated output is in ${path.relative(root, buildDir)}`);
    await fs.rm(buildDir, { recursive: true, force: true });
    return { topic, status: "checked" };
  }
  await publishArtifacts(topicDir, buildDir); await fs.rm(buildDir, { recursive: true, force: true });
  return { topic, status: "rendered" };
}

async function main() {
  const args = parseArgs(process.argv.slice(2)); const root = path.resolve(args.root); const topics = await findTopics(root, args.topics);
  if (!topics.length) { console.log("No materialized study-slide sources found."); return; }
  await fs.rm(path.join(root, DIAGNOSTIC_ROOT), { recursive: true, force: true });
  const { server, origin } = await startServer(path.join(root, DIAGNOSTIC_ROOT));
  const browser = await puppeteer.launch({ headless: "shell", args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage", "--font-render-hinting=none"] });
  try { for (const topic of topics) { const result = await renderTopic({ browser, root, origin, topic, check: args.check }); console.log(`${result.topic}: ${result.status}`); } }
  finally { await browser.close(); await new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve())); }
}

main().catch((error) => { console.error(`ERROR: ${error?.stack || error}`); process.exit(1); });
