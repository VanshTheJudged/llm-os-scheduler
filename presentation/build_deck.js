// Build presentation/final_presentation.pptx, presentation_outline.md and speaker_notes.md.
//
// Every number on the slides comes from presentation/deck_data.json, which
// presentation/build_data.py extracts from experiments/results/analysis/.
//
//   npm install pptxgenjs@3.12.0            (once, anywhere; then point NODE_PATH at it)
//   python presentation/build_data.py
//   node presentation/build_deck.js
//
// Optional: set APPLY_THEME_JS to a theme-writer module exporting applyTheme(file, theme)
// so the deck's theme palette matches the colours below (shapes use explicit hex either way).

const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");

const HERE = __dirname;
const D = JSON.parse(fs.readFileSync(path.join(HERE, "deck_data.json"), "utf8"));

// ---------------------------------------------------------------- palette / theme
const COL = {
  ink: "1B2430", slate: "3A4654", muted: "5B6470", line: "C3C9D1", grid: "E3E6EA",
  panel: "EEF1F5", white: "FFFFFF", sjf: "EB6834", fcfs: "2A78D6", oracle: "1BAF7A",
  grey: "8A93A0", soft: "C9D3DE", good: "0C8A0C",
};
const THEME = {
  name: "LLM Scheduling Study", headFontFace: "Cambria", bodyFontFace: "Calibri",
  colors: { dk1: COL.ink, lt1: COL.white, dk2: COL.slate, lt2: COL.panel, accent1: COL.sjf, accent2: COL.fcfs,
            accent3: COL.oracle, accent4: COL.grey, accent5: "6250D6", accent6: "E34948", hlink: COL.fcfs, folHlink: "6250D6" },
};
const FOOTER = "OS-inspired LLM scheduling · simulation study · all results simulated, not GPU measurements";

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.333 x 7.5 in
pres.title = "OS-Inspired Scheduling for LLM Inference Requests";
pres.subject = "Final-year project review: FCFS vs predictive SJF (simulation study)";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };

pres.defineSlideMaster({
  title: "TITLE_DARK",
  background: { color: COL.ink },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.8, y: 1.55, w: 11.7, h: 1.6, fontSize: 40, bold: true, color: COL.white, valign: "bottom", align: "left", margin: 0 }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: 0.8, y: 3.3, w: 11.7, h: 0.9, fontSize: 20, color: COL.soft, valign: "top", margin: 0 }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "CONTENT",
  background: { color: COL.white },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.35, w: 12.1, h: 0.8, fontSize: 30, bold: true, color: COL.ink, valign: "middle", align: "left", margin: 0 }, text: "" } },
    { text: { text: FOOTER, options: { x: 0.6, y: 7.02, w: 10.5, h: 0.3, fontSize: 10, color: COL.muted, margin: 0 } } },
  ],
  slideNumber: { x: 12.2, y: 7.02, w: 0.5, h: 0.3, fontSize: 10, color: COL.muted, align: "right" },
});
pres.defineSlideMaster({
  title: "CLOSING_DARK",
  background: { color: COL.ink },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.35, w: 12.1, h: 0.8, fontSize: 30, bold: true, color: COL.white, valign: "middle", align: "left", margin: 0 }, text: "" } },
  ],
  slideNumber: { x: 12.2, y: 7.02, w: 0.5, h: 0.3, fontSize: 10, color: COL.soft, align: "right" },
});

// ---------------------------------------------------------------- helpers
const outline = [];
const notesMd = [];
let n = 0;

function newSlide(master, section, title, notes, outlineBullets) {
  n += 1;
  const s = pres.addSlide({ masterName: master, sectionTitle: section });
  s.addText(title, { placeholder: "title" });
  s.addNotes(notes);
  outline.push(`## Slide ${n}: ${title}\n\n${outlineBullets.map((b) => `- ${b}`).join("\n")}\n`);
  notesMd.push(`### Slide ${n}: ${title}\n\n${notes}\n`);
  return s;
}

function text(s, t, o) {
  s.addText(t, { isTextBox: true, margin: 0, color: COL.ink, fontSize: 16, valign: "top", ...o });
}

function badge(s, x, y, label, fill, name, d = 0.42, fontSize = 15) {
  s.addText(label, { shape: pres.shapes.OVAL, x, y, w: d, h: d, fill: { color: fill }, line: { color: fill },
    color: COL.white, bold: true, fontSize, align: "center", valign: "middle", margin: 0, objectName: name });
}

function card(s, x, y, w, h, name, opts = {}) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.08, fill: { color: opts.fill || COL.panel },
    line: opts.dashed ? { color: COL.grey, width: 1.25, dashType: "dash" } : { color: opts.fill || COL.panel, width: 0.5 },
    objectName: name });
}

function stat(s, x, y, w, value, label, name, valueColor = COL.ink) {
  card(s, x, y, w, 1.12, name + " card");
  text(s, value, { x: x + 0.2, y: y + 0.1, w: w - 0.4, h: 0.55, fontSize: 28, bold: true, color: valueColor, objectName: name + " value" });
  text(s, label, { x: x + 0.2, y: y + 0.64, w: w - 0.4, h: 0.42, fontSize: 13, color: COL.muted, objectName: name + " label" });
}

const AX = { catAxisLabelColor: COL.muted, valAxisLabelColor: COL.muted, catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt",
  catAxisLabelFontSize: 12, valAxisLabelFontSize: 12, valGridLine: { color: COL.grid, size: 1 }, catGridLine: { style: "none" },
  legendFontFace: "+mn-lt", legendFontSize: 12, legendColor: COL.muted, titleFontFace: "+mn-lt", titleFontSize: 14, titleColor: COL.ink,
  dataLabelFontFace: "+mn-lt", dataLabelFontSize: 11, dataLabelColor: COL.slate, valAxisTitleColor: COL.muted, catAxisTitleColor: COL.muted,
  valAxisTitleFontSize: 12, catAxisTitleFontSize: 12, valAxisTitleFontFace: "+mn-lt", catAxisTitleFontFace: "+mn-lt", catAxisLineShow: true, valAxisLineShow: false };

const pct = (v) => `${v.toFixed(1)}%`;
const SUP = { "-": "⁻", 0: "⁰", 1: "¹", 2: "²", 3: "³", 4: "⁴", 5: "⁵", 6: "⁶", 7: "⁷", 8: "⁸", 9: "⁹" };
const sci = (x) => { const [m, e] = x.toExponential(1).split("e"); return `${m} × 10${String(Number(e)).split("").map((c) => SUP[c]).join("")}`; };
const NB = "\u00a0"; // non-breaking space keeps "rho = 0.8" on one line
const f1 = (v) => v.toFixed(1);
const e2 = D.exp2a.at08;

// ================================================================ 1. Title
pres.addSection({ title: "Introduction" });
{
  n += 1;
  const s = pres.addSlide({ masterName: "TITLE_DARK", sectionTitle: "Introduction" });
  const t = "OS-Inspired Scheduling for LLM Inference Requests";
  s.addText(t, { placeholder: "title" });
  s.addText("Predictive Shortest-Job-First vs FCFS using output-length prediction: a validated simulation study", { placeholder: "body" });
  text(s, "Final-year B.Tech project review · October 2026", { x: 0.8, y: 4.35, w: 8, h: 0.4, fontSize: 16, color: COL.grey, objectName: "occasion" });
  // Motif: requests as chips whose width is their length; FCFS order vs SJF order.
  const lens = [2.4, 0.35, 1.3, 0.5, 0.3, 0.9];
  const rows = [["FCFS: arrival order", lens], ["SJF: shortest predicted first", [...lens].sort((a, b) => a - b)]];
  rows.forEach(([label, arr], r) => {
    const y = 5.35 + r * 0.62;
    text(s, label, { x: 0.8, y: y + 0.05, w: 3.2, h: 0.35, fontSize: 14, color: COL.soft, objectName: `motif label ${r}` });
    let x = 4.1;
    arr.forEach((w, i) => {
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h: 0.42, rectRadius: 0.06, fill: { color: w <= 0.5 ? COL.sjf : COL.slate },
        line: { color: COL.ink, width: 1 }, objectName: `motif chip ${r}-${i}` });
      x += w + 0.08;
    });
  });
  const notes = "Introduce the project in one sentence: we ask whether ordering LLM requests by a predicted output length, the way an operating system orders CPU jobs by burst length, makes requests finish sooner than first-come-first-served, and what it costs. The chips show the idea: the same six requests, wide ones are long generations, orange ones are short. Under FCFS the short ones queue behind the long one; SJF moves them forward. Say up front that everything is a simulation study.";
  s.addNotes(notes);
  outline.push(`## Slide 1: ${t}\n\n- Predictive Shortest-Job-First vs FCFS using output-length prediction: a validated simulation study\n- Final-year B.Tech project review · October 2026 (team and supervisor names to be added by the authors)\n- Visual: six request chips in FCFS order vs SJF order\n`);
  notesMd.push(`### Slide 1: ${t}\n\n${notes}\n`);
}

// ================================================================ 2. Motivation
{
  const s = newSlide("CONTENT", "Introduction", "Under FCFS, short requests wait behind long ones",
    "An LLM generates one token per step, so a request's service time grows with its output length, which ranges from a handful of tokens to thousands. vLLM's paper states it serves requests first-come-first-served. The worked example on the right is the hand-calculated case from Experiment 1: four requests, one second per token. Under FCFS, the two short requests R2 and R3 wait behind R1. Under SJF they go first: mean completion time drops from 6.75 to 6.00 seconds, but R1, the longest of the waiting requests, now waits 7 seconds instead of 4. That trade-off — faster on average, slower for long jobs — is the whole story of the project.",
    ["Service time grows with output length (one token per model step)", "vLLM admits requests FCFS (Kwon et al., SOSP 2023)", "Worked example (EXP1): mean JCT 6.75 s under FCFS vs 6.00 s under SJF; same finish time 11 s", "Cost: the longest waiting request (R1) waits 7 s instead of 4 s"]);
  text(s, [
    { text: "One token per model step: generation time grows with output length", options: { bullet: true, breakLine: true } },
    { text: "Output lengths span a few tokens to thousands", options: { bullet: true, breakLine: true } },
    { text: "vLLM admits waiting requests first-come, first-served", options: { bullet: true, breakLine: true } },
    { text: "OS answer to the same convoy effect: Shortest-Job-First, with aging against starvation", options: { bullet: true } },
  ], { x: 0.6, y: 1.55, w: 5.4, h: 3.6, fontSize: 17, paraSpaceAfter: 10, objectName: "motivation bullets" });
  text(s, "Kwon et al., Efficient Memory Management for LLM Serving with PagedAttention, SOSP 2023.", { x: 0.6, y: 6.45, w: 5.6, h: 0.4, fontSize: 10, color: COL.muted, objectName: "citation" });

  // Gantt of the hand example (EXP1): prefill 1 s + decode 1 s/token => service = n s.
  const x0 = 6.95, sc = 0.5, h = 0.55;
  const fc = [["R0", 0, 5], ["R1", 5, 8], ["R2", 8, 9], ["R3", 9, 11]];
  const sj = [["R0", 0, 5], ["R2", 5, 6], ["R3", 6, 8], ["R1", 8, 11]];
  const short = new Set(["R2", "R3"]);
  [["FCFS", fc, 2.05, "mean JCT 6.75 s"], ["SJF", sj, 3.55, "mean JCT 6.00 s"]].forEach(([lab, blocks, y, m]) => {
    text(s, lab, { x: x0 - 0.8, y: y + 0.1, w: 0.7, h: 0.35, fontSize: 15, bold: true, objectName: `${lab} row label` });
    blocks.forEach(([r, a, b]) => {
      s.addText(r, { shape: pres.shapes.RECTANGLE, x: x0 + a * sc, y, w: (b - a) * sc - 0.04, h, fill: { color: short.has(r) ? COL.sjf : COL.slate },
        line: { color: COL.white, width: 1 }, color: COL.white, fontSize: 13, bold: true, align: "center", valign: "middle", margin: 0, objectName: `${lab} ${r}` });
    });
    text(s, m, { x: x0, y: y + h + 0.08, w: 5.5, h: 0.32, fontSize: 14, color: COL.muted, objectName: `${lab} mean` });
  });
  const ay = 4.75;
  s.addShape(pres.shapes.LINE, { x: x0, y: ay, w: 11 * sc, h: 0, line: { color: COL.line, width: 1 }, objectName: "time axis" });
  for (let t = 0; t <= 11; t++) {
    text(s, String(t), { x: x0 + t * sc - 0.15, y: ay + 0.06, w: 0.3, h: 0.25, fontSize: 11, color: COL.muted, align: "center", objectName: `tick ${t}` });
  }
  text(s, "time (s); arrivals R0 t=0, R1 t=1, R2 t=2, R3 t=3; lengths 5, 3, 1, 2 tokens", { x: x0, y: ay + 0.36, w: 5.8, h: 0.3, fontSize: 11, color: COL.muted, objectName: "axis caption" });
  card(s, x0 - 0.8, 5.55, 6.3, 0.95, "tradeoff card");
  text(s, "SJF: R2 and R3 finish sooner; R1 waits 7 s instead of 4 s", { x: x0 - 0.6, y: 5.72, w: 6.0, h: 0.6, fontSize: 15, color: COL.ink, valign: "middle", objectName: "tradeoff text" });
}

// ================================================================ 3. Problem statement
{
  const s = newSlide("CONTENT", "Introduction", "Research question and objectives",
    "State the research question exactly as written. Then the three objectives, the metrics we judge by, and the scope. The scope box is important for honesty: everything is done in a simulator with one execution slot, seven experiments, ten paired seeds each.",
    ["RQ: can lightweight output-length prediction plus OS-style scheduling improve completion time and responsiveness vs FCFS without unacceptable fairness or overhead costs?", "Objectives: predict at admission; order with OS policies; measure against FCFS on identical workloads", "Criteria: TTFT, mean/median/P95/P99 JCT, throughput, waiting by length category, scheduling overhead", "Scope: discrete-event simulation, single slot, 7 experiments, 10 paired seeds"]);
  card(s, 0.6, 1.45, 12.1, 1.35, "question card");
  text(s, "Can lightweight output-length prediction plus OS-style scheduling make LLM requests finish sooner than FCFS, without unacceptable fairness or overhead costs?",
    { x: 0.9, y: 1.6, w: 11.5, h: 1.05, fontSize: 20, italic: true, color: COL.ink, valign: "middle", objectName: "research question" });
  const cols = [
    ["Objectives", ["Predict output length at admission", "Order requests with OS policies (SJF, aging)", "Compare with FCFS on identical workloads"]],
    ["Evaluation criteria", ["TTFT and mean / median / P95 / P99 JCT", "Throughput (requests/s, tokens/s)", "Waiting by length category; overhead"]],
    ["Scope", ["Discrete-event simulation, one execution slot", "7 experiments, 10 paired seeds each", "Planned work clearly separated"]],
  ];
  cols.forEach(([h, items], i) => {
    const x = 0.6 + i * 4.1;
    badge(s, x, 3.15, String(i + 1), i === 0 ? COL.sjf : i === 1 ? COL.fcfs : COL.slate, `objective badge ${i}`);
    text(s, h, { x: x + 0.55, y: 3.17, w: 3.3, h: 0.4, fontSize: 18, bold: true, objectName: `col head ${i}` });
    text(s, items.map((t, j) => ({ text: t, options: { bullet: true, breakLine: j < items.length - 1 } })),
      { x, y: 3.75, w: 3.8, h: 1.75, fontSize: 15, paraSpaceAfter: 8, objectName: `col body ${i}` });
  });
  text(s, "Experiments", { x: 0.6, y: 5.55, w: 3, h: 0.35, fontSize: 15, bold: true, objectName: "exp strip head" });
  ["EXP1 validation", "EXP2 FCFS vs SJF", "EXP3 composition", "EXP4 predictor quality", "EXP5 fairness", "EXP6 size", "EXP7 aging (ext.)"].forEach((t, i) => {
    const x = 0.6 + i * 1.75;
    s.addText(t, { shape: pres.shapes.ROUNDED_RECTANGLE, x, y: 5.98, w: 1.6, h: 0.62, rectRadius: 0.08, fill: { color: i === 6 ? COL.white : COL.panel },
      line: i === 6 ? { color: COL.grey, width: 1, dashType: "dash" } : { color: COL.panel, width: 0.5 }, color: COL.ink, fontSize: 13,
      align: "center", valign: "middle", margin: 0.04, objectName: `exp chip ${i}` });
  });
}

// ================================================================ 4. Background
pres.addSection({ title: "Background and design" });
{
  const s = newSlide("CONTENT", "Background and design", "Where this project sits in prior work",
    "Left: the four OS concepts we borrow. Right: the LLM systems most relevant to us, each verified from the paper's abstract or proceedings page. Two corrections to our original synopsis: vLLM's paper says it preempts the latest-arrived requests first, not the oldest; and S3 uses a learned DistilBERT predictor, not a heuristic. Clairvoyant is the closest setting to ours: predictive SJF admission in front of a serial backend. Our contribution is deliberately modest: a validated, reproducible evaluation of known policies, not a new algorithm.",
    ["OS concepts: FCFS, SJF, MLFQ, aging", "Orca (OSDI 2022): iteration-level scheduling", "vLLM (SOSP 2023): PagedAttention; FCFS; preempts latest arrivals first", "FastServe (NSDI 2026): token-level preemption, skip-join MLFQ (planned here)", "S³ (NeurIPS 2023): learned length prediction for memory/throughput", "LTR (NeurIPS 2024): learn to rank lengths, approximates SJF", "Clairvoyant (arXiv 2026): predictive SJF for serial backends, closest setting", "Contribution: validated, reproducible evaluation of established policies, not a new algorithm"]);
  const os = [["FCFS", "serve in arrival order"], ["SJF", "shortest job first; minimises mean wait"], ["MLFQ", "learn length online by demotion"], ["Aging", "raise priority while waiting"]];
  text(s, "OS scheduling concepts", { x: 0.6, y: 1.45, w: 4.2, h: 0.4, fontSize: 18, bold: true, objectName: "os head" });
  os.forEach(([k, v], i) => {
    const y = 2.0 + i * 0.95;
    card(s, 0.6, y, 4.2, 0.8, `os card ${i}`);
    text(s, k, { x: 0.8, y: y + 0.08, w: 3.9, h: 0.32, fontSize: 16, bold: true, objectName: `os key ${i}` });
    text(s, v, { x: 0.8, y: y + 0.42, w: 3.9, h: 0.32, fontSize: 14, color: COL.muted, objectName: `os val ${i}` });
  });
  const hdr = { bold: true, color: COL.white, fill: { color: COL.slate }, fontSize: 13 };
  const rows = [
    [{ text: "System", options: hdr }, { text: "Key idea", options: hdr }, { text: "Relation to this project", options: hdr }],
    ["Orca · OSDI '22", "iteration-level scheduling", "context: we model request-level only"],
    ["vLLM · SOSP '23", "PagedAttention; FCFS; preempts latest first", "our FCFS baseline"],
    ["FastServe · NSDI '26", "token preemption, skip-join MLFQ", "planned (MLFQ, preemption)"],
    ["S³ · NeurIPS '23", "learned length → memory packing", "different goal (throughput)"],
    ["LTR · NeurIPS '24", "learn to rank lengths ≈ SJF", "consistent with our ranking result"],
    ["Clairvoyant · arXiv '26", "predictive SJF, serial backend", "closest setting to ours"],
  ];
  s.addTable(rows, { x: 5.2, y: 1.5, w: 7.5, colW: [2.0, 2.85, 2.65], fontSize: 13, color: COL.ink, fontFace: "Calibri",
    border: { type: "solid", pt: 0.75, color: COL.grid }, rowH: 0.5, valign: "middle", margin: 0.06, objectName: "related work table" });
  text(s, "Contribution: a validated, reproducible evaluation of established policies on LLM-shaped workloads, not a new algorithm.",
    { x: 5.2, y: 5.25, w: 7.5, h: 0.7, fontSize: 15, italic: true, color: COL.slate, objectName: "contribution" });
  text(s, "Yu et al. 2022; Kwon et al. 2023; Wu et al. 2026; Jin et al. 2023; Fu et al. 2024; Sundaresan 2026. Full citations: docs/LITERATURE_REVIEW.md",
    { x: 5.2, y: 6.45, w: 7.5, h: 0.4, fontSize: 10, color: COL.muted, objectName: "citations" });
}

// ================================================================ 5. Architecture
{
  const s = newSlide("CONTENT", "Background and design", "System architecture as implemented",
    "Walk the pipeline left to right. A seeded generator produces an immutable workload. At arrival the predictor sees only observable prompt features, never the true length. The policy orders the waiting queue. The simulated execution slot runs prefill, which emits the first token, then decodes the remaining tokens at the true length. Metrics are computed per run, per length category and per request. The dashed boxes are planned and not built. The key design decision for validity: the same workload is replayed under every policy, so all comparisons are paired.",
    ["Workload generator (seeded, 3 mixes) → Length predictor (features only) → Scheduler policy (FCFS, SJF, aging) → Simulated execution slot (prefill then decode at true length) → Metrics & analysis", "Planned, not implemented: MLFQ, preemption (recompute/swap), KV-cache & batching, vLLM/GPU backend", "Same workload replayed under every policy: paired comparison"]);
  const boxes = [
    ["Workload generator", "seeded; 3 task mixes; Poisson arrivals"],
    ["Length predictor", "sees prompt features only"],
    ["Scheduler policy", "FCFS · SJF · aging"],
    ["Execution slot (simulated)", "prefill → decode at true length"],
    ["Metrics & analysis", "TTFT, JCT, fairness, CIs"],
  ];
  const fills = [COL.panel, COL.panel, "FCE3D8", COL.panel, COL.panel];
  boxes.forEach(([h, b], i) => {
    const x = 0.6 + i * 2.5;
    card(s, x, 1.75, 2.1, 1.9, `stage ${i}`, { fill: fills[i] });
    badge(s, x + 0.15, 1.9, String(i + 1), i === 2 ? COL.sjf : COL.slate, `stage badge ${i}`, 0.38, 13);
    text(s, h, { x: x + 0.15, y: 2.38, w: 1.85, h: 0.6, fontSize: 15, bold: true, objectName: `stage head ${i}` });
    text(s, b, { x: x + 0.15, y: 2.98, w: 1.85, h: 0.6, fontSize: 13, color: COL.muted, objectName: `stage body ${i}` });
    if (i < 4) s.addShape(pres.shapes.LINE, { x: x + 2.12, y: 2.7, w: 0.36, h: 0, line: { color: COL.slate, width: 1.75, endArrowType: "triangle" }, objectName: `arrow ${i}` });
  });
  text(s, "Planned, not implemented", { x: 5.6, y: 4.05, w: 7.0, h: 0.35, fontSize: 14, bold: true, color: COL.grey, objectName: "planned head" });
  ["MLFQ + priority boost", "Preemption: recompute / swap", "KV-cache & batching", "vLLM / GPU backend"].forEach((t, i) => {
    const x = 5.6 + i * 1.8;
    card(s, x, 4.45, 1.65, 0.95, `planned ${i}`, { fill: COL.white, dashed: true });
    text(s, t, { x: x + 0.1, y: 4.5, w: 1.45, h: 0.85, fontSize: 13, color: COL.grey, align: "center", valign: "middle", objectName: `planned text ${i}` });
  });
  card(s, 0.6, 5.75, 12.1, 0.85, "pairing card");
  badge(s, 0.8, 5.96, "=", COL.fcfs, "pairing badge", 0.42, 16);
  text(s, "One immutable workload per seed is replayed under every policy, so differences come only from the scheduling decision",
    { x: 1.4, y: 5.85, w: 11.1, h: 0.65, fontSize: 15, valign: "middle", objectName: "pairing text" });
}

// ================================================================ 6. Implementation status + demo
{
  const st = D.exp1, dm = D.demo;
  const s = newSlide("CONTENT", "Background and design", "Implementation status: what is built and tested",
    `About half of the proposed system is built, as one working pipeline rather than half-finished pieces: 9 of the synopsis's 18 components are complete and one, aging, is partial. Everything on the left is unit-tested: ${st.pytest}. The planned half — MLFQ, both preemption modes, memory and batching, a learned predictor, priority classes — is not started; vLLM and GPU work is blocked by the hardware audit. For the demo, run python experiments/scripts/demo.py: it generates a fixed workload, runs FCFS and SJF on it, prints the comparison, saves CSVs and regenerates a plot. In the recorded run (${dm.run}) mean JCT went from ${f1(dm.fcfs_jct)} to ${f1(dm.sjf_jct)} seconds.`,
    ["Built and tested: request model; seeded workloads; heuristic predictor + references; FCFS and predictive SJF; discrete-event simulator; metrics, runner and analysis; aging (partial, extension)", "Planned: MLFQ; recompute/swap preemption; KV-cache & batching; learned predictor; priority classes", "Blocked: vLLM / GPU (no vLLM, no WSL/Docker, 4 GB GPU)", `Evidence: ${st.pytest}; demo.py run ${dm.run}: mean JCT ${f1(dm.fcfs_jct)} s → ${f1(dm.sjf_jct)} s`]);
  text(s, "Built and tested · 9 of 18 synopsis components, 1 partial", { x: 0.6, y: 1.45, w: 6.4, h: 0.4, fontSize: 17, bold: true, objectName: "built head" });
  const built = ["Request model with enforced state machine", "Seeded workloads: short-heavy, mixed, long-heavy", "Heuristic predictor + labelled oracle references", "FCFS and non-preemptive predictive SJF", "Discrete-event single-slot simulator", "Metrics, paired runner, analysis, figures", "Extension: linear aging (partial)"];
  built.forEach((t, i) => {
    const y = 2.0 + i * 0.6;
    badge(s, 0.6, y, "✓", i === 6 ? COL.grey : COL.good, `check ${i}`, 0.36, 13);
    text(s, t, { x: 1.1, y: y + 0.02, w: 5.9, h: 0.36, fontSize: 15, valign: "middle", objectName: `built ${i}` });
  });
  card(s, 7.3, 1.45, 5.4, 2.25, "planned card", { fill: COL.white, dashed: true });
  text(s, "Planned", { x: 7.5, y: 1.55, w: 5.0, h: 0.36, fontSize: 16, bold: true, color: COL.grey, objectName: "planned head" });
  text(s, "MLFQ · recompute and swap preemption · KV-cache and batching · learned predictor · priority classes",
    { x: 7.5, y: 1.95, w: 5.0, h: 0.8, fontSize: 14, color: COL.muted, objectName: "planned list" });
  text(s, "Blocked: vLLM / GPU runs (no vLLM, WSL or Docker; 4 GB GPU)", { x: 7.5, y: 2.85, w: 5.0, h: 0.7, fontSize: 14, color: COL.muted, objectName: "blocked" });
  card(s, 7.3, 3.9, 5.4, 2.75, "evidence card");
  text(s, st.pytest.replace(/ in .*/, ""), { x: 7.5, y: 4.0, w: 5.0, h: 0.55, fontSize: 26, bold: true, objectName: "tests value" });
  text(s, "unit tests (pytest), incl. hand-calculated example", { x: 7.5, y: 4.55, w: 5.0, h: 0.35, fontSize: 13, color: COL.muted, objectName: "tests label" });
  text(s, "python experiments/scripts/demo.py", { x: 7.5, y: 5.05, w: 5.0, h: 0.35, fontSize: 13, fontFace: "Courier New", color: COL.slate, objectName: "demo cmd" });
  text(s, `Recorded demo (${dm.n.toLocaleString("en-US")} requests, load 0.9): mean JCT ${f1(dm.fcfs_jct)} s → ${f1(dm.sjf_jct)} s; CSVs and a plot saved`,
    { x: 7.5, y: 5.45, w: 5.0, h: 0.95, fontSize: 14, objectName: "demo result" });
}

// ================================================================ 7. Policies
{
  const s = newSlide("CONTENT", "Background and design", "Three policies behind one interface",
    "All three policies share one interface and are binary-heap queues with an ordering key fixed at admission. FCFS orders by arrival. Predictive SJF orders by predicted output length and never interrupts a running request — it is non-preemptive, which matters when comparing with FastServe. The aging extension subtracts a times the waiting time; because that term is the same for every waiting request at a given moment, it is exactly equivalent to a static key, predicted plus a times arrival time. a = 0 is SJF and very large a is FCFS, both unit-tested. MLFQ needs a time-varying policy and preemption, so it is planned. The heuristic predictor at the bottom uses only observable features.",
    ["FCFS: earliest arrival first; baseline", "Predictive SJF: smallest predicted output first; non-preemptive", "Aging (extension): predicted − a·wait ≡ predicted + a·arrival; a=0 is SJF, a→∞ is FCFS", "MLFQ: planned (needs preemption)", "Heuristic: prior[task] × √(prompt/1024) for summaries × 2 if detail requested, capped at max_tokens"]);
  const cards = [
    ["FCFS", COL.fcfs, "Earliest arrival first", "key = (arrival)", "Baseline: vLLM's admission order", "Implemented"],
    ["Predictive SJF", COL.sjf, "Smallest predicted output first; never interrupts a running request", "key = (predicted, arrival)", "Non-preemptive", "Implemented"],
    ["SJF + aging", COL.slate, "Priority improves while waiting: predicted − a × wait", "≡ key = predicted + a × arrival", "a = 0 → SJF;  a → ∞ → FCFS", "Extension"],
    ["MLFQ", COL.grey, "Demote by tokens generated vs prediction; periodic boost", "time-varying; needs preemption", "Synopsis centrepiece", "Planned"],
  ];
  cards.forEach(([h, c, rule, key, note, status], i) => {
    const x = 0.6 + i * 3.08;
    const planned = status === "Planned";
    card(s, x, 1.5, 2.85, 3.85, `policy card ${i}`, planned ? { fill: COL.white, dashed: true } : {});
    badge(s, x + 0.2, 1.68, String(i + 1), c, `policy badge ${i}`);
    text(s, h, { x: x + 0.75, y: 1.7, w: 2.0, h: 0.4, fontSize: 18, bold: true, color: planned ? COL.grey : COL.ink, objectName: `policy head ${i}` });
    text(s, rule, { x: x + 0.2, y: 2.3, w: 2.5, h: 1.15, fontSize: 15, color: planned ? COL.grey : COL.ink, objectName: `policy rule ${i}` });
    text(s, key, { x: x + 0.2, y: 3.5, w: 2.5, h: 0.6, fontSize: 12, fontFace: "Courier New", color: planned ? COL.grey : COL.slate, objectName: `policy key ${i}` });
    text(s, note, { x: x + 0.2, y: 4.15, w: 2.5, h: 0.55, fontSize: 13, color: COL.muted, objectName: `policy note ${i}` });
    text(s, status, { x: x + 0.2, y: 4.8, w: 2.5, h: 0.35, fontSize: 13, bold: true, color: planned ? COL.grey : c === COL.slate ? COL.slate : COL.good, objectName: `policy status ${i}` });
  });
  card(s, 0.6, 5.6, 12.1, 1.05, "predictor card");
  text(s, [
    { text: "Heuristic predictor (features only):  ", options: { bold: true } },
    { text: "prediction = prior[task] × √(prompt / 1024) [summaries] × 2 [if detail requested], capped at max_tokens;  priors qa 32, chat 128, summary 128, code 256, long-form 512" },
  ], { x: 0.85, y: 5.7, w: 11.6, h: 0.85, fontSize: 14, valign: "middle", objectName: "predictor formula" });
}

// ================================================================ 8. Methodology + validation
pres.addSection({ title: "Evaluation" });
{
  const st = D.exp1;
  const s = newSlide("CONTENT", "Evaluation", "Paired experiments on a validated simulator",
    `Methodology on the left: three synthetic workload mixes, Poisson arrivals at a target utilisation, ten paired seeds of five thousand requests, and confidence intervals computed across seeds, never across correlated requests. The service-time constants are assumptions; because load is set as utilisation, rescaling them rescales every time metric equally. On the right is why the simulator can be trusted: an independent Lindley recursion for FCFS agrees to ${st.lindley_max_diff_s.toExponential(1)} seconds; simulated mean waits agree with the Pollaczek-Khinchine and Cobham formulas within ${st.mean_abs_err_pct}% on average over ${st.n_cells} cells; reruns are bit-identical; all unit tests pass.`,
    ["3 synthetic mixes; Poisson arrivals at utilisation ρ; 10 paired seeds × 5,000 requests", "Unit of analysis = seed; 95% t-intervals on per-seed change vs FCFS", "Assumed service: prefill 10 ms + 0.2 ms/token, decode 25 ms/token", `Validation: Lindley max gap ${st.lindley_max_diff_s.toExponential(1)} s; P-K/Cobham mean abs error ${st.mean_abs_err_pct}% (${st.n_cells} cells); deterministic; ${st.pytest}`]);
  text(s, [
    { text: "Workloads: short-heavy, mixed, long-heavy task mixes (synthetic)", options: { bullet: true, breakLine: true } },
    { text: "Poisson arrivals at target utilisation ρ = 0.5 … 1.3", options: { bullet: true, breakLine: true } },
    { text: "10 paired seeds × 5,000 requests; same trace for every policy", options: { bullet: true, breakLine: true } },
    { text: "Unit of analysis = seed; 95 % t-interval on per-seed change vs FCFS", options: { bullet: true, breakLine: true } },
    { text: "Assumed service: prefill 10 ms + 0.2 ms/token; decode 25 ms/token", options: { bullet: true, breakLine: true } },
    { text: "Hypotheses written into each config before its run", options: { bullet: true } },
  ], { x: 0.6, y: 1.5, w: 6.2, h: 4.9, fontSize: 16, paraSpaceAfter: 10, objectName: "method bullets" });
  text(s, "Simulator validation (EXP1)", { x: 7.2, y: 1.45, w: 5.5, h: 0.4, fontSize: 17, bold: true, objectName: "validation head" });
  const tiles = [
    [sci(st.lindley_max_diff_s) + " s", "max gap vs independent Lindley recursion (FCFS)"],
    [`${st.mean_abs_err_pct}%`, `mean abs. error vs Pollaczek–Khinchine & Cobham (${st.n_cells} cells)`],
    [st.pytest.replace(/ passed.*/, "") + " / " + st.pytest.replace(/ passed.*/, ""), "unit tests pass"],
    ["identical", "per-request records on rerun (SHA-256)"],
  ];
  tiles.forEach(([v, l], i) => {
    const x = 7.2 + (i % 2) * 2.8, y = 2.0 + Math.floor(i / 2) * 2.15;
    card(s, x, y, 2.6, 1.95, `val tile ${i}`);
    text(s, v, { x: x + 0.18, y: y + 0.2, w: 2.3, h: 0.6, fontSize: 24, bold: true, objectName: `val value ${i}` });
    text(s, l, { x: x + 0.18, y: y + 0.9, w: 2.3, h: 0.95, fontSize: 13, color: COL.muted, objectName: `val label ${i}` });
  });
}

// ================================================================ 9. Core result
{
  const s = newSlide("CONTENT", "Evaluation", `Predictive SJF cuts mean JCT by ${Math.round(e2.jct_mean.heur_rel)}% at 80% load`,
    `This is the core result, EXP2A, mixed workload. The chart shows mean job completion time against load for FCFS, SJF with the heuristic predictor, and SJF with an oracle that knows true lengths — a reference, not deployable. FCFS blows up near saturation; SJF grows much more slowly. At load 0.8 the heuristic cuts mean JCT by ${pct(e2.jct_mean.heur_rel)}, interval ${f1(e2.jct_mean.heur_lo)} to ${f1(e2.jct_mean.heur_hi)}, better on all ten seeds; TTFT by ${pct(e2.ttft_mean.heur_rel)}; P95 by ${pct(e2.jct_p95.heur_rel)}. Across loads the reduction goes from ${pct(D.exp2a.reduction_heur[0])} to ${pct(D.exp2a.reduction_heur[D.exp2a.reduction_heur.length - 1])}. Throughput does not change, because both policies keep the slot busy whenever work is waiting.`,
    [`Chart: mean JCT vs load (FCFS, SJF-heuristic, SJF-oracle reference), mixed workload, 10 seeds`, `At ρ = 0.8: mean JCT −${pct(e2.jct_mean.heur_rel)} [${f1(e2.jct_mean.heur_lo)}, ${f1(e2.jct_mean.heur_hi)}], 10/10 seeds`, `Mean TTFT −${pct(e2.ttft_mean.heur_rel)}; P95 JCT −${pct(e2.jct_p95.heur_rel)}`, "Throughput unchanged (work-conserving policies)", `Reduction grows with load: ${pct(D.exp2a.reduction_heur[0])} at ρ = 0.5 to ${pct(D.exp2a.reduction_heur[D.exp2a.reduction_heur.length - 1])} at ρ = 0.95`]);
  const labels = D.exp2a.loads.map((l) => l.toFixed(2).replace(/0$/, ""));
  s.addChart(pres.charts.LINE, [
    { name: "FCFS", labels, values: D.exp2a.mean_jct["FCFS"] },
    { name: "SJF-heuristic", labels, values: D.exp2a.mean_jct["SJF-heuristic"] },
    { name: "SJF-oracle (reference)", labels, values: D.exp2a.mean_jct["SJF-oracle"] },
  ], { x: 0.6, y: 1.45, w: 7.7, h: 5.35, ...AX, chartColors: [COL.fcfs, COL.sjf, COL.oracle], lineSize: 2, lineDataSymbol: "circle", lineDataSymbolSize: 7,
    showLegend: true, legendPos: "b", showTitle: true, title: "Mean JCT (s) vs offered load ρ · mixed workload · mean of 10 seeds",
    showValAxisTitle: true, valAxisTitle: "mean JCT (s)", showCatAxisTitle: true, catAxisTitle: "offered load ρ", valAxisMinVal: 0, objectName: "mean jct chart" });
  stat(s, 8.7, 1.5, 4.0, `−${pct(e2.jct_mean.heur_rel)}`, `mean JCT at ρ${NB}=${NB}0.8 [${f1(e2.jct_mean.heur_lo)}, ${f1(e2.jct_mean.heur_hi)}], better on ${e2.jct_mean.better}/10${NB}seeds`, "stat jct", COL.sjf);
  stat(s, 8.7, 2.8, 4.0, `−${pct(e2.ttft_mean.heur_rel)}`, `mean time to first token at ρ${NB}=${NB}0.8`, "stat ttft");
  stat(s, 8.7, 4.1, 4.0, `−${pct(e2.jct_p95.heur_rel)}`, `P95 JCT at ρ${NB}=${NB}0.8`, "stat p95");
  stat(s, 8.7, 5.4, 4.0, `${e2.throughput_tps.heur_rel.toFixed(1)}%`, "throughput change: both policies keep the slot busy", "stat tput");
}

// ================================================================ 10. Sensitivity
{
  const rows = D.exp4;
  const nice = { "SJF-oracle": "oracle*", "SJF-noise0.5": "noise σ=0.5*", "SJF-heuristic": "heuristic", "SJF-noise1.0": "noise σ=1*",
    "SJF-noise2.0": "noise σ=2*", "SJF-noise3.0": "noise σ=3*", "SJF-max_tokens": "max_tokens", "SJF-random": "random", "SJF-prompt_length": "prompt length" };
  const pl = rows.find((r) => r.condition === "SJF-prompt_length"), rnd = rows.find((r) => r.condition === "SJF-random"), he = rows.find((r) => r.condition === "SJF-heuristic");
  const s = newSlide("CONTENT", "Evaluation", "Gains follow ranking quality and size variability",
    `Left, EXP4: mean-JCT improvement over FCFS for each predictor, with its Spearman rank correlation in brackets. Starred bars are references that read the true length plus synthetic noise. The gain degrades smoothly: even sigma 1 keeps most of it. The heuristic captures ${he.gain_captured}% of the oracle's gain. Two controls matter: random predictions give FCFS's mean, as queueing theory predicts; and prompt length, despite a positive correlation of ${pl.spearman}, is ${Math.abs(pl.reduction)}% worse than FCFS because it promotes long-form answers, which have short prompts. Right, EXP3: the gain is largest when request sizes vary most — short-heavy has the highest coefficient of variation.`,
    [...rows.map((r) => `${nice[r.condition]} (Spearman ${r.spearman.toFixed(2)}): ${r.reduction > 0 ? "−" : "+"}${Math.abs(r.reduction).toFixed(1)}% mean JCT vs FCFS`), `By mix at ρ = 0.8 (heuristic): ${D.exp3.mixes.map((m, i) => `${m} ${pct(D.exp3.heur[i])}`).join(", ")}; service CV ${D.exp3.cv.join(" / ")}`, "* reference: reads the true length; not deployable"]);
  s.addChart(pres.charts.BAR, [{ name: "mean-JCT improvement vs FCFS (%)", labels: rows.map((r) => `${nice[r.condition]} (${r.spearman.toFixed(2)})`), values: rows.map((r) => r.reduction) }],
    { x: 0.6, y: 1.45, w: 7.1, h: 4.5, ...AX, barDir: "bar", catAxisOrientation: "maxMin", showLegend: false, showValue: true, dataLabelPosition: "outEnd",
      dataLabelFormatCode: '0.0"%"', valAxisMinVal: -20, valAxisMaxVal: 60, valAxisMajorUnit: 20, valAxisLabelFormatCode: '0"%"', barGapWidthPct: 60,
      chartColors: rows.map((r) => (r.condition === "SJF-heuristic" ? COL.sjf : r.reference ? COL.oracle : COL.grey)),
      catAxisLabelPos: "low", showTitle: true, title: "Mean-JCT improvement vs FCFS by predictor (rank corr.) · load 0.8", objectName: "predictor chart" });
  const mixLabels = D.exp3.mixes.map((m, i) => `${m.replace("_", "-")} (CV ${D.exp3.cv[i]})`);
  s.addChart(pres.charts.BAR, [
    { name: "SJF-heuristic", labels: mixLabels, values: D.exp3.heur },
    { name: "SJF-oracle (reference)", labels: mixLabels, values: D.exp3.oracle },
  ], { x: 8.0, y: 1.45, w: 4.7, h: 4.5, ...AX, barDir: "col", barGrouping: "clustered", chartColors: [COL.sjf, COL.oracle], showLegend: true, legendPos: "b",
    showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: '0"%"', valAxisMinVal: 0, valAxisMaxVal: 70, valAxisLabelFormatCode: '0"%"',
    catAxisLabelFontSize: 11, showTitle: true, title: "Improvement by workload mix · load 0.8", objectName: "mix chart" });
  text(s, [
    { text: `Random predictions give FCFS's mean (${rnd.reduction > 0 ? "+" : ""}${rnd.reduction.toFixed(1)}%, CI includes 0).`, options: { breakLine: true } },
    { text: `Prompt length correlates positively (${pl.spearman}) yet is ${Math.abs(pl.reduction).toFixed(1)}% worse than FCFS: it promotes long‑form answers.` },
  ], { x: 0.6, y: 6.0, w: 12.1, h: 0.62, fontSize: 14, color: COL.ink, objectName: "sensitivity takeaway" });
  text(s, "* reference: reads the true length; not deployable", { x: 0.6, y: 6.68, w: 6, h: 0.26, fontSize: 10, color: COL.muted, objectName: "ref footnote" });
}

// ================================================================ 11. Fairness
{
  const f = D.exp5;
  const s = newSlide("CONTENT", "Evaluation", "Long requests pay for the gain",
    `EXP5, mixed workload at load 0.9. Left: mean waiting time by the request's true length category. FCFS treats every category the same, about 85 seconds. SJF cuts short-request waits to about 11 seconds and pushes long-request waits up to ${f1(f.wait_mean["SJF-heuristic"][2])}. Right: the worst case per seed for long requests rises from ${f.long_max.FCFS} to ${f.long_max["SJF-heuristic"]} seconds with the heuristic and ${f.long_max["SJF-oracle"]} with the oracle. Three things on the bottom row. The negative result: with heuristic predictions, P99 completion time is worse than FCFS at load 0.9 and above, because the coarse 'very long' prediction class — ${f.all_pred_ge1024}% of requests — waits as a block. Prediction error spreads the harm to medium requests. And by slowdown, FCFS is actually the less fair policy for short requests. Nothing in plain SJF bounds a long request's wait.`,
    [`Mean wait by category (s), FCFS / SJF-heuristic / SJF-oracle: short ${f.wait_mean.FCFS[0]} / ${f.wait_mean["SJF-heuristic"][0]} / ${f.wait_mean["SJF-oracle"][0]}; long ${f.wait_mean.FCFS[2]} / ${f.wait_mean["SJF-heuristic"][2]} / ${f.wait_mean["SJF-oracle"][2]}`, `Per-seed max wait of long requests: ${f.long_max.FCFS} / ${f.long_max["SJF-heuristic"]} / ${f.long_max["SJF-oracle"]} s`, `P99 JCT with heuristic worse than FCFS at ρ ≥ 0.9: ${D.exp2a.p99_heur["0.9"]}%, ${D.exp2a.p99_heur["0.95"]}%`, `${f.n_over["SJF-heuristic"]} requests/seed exceed FCFS's worst wait (${f.n_over_medium_heur} medium)`, `Slowdown of short requests: FCFS ${f1(f.short_slowdown.FCFS)}× vs SJF ${f1(f.short_slowdown["SJF-heuristic"])}×`]);
  const cats = f.cats;
  s.addChart(pres.charts.BAR, ["FCFS", "SJF-heuristic", "SJF-oracle"].map((c) => ({ name: c === "SJF-oracle" ? "SJF-oracle (ref.)" : c, labels: cats, values: f.wait_mean[c] })),
    { x: 0.6, y: 1.45, w: 6.6, h: 3.85, ...AX, barDir: "col", barGrouping: "clustered", chartColors: [COL.fcfs, COL.sjf, COL.oracle], showLegend: true, legendPos: "b",
      showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0", valAxisMinVal: 0, showTitle: true,
      title: "Mean waiting time (s) by true length · mixed, ρ = 0.9", objectName: "wait by category chart" });
  s.addChart(pres.charts.BAR, [{ name: "max wait of long requests (s)", labels: ["FCFS", "SJF-heuristic", "SJF-oracle (ref.)"], values: [f.long_max.FCFS, f.long_max["SJF-heuristic"], f.long_max["SJF-oracle"]] }],
    { x: 7.5, y: 1.45, w: 5.2, h: 3.85, ...AX, barDir: "col", chartColors: [COL.fcfs, COL.sjf, COL.oracle], showLegend: false, showValue: true,
      dataLabelPosition: "outEnd", dataLabelFormatCode: "#,##0", valAxisMinVal: 0, barGapWidthPct: 80, showTitle: true,
      title: "Per-seed max wait of long requests (s)", objectName: "max wait chart" });
  const calls = [
    [`P99 JCT worse than FCFS at ρ${NB}≥${NB}0.9 with heuristic: ${D.exp2a.p99_heur["0.9"]}%, ${D.exp2a.p99_heur["0.95"]}%`, COL.sjf],
    [`${f.n_over["SJF-heuristic"]} requests per seed wait longer than FCFS's worst case; ${f.n_over_medium_heur} are mispredicted medium ones`, COL.slate],
    [`By slowdown, FCFS is less fair: short requests wait ${Math.round(f.short_slowdown.FCFS)}× their service time vs ${Math.round(f.short_slowdown["SJF-heuristic"])}×`, COL.fcfs],
  ];
  calls.forEach(([t, c], i) => {
    const x = 0.6 + i * 4.1;
    card(s, x, 5.55, 3.9, 1.25, `fair call ${i}`);
    badge(s, x + 0.15, 5.7, "!", c, `fair badge ${i}`, 0.36, 14);
    text(s, t, { x: x + 0.62, y: 5.62, w: 3.15, h: 1.1, fontSize: 14, valign: "middle", objectName: `fair text ${i}` });
  });
}

// ================================================================ 12. Aging extension
{
  const g = D.exp7;
  const i1 = g.labels.indexOf("a=1"), i0 = 0;
  const keep = Math.round((g.gain[i1] / g.gain[i0]) * 100), cut = Math.round((1 - g.max_wait[i1] / g.max_wait[i0]) * 100);
  const s = newSlide("CONTENT", "Evaluation", "Extension: aging trades mean JCT for worst-case wait",
    `EXP7, the one extension we built: SJF with linear aging, mixed workload at load 0.9. Read left to right along the aging rate a, in tokens of priority per second waited. The left chart is the mean-JCT gain over FCFS; the right is the worst-case wait. Both fall together. At a = 1, aging keeps ${keep}% of SJF's mean gain and cuts the worst-case wait by ${cut}%. But no rate we tested reaches FCFS's worst case while keeping most of the gain — aging is a dial, not a cure. The grid was chosen on separate development seeds. This is simulated, and it is not production-quality starvation prevention.`,
    [`Aging rates a ∈ {0 (SJF), 0.5, 1, 2, 3, 5, 10, 30, 100, ∞ (FCFS)} tokens/s; mixed workload, ρ = 0.9`, `Mean-JCT gain vs FCFS: ${g.gain.map((v) => v.toFixed(1)).join(", ")}%`, `Max wait (s): ${g.max_wait.join(", ")}`, `a = 1 keeps ${keep}% of SJF's gain and cuts its worst-case wait by ${cut}%`, "No tested rate reaches FCFS's worst case while keeping most of the gain"]);
  const labels = g.labels.map((l) => l.replace("SJF (a=0)", "SJF").replace("a=", ""));
  s.addChart(pres.charts.LINE, [{ name: "mean-JCT gain vs FCFS (%)", labels, values: g.gain }],
    { x: 0.6, y: 1.45, w: 5.95, h: 4.2, ...AX, chartColors: [COL.sjf], lineSize: 2, lineDataSymbol: "circle", lineDataSymbolSize: 7, showLegend: false,
      showTitle: true, title: "Mean-JCT gain vs FCFS (%) by aging rate a", showCatAxisTitle: true, catAxisTitle: "aging rate a (tokens/s); SJF is a = 0, FCFS the large-a limit",
      valAxisMinVal: 0, valAxisMaxVal: 70, valAxisLabelFormatCode: '0"%"', objectName: "aging gain chart" });
  s.addChart(pres.charts.LINE, [{ name: "max waiting time (s)", labels, values: g.max_wait }],
    { x: 6.75, y: 1.45, w: 5.95, h: 4.2, ...AX, chartColors: [COL.slate], lineSize: 2, lineDataSymbol: "circle", lineDataSymbolSize: 7, showLegend: false,
      showTitle: true, title: "Worst-case waiting time (s; per-seed max, mean of 10)", showCatAxisTitle: true, catAxisTitle: "aging rate a (tokens/s); SJF is a = 0, FCFS the large-a limit",
      valAxisMinVal: 0, valAxisLabelFormatCode: "#,##0", objectName: "aging max chart" });
  card(s, 0.6, 5.9, 12.1, 0.85, "aging takeaway card");
  text(s, `a = 1 keeps ${keep}% of SJF's mean-JCT gain and cuts its worst-case wait by ${cut}%. No tested rate reaches FCFS's worst case while keeping most of the gain.`,
    { x: 0.85, y: 5.98, w: 11.6, h: 0.7, fontSize: 15, valign: "middle", objectName: "aging takeaway" });
}

// ================================================================ 13. Limitations
pres.addSection({ title: "Wrap-up" });
{
  const s = newSlide("CONTENT", "Wrap-up", "What these results do not show",
    "Be direct about validity. Biggest threat: a single execution slot. A real server batches many sequences, so short requests can share iterations with long ones and FCFS head-of-line blocking is weaker; our absolute gains are probably overstated for batched serving. Timing constants are assumptions. The workload is synthetic, and our heuristic uses the same features the generator uses, so its accuracy is optimistic — that is why EXP4 sweeps prediction error. We did not implement preemption, so the latency-versus-preemption-overhead question is unanswered. Ten seeds per configuration is enough for means but tails are noisy, and two analyses were post-hoc.",
    ["Simulator ≠ GPU server: one slot, no batching, assumed timing; gains likely overstated for batched serving", "Synthetic workload: no real prompts; heuristic shares the generator's features (optimistic)", "Missing mechanisms: no preemption, KV-cache, MLFQ; preemption-overhead question unanswered", "Statistics: 10 seeds; tail metrics noisy; two post-hoc analyses labelled as such"]);
  const L = [
    ["Simulator ≠ GPU server", "One slot, no batching, no memory; assumed timing constants. Gains are likely overstated for continuously batched serving."],
    ["Synthetic workload", "No real prompts or traces. The heuristic uses the generator's own features, so its accuracy is optimistic."],
    ["Missing mechanisms", "No preemption, KV-cache or MLFQ: the latency vs preemption-overhead question (RQ6) is unanswered."],
    ["Statistical limits", "10 seeds per configuration; P99 and maxima are noisy; two analyses were post-hoc and are labelled."],
  ];
  L.forEach(([h, b], i) => {
    const x = 0.6 + (i % 2) * 6.15, y = 1.5 + Math.floor(i / 2) * 2.6;
    card(s, x, y, 5.95, 2.35, `limit card ${i}`);
    badge(s, x + 0.25, y + 0.25, String(i + 1), COL.slate, `limit badge ${i}`);
    text(s, h, { x: x + 0.85, y: y + 0.27, w: 4.9, h: 0.4, fontSize: 18, bold: true, objectName: `limit head ${i}` });
    text(s, b, { x: x + 0.85, y: y + 0.85, w: 4.85, h: 1.35, fontSize: 16, color: COL.slate, objectName: `limit body ${i}` });
  });
}

// ================================================================ 14. Future work
{
  const s = newSlide("CONTENT", "Wrap-up", "Next steps toward a real system",
    "The future-work order follows the gaps. First MLFQ with a priority boost, which needs a time-varying policy interface and preemption in the simulator. Then the two preemption modes, recompute and swap, with modelled costs, which finally answers research question six. Then batching with a KV-cache budget to see whether single-slot conclusions survive. Then a learned predictor trained and tested on real prompts with logged lengths. Finally real-hardware validation: a patched vLLM scheduler or an admission proxy in front of a serial backend, replaying the same paired traces.",
    ["1. MLFQ + priority boost (time-varying policy)", "2. Preemption: recompute vs swap with modelled costs (answers RQ6)", "3. Batching and KV-cache budget", "4. Learned predictor on real prompts with logged lengths", "5. Real GPU validation: patched vLLM scheduler or admission proxy, same paired traces"]);
  const steps = [
    ["MLFQ + boost", "demote by tokens vs prediction; periodic priority boost"],
    ["Preemption", "recompute vs swap, with modelled costs (answers RQ6)"],
    ["Batching + memory", "multiple slots and a KV-cache budget"],
    ["Learned predictor", "trained and tested on real prompts with logged lengths"],
    ["Real GPU validation", "patched vLLM scheduler or admission proxy; same traces"],
  ];
  steps.forEach(([h, b], i) => {
    const x = 0.6 + i * 2.48;
    badge(s, x + 0.75, 2.0, String(i + 1), i === 4 ? COL.sjf : COL.slate, `step badge ${i}`, 0.62, 20);
    if (i < 4) s.addShape(pres.shapes.LINE, { x: x + 1.45, y: 2.31, w: 1.7, h: 0, line: { color: COL.line, width: 1.5, endArrowType: "triangle" }, objectName: `step arrow ${i}` });
    card(s, x, 2.95, 2.2, 2.3, `step card ${i}`);
    text(s, h, { x: x + 0.18, y: 3.1, w: 1.85, h: 0.7, fontSize: 17, bold: true, objectName: `step head ${i}` });
    text(s, b, { x: x + 0.18, y: 3.85, w: 1.85, h: 1.55, fontSize: 14, color: COL.slate, objectName: `step body ${i}` });
  });
  text(s, "Each step reuses the existing paired-trace runner, configs and analysis pipeline.", { x: 0.6, y: 5.6, w: 12.1, h: 0.45, fontSize: 15, italic: true, color: COL.slate, objectName: "future note" });
}

// ================================================================ 15. Conclusion
{
  const s = newSlide("CLOSING_DARK", "Wrap-up", "Conclusion",
    `Three findings, all from simulation. One: ordering requests by a simple, interpretable length prediction cut mean completion time by ${pct(D.exp2a.reduction_heur[0])} to ${pct(D.exp2a.reduction_heur[D.exp2a.reduction_heur.length - 1])} depending on load, and time to first token by ${pct(e2.ttft_mean.heur_rel)} at 80% load. Two: the gain depends on ranking long requests correctly; uninformative predictions give nothing, and a misleading feature can be worse than FCFS. Three: long requests pay — worst-case waits grow about ${Math.round(D.exp5.max_ratio_range[0])} to ${Math.round(D.exp5.max_ratio_range[1])} times — and aging trades rather than removes that cost. The practical message: length-aware admission is worth testing on a real batched server, with a starvation guard. Then invite questions.`,
    [`Ordering by a simple length prediction cut mean JCT ${pct(D.exp2a.reduction_heur[0])}–${pct(D.exp2a.reduction_heur[D.exp2a.reduction_heur.length - 1])} (ρ 0.5–0.95) and TTFT ${pct(e2.ttft_mean.heur_rel)} at ρ = 0.8`, "The gain follows ranking quality; uninformative predictions give none", `Long requests pay: worst-case waits ~${Math.round(D.exp5.max_ratio_range[0])}–${Math.round(D.exp5.max_ratio_range[1])}× FCFS; aging trades, does not remove, the cost`, "All results simulated (single-slot M/G/1); next: validate on a batched GPU server", "Questions?"]);
  const F = [
    `Ordering by a simple length prediction cut mean JCT by ${Math.round(D.exp2a.reduction_heur[0])}–${Math.round(D.exp2a.reduction_heur[D.exp2a.reduction_heur.length - 1])}% (load 0.5–0.95) and TTFT by ${pct(e2.ttft_mean.heur_rel)} at load${NB}0.8`,
    "Gains follow ranking quality: random predictions give none; a misleading feature can hurt",
    `Long requests pay: worst-case waits ~${Math.round(D.exp5.max_ratio_range[0])}–${Math.round(D.exp5.max_ratio_range[1])}× FCFS; aging trades the cost, it does not remove it`,
  ];
  F.forEach((t, i) => {
    const y = 1.6 + i * 1.2;
    badge(s, 0.6, y + 0.05, String(i + 1), COL.sjf, `finding badge ${i}`, 0.55, 18);
    text(s, t, { x: 1.4, y, w: 11.2, h: 0.75, fontSize: 20, color: COL.white, valign: "middle", objectName: `finding ${i}` });
  });
  text(s, "Questions?", { x: 0.6, y: 5.35, w: 6, h: 0.8, fontSize: 32, bold: true, color: COL.white, objectName: "questions" });
  text(s, "All results are simulated (single-slot M/G/1, assumed timing, synthetic workloads); none are GPU measurements. Code, data and logs: llm-os-scheduler/",
    { x: 0.6, y: 6.35, w: 11.5, h: 0.5, fontSize: 13, color: COL.soft, objectName: "closing caveat" });
}

// ---------------------------------------------------------------- write
(async () => {
  const out = path.join(HERE, "final_presentation.pptx");
  await pres.writeFile({ fileName: out });
  if (process.env.APPLY_THEME_JS) {
    const { applyTheme } = require(process.env.APPLY_THEME_JS);
    await applyTheme(out, THEME);
  }
  const head = "# Presentation outline\n\nGenerated by `presentation/build_deck.js` from `presentation/deck_data.json` (which `build_data.py` extracts from `experiments/results/analysis/`). All results are simulated.\n\n";
  fs.writeFileSync(path.join(HERE, "presentation_outline.md"), head + outline.join("\n"));
  const viva = fs.readFileSync(path.join(HERE, "..", "docs", "VIVA_QUESTIONS.md"), "utf8").replace(/^# .*\n/, "");
  fs.writeFileSync(path.join(HERE, "speaker_notes.md"),
    "# Speaker notes\n\nAbout one minute per slide (15 slides, about 15 minutes). The same notes are embedded in the deck's notes pane.\n\n" +
    notesMd.join("\n") + "\n## Likely viva questions\n\nCopied from `docs/VIVA_QUESTIONS.md`.\n" + viva);
  console.log(`wrote ${out} (${n} slides), presentation_outline.md, speaker_notes.md`);
})();
