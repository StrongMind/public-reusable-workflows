#!/usr/bin/env node
/**
 * Runtime accessibility gate: axe-core + Playwright.
 * Maps changed paths -> URL journeys from AXE_TARGETS_PATH JSON.
 * Writes tmp/axe/axe-results.json + tmp/axe/summary.md; optional PR comment + annotations.
 */
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

import AxeBuilder from "@axe-core/playwright";
import picomatch from "picomatch";
import { chromium } from "playwright";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, "../../..");
const TMP_AXE = process.env.AXE_OUTPUT_DIR
  ? path.resolve(process.env.AXE_OUTPUT_DIR)
  : path.join(REPO_ROOT, "tmp", "axe");
const MARKER = process.env.AXE_STICKY_MARKER ?? "<!-- axe-a11y-report:sticky -->";

const AXE_TAGS = ["wcag2a", "wcag2aa"];

function readChangedFiles() {
  const fileEnv = process.env.CHANGED_FILES_FILE;
  if (fileEnv && fs.existsSync(fileEnv)) {
    return fs
      .readFileSync(fileEnv, "utf8")
      .split(/\r?\n/)
      .map((s) => s.trim())
      .filter(Boolean);
  }
  const raw = process.env.CHANGED_FILES ?? "";
  return raw.split(/\r?\n/).map((s) => s.trim()).filter(Boolean);
}

function loadTargets() {
  const override = process.env.AXE_TARGETS_PATH;
  if (!override) {
    throw new Error("AXE_TARGETS_PATH is required. Provide a changed-file -> URL mapping JSON.");
  }
  if (!fs.existsSync(override)) {
    throw new Error(`AXE_TARGETS_PATH does not exist: ${override}`);
  }
  const data = JSON.parse(fs.readFileSync(override, "utf8"));
  if (!Array.isArray(data.rules)) {
    throw new Error("axe targets file: missing rules[]");
  }
  return data;
}

function firstMatchingRule(rules, changedPath) {
  const posixPath = changedPath.split(path.sep).join("/");
  for (const rule of rules) {
    const globs = rule.globs;
    if (!Array.isArray(globs)) continue;
    for (const g of globs) {
      const isMatch = picomatch(g, { dot: true })(posixPath);
      if (isMatch) return rule;
    }
  }
  return null;
}

function journeyForRule(rule) {
  const j = rule.journey ?? rule.pathnames ?? rule.urls;
  if (!Array.isArray(j) || j.length === 0) {
    throw new Error(`axe_targets: rule missing journey/pathnames/urls: ${JSON.stringify(rule)}`);
  }
  return j.map((p) => (p.startsWith("/") ? p : `/${p}`));
}

function collectJourneys(changedFiles, rules) {
  /** @type {Map<string, { key: string, paths: string[] }>} */
  const byKey = new Map();
  for (const file of changedFiles) {
    const rule = firstMatchingRule(rules, file);
    if (!rule) continue;
    const journey = journeyForRule(rule);
    const key = journey.join(">");
    if (!byKey.has(key)) {
      byKey.set(key, { key, paths: journey });
    }
  }
  return [...byKey.values()];
}

function ensureDir(p) {
  fs.mkdirSync(p, { recursive: true });
}

function githubEvent() {
  const p = process.env.GITHUB_EVENT_PATH;
  if (!p || !fs.existsSync(p)) return null;
  return JSON.parse(fs.readFileSync(p, "utf8"));
}

async function githubApi(pathSuffix, init) {
  const token = process.env.GITHUB_TOKEN;
  if (!token) throw new Error("GITHUB_TOKEN required for API calls");
  const repo = process.env.GITHUB_REPOSITORY;
  if (!repo) throw new Error("GITHUB_REPOSITORY not set");
  const url = `https://api.github.com/repos/${repo}${pathSuffix}`;
  const res = await fetch(url, {
    ...init,
    headers: {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${token}`,
      "X-GitHub-Api-Version": "2022-11-28",
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`GitHub API ${pathSuffix} ${res.status}: ${text}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

async function upsertStickyComment(body) {
  const ev = githubEvent();
  const prFromEnv = Number.parseInt(process.env.AXE_PR_NUMBER ?? "", 10);
  const pr = Number.isInteger(prFromEnv) && prFromEnv > 0 ? prFromEnv : (ev?.pull_request?.number ?? ev?.number);
  if (!pr) {
    console.warn("No pull_request in GITHUB_EVENT; skipping PR comment.");
    return;
  }
  const comments = await githubApi(`/issues/${pr}/comments`, { method: "GET" });
  const existing = Array.isArray(comments)
    ? comments.find((c) => typeof c.body === "string" && c.body.includes(MARKER))
    : null;
  const fullBody = `${MARKER}\n${body}`;
  if (existing?.id) {
    await githubApi(`/issues/comments/${existing.id}`, {
      method: "PATCH",
      body: JSON.stringify({ body: fullBody }),
    });
  } else {
    await githubApi(`/issues/${pr}/comments`, {
      method: "POST",
      body: JSON.stringify({ body: fullBody }),
    });
  }
}

function emitAnnotations(violations, baseUrl, pageUrl) {
  const max = Number(process.env.AXE_ANNOTATION_LIMIT ?? "20");
  let n = 0;
  for (const v of violations) {
    if (n >= max) break;
    const nodes = v.nodes?.slice(0, 3) ?? [];
    for (const node of nodes) {
      if (n >= max) break;
      const target = Array.isArray(node.target) ? node.target.join(" ") : String(node.target);
      const msg = `${v.id}: ${v.help} — ${target}`.replace(/\r?\n/g, " ");
      const safe = msg.slice(0, 4000);
      console.log(`::warning file=${pageUrl.replace(baseUrl, "") || "/"}::${safe}`);
      n++;
    }
  }
}

async function run() {
  ensureDir(TMP_AXE);
  const baseUrl = (process.env.AXE_BASE_URL ?? "http://127.0.0.1:4173").replace(/\/$/, "");
  const changedFiles = readChangedFiles();
  const { rules } = loadTargets();

  const journeys =
    changedFiles.length === 0
      ? []
      : collectJourneys(changedFiles, rules);

  /** @type {{ meta: object, pages: object[] }} */
  const out = {
    meta: {
      baseUrl,
      changedFiles,
      tags: AXE_TAGS,
      journeys: journeys.map((j) => j.paths),
      timestamp: new Date().toISOString(),
    },
    pages: [],
  };

  let totalViolations = 0;
  let totalIncomplete = 0;

  if (journeys.length === 0) {
    const summary =
      changedFiles.length === 0
        ? "## Axe accessibility (runtime)\n\nNo changed files in this diff — **skipped** (nothing to map).\n"
        : "## Axe accessibility (runtime)\n\nNo URL journeys matched changed files — **skipped**.\n";
    fs.writeFileSync(path.join(TMP_AXE, "summary.md"), summary, "utf8");
    fs.writeFileSync(path.join(TMP_AXE, "axe-results.json"), JSON.stringify(out, null, 2), "utf8");
    if (process.env.AXE_POST_COMMENT === "true") {
      await upsertStickyComment(summary);
    }
    console.log(summary);
    return;
  }

  const browser = await chromium.launch({ headless: true });
  try {
    for (const { paths: journeyPaths } of journeys) {
      const context = await browser.newContext();
      const page = await context.newPage();
      const pageResults = { journey: journeyPaths, scans: [] };

      for (const pathname of journeyPaths) {
        const url = `${baseUrl}${pathname}`;
        await page.goto(url, { waitUntil: "networkidle", timeout: 60_000 });
        const analysis = await new AxeBuilder({ page }).withTags(AXE_TAGS).analyze();
        const { violations, incomplete, passes, ...rest } = analysis;
        totalViolations += violations.length;
        totalIncomplete += incomplete.length;

        if (process.env.AXE_ANNOTATIONS !== "false") {
          emitAnnotations(violations, baseUrl, url);
        }

        pageResults.scans.push({
          url,
          pathname,
          violationCount: violations.length,
          incompleteCount: incomplete.length,
          passCount: passes?.length ?? 0,
          violations,
          incomplete,
          raw: { ...rest, violations, incomplete, passes },
        });
      }

      await context.close();
      out.pages.push(pageResults);
    }
  } finally {
    await browser.close();
  }

  fs.writeFileSync(path.join(TMP_AXE, "axe-results.json"), JSON.stringify(out, null, 2), "utf8");

  const verdict =
    totalViolations === 0
      ? "**PASS** — no axe violations (wcag2a + wcag2aa)."
      : `**FAIL** — ${totalViolations} axe violation group(s) reported.`;

  const lines = [
    "## Axe accessibility (runtime)",
    "",
    verdict,
    "",
    `**Base URL:** \`${baseUrl}\``,
    `**Changed files (${changedFiles.length}):** ${changedFiles.length ? changedFiles.map((f) => `\`${f}\``).join(", ") : "—"}`,
    "",
    "### URLs scanned",
  ];

  for (const p of out.pages) {
    lines.push(`- Journey: ${p.journey.map((x) => `\`${x}\``).join(" → ")}`);
    for (const s of p.scans) {
      lines.push(`  - \`${s.url}\` — ${s.violationCount} violation group(s), ${s.incompleteCount} incomplete`);
    }
  }

  lines.push("", "### Findings");
  if (totalViolations === 0) {
    lines.push("_No violations._");
  } else {
    for (const p of out.pages) {
      for (const s of p.scans) {
        for (const v of s.violations) {
          lines.push(`- **${v.id}** (${v.impact}): ${v.help}`);
          if (v.helpUrl) lines.push(`  - Help: ${v.helpUrl}`);
          const nodes = v.nodes?.slice(0, 5) ?? [];
          for (const n of nodes) {
            const t = Array.isArray(n.target) ? n.target.join(" ") : n.target;
            const fx = n.failureSummary ? ` — ${n.failureSummary.replace(/\s+/g, " ").trim()}` : "";
            lines.push(`  - \`${t}\`${fx}`);
          }
        }
      }
    }
  }

  if (totalIncomplete > 0) {
    lines.push("", `_Note: ${totalIncomplete} incomplete check(s) — review raw \`tmp/axe/axe-results.json\`._`);
  }

  const summaryMd = lines.join("\n");
  fs.writeFileSync(path.join(TMP_AXE, "summary.md"), summaryMd, "utf8");

  if (process.env.AXE_POST_COMMENT === "true") {
    await upsertStickyComment(summaryMd);
  }

  const sumFile = process.env.GITHUB_STEP_SUMMARY;
  if (sumFile) {
    fs.appendFileSync(sumFile, `\n${summaryMd}\n`);
  }

  console.log(summaryMd);

  const enforce = (process.env.AXE_ENFORCE ?? "warn").toLowerCase();
  if (totalViolations > 0 && enforce === "block") {
    process.exitCode = 1;
  }
}

run().catch((err) => {
  console.error(err);
  process.exitCode = 1;
});
