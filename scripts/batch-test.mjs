/**
 * Batch Testing Script — Ding Ding Cat Sticker Generator
 *
 * Tests every combination of user choices:
 *   Festival (9) × Quick Pick (6) = 54 combinations
 *
 * For each combination:
 *   1. Creates a sticker record via POST /api/stickers
 *   2. Triggers async generation via POST /api/stickers/:id/generate
 *   3. Polls GET /api/stickers/:id until status is "generated" or "failed"
 *   4. Downloads the first candidate image
 *   5. Saves it to "Batch testing/" folder
 *
 * Usage:
 *   node scripts/batch-test.mjs
 *
 * Environment variables (optional):
 *   API_BASE_URL  — server base URL (default: http://localhost:4000)
 *   CONCURRENCY    — max parallel generations (default: 3)
 *   THEMES         — comma-separated theme ids to limit scope (default: all 9)
 *   QUICK_PICKS    — comma-separated quick pick labels to limit scope (default: all 6)
 */

import { access, mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

// ──────────────────────────────────────────────
// Configuration
// ──────────────────────────────────────────────

const API_BASE_URL = process.env.API_BASE_URL || "http://localhost:4000";
const CONCURRENCY = Number(process.env.CONCURRENCY) || 3;

// Pick which themes and quick-picks to include (comma-separated env vars)
const THEME_FILTER = process.env.THEMES
  ? new Set(process.env.THEMES.split(",").map((s) => s.trim()))
  : null;
const QUICK_PICK_FILTER = process.env.QUICK_PICKS
  ? new Set(process.env.QUICK_PICKS.split(",").map((s) => s.trim()))
  : null;

const POLL_INTERVAL_MS = 3000; // check every 3s
const MAX_WAIT_MS = 20 * 60 * 1000; // 20 minutes timeout per generation

// ──────────────────────────────────────────────
// Festival & Quick Pick definitions
// ──────────────────────────────────────────────

const FESTIVALS = [
  {
    id: "general",
    label: "General",
    picks: [
      ["Classic Tram Ride", "riding happily on a classic Hong Kong tram with confident energy"],
      ["City Explorer", "exploring the city with a bright and welcoming expression"],
      ["Bell Helmet Hero", "standing proudly with the signature bell helmet in a clean sticker pose"],
      ["Team Greeting", "waving hello in a friendly greeting pose for a brand sticker"],
      ["Workshop Ready", "holding a simple notebook in a polished creative studio scene"],
      ["Choose for Me", "create a polished general TramPlus sticker with a balanced, versatile pose"],
    ],
  },
  {
    id: "lunar",
    label: "Lunar New Year",
    picks: [
      ["Lantern Dance", "dancing gracefully with glowing red lanterns and firecrackers"],
      ["Red Envelope", "holding a lucky red envelope, excited expression"],
      ["Lucky Dragon", "riding proudly on a golden lucky dragon"],
      ["Fireworks", "watching spectacular colorful fireworks light up the sky"],
      ["Tangyuan", "eating sweet sticky rice tangyuan balls with a happy smile"],
      ["Cheongsam", "wearing an elegant traditional red cheongsam dress"],
    ],
  },
  {
    id: "christmas",
    label: "Christmas",
    picks: [
      ["Santa Hat", "wearing a fluffy red Santa hat, merry and jolly"],
      ["Gift Box", "unwrapping a big Christmas present with excitement"],
      ["Snowman", "building a cheerful snowman in a snowy field"],
      ["Reindeer Ride", "riding Rudolph the red-nosed reindeer through the sky"],
      ["Cookies", "baking Christmas cookies wearing a tiny chef hat"],
      ["Caroling", "singing Christmas carols holding a tiny songbook"],
    ],
  },
  {
    id: "halloween",
    label: "Halloween",
    picks: [
      ["Pumpkin", "sitting inside a glowing carved jack-o-lantern"],
      ["Witch Hat", "casting a spell wearing a classic pointed witch hat"],
      ["Bat Wings", "flying with tiny bat wings under a full moon"],
      ["Ghost Costume", "dressed as an adorable ghost costume"],
      ["Spider Web", "tangled in a spooky spider web with a startled face"],
      ["Trick or Treat", "trick or treating holding a candy bucket"],
    ],
  },
  {
    id: "valentine",
    label: "Valentine",
    picks: [
      ["Love Letter", "writing a heartfelt love letter with a quill pen"],
      ["Roses", "holding a beautiful bouquet of red roses"],
      ["Cupid Arrow", "struck by a cupid arrow with heart-shaped eyes"],
      ["Chocolates", "presenting an elegant heart-shaped chocolate box"],
      ["Celebration Toast", "toasting with two tiny celebration glasses"],
      ["Heart Cloud", "floating happily on a pink cloud surrounded by hearts"],
    ],
  },
  {
    id: "midautumn",
    label: "Mid-Autumn Festival",
    picks: [
      ["Mooncake Time", "holding a mooncake proudly under the full moon"],
      ["Lantern Walk", "walking with a glowing lantern on a festive evening"],
      ["Moon Gazing", "looking up at a bright full moon with a calm happy smile"],
      ["Harbour Night", "enjoying a moonlit Hong Kong harbour night in sticker style"],
      ["Family Gathering", "celebrating a warm Mid-Autumn gathering with festive details"],
      ["Choose for Me", "create a polished Mid-Autumn sticker with moonlight and lantern details"],
    ],
  },
  {
    id: "dragonboat",
    label: "Dragon Boat Festival",
    picks: [
      ["Dragon Boat Race", "racing proudly on a dragon boat with energetic motion"],
      ["Rice Dumpling", "holding a traditional rice dumpling wrapped in bamboo leaves"],
      ["Victory Pose", "celebrating a strong finish after a dragon boat race"],
      ["Water Splash", "splashing through the water with dynamic festival energy"],
      ["Team Captain", "leading a dragon boat team with determined focus"],
      ["Choose for Me", "create a polished Dragon Boat Festival sticker with racing energy"],
    ],
  },
  {
    id: "easter",
    label: "Easter",
    picks: [
      ["Easter Egg", "carefully decorating a colorful Easter egg"],
      ["Bunny Ears", "hopping around happily wearing fluffy pink bunny ears"],
      ["Cherry Blossoms", "sitting peacefully in a field of cherry blossoms"],
      ["Baby Chick", "cuddling a tiny newly hatched baby chick"],
      ["Candy Hunt", "eagerly finding hidden Easter candies in the grass"],
      ["Pastel Rainbow", "skipping joyfully over a pastel rainbow"],
    ],
  },
  {
    id: "birthday",
    label: "Birthday",
    picks: [
      ["Birthday Cake", "presenting a birthday cake with a cheerful smile"],
      ["Wish Moment", "making a birthday wish beside glowing candles"],
      ["Party Hat", "wearing a neat party hat in a celebratory pose"],
      ["Gift Surprise", "opening a surprise gift box with excitement"],
      ["Celebrate Big", "posing in a bright birthday celebration scene"],
      ["Choose for Me", "create a polished birthday sticker with cheerful celebration details"],
    ],
  },
];

// ──────────────────────────────────────────────
// Helpers
// ──────────────────────────────────────────────

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(__dirname, "..");
const OUTPUT_DIR = path.join(PROJECT_ROOT, "Batch testing");

function slugify(value) {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "") || "untitled";
}

function log(level, msg) {
  const timestamp = new Date().toISOString().split("T")[1].slice(0, 12);
  const icon = { info: "[i]", ok: "[✓]", warn: "[!]", error: "[✗]" }[level] || "[?]";
  console.log(`${timestamp} ${icon} ${msg}`);
}

async function findExistingFile(dir, slug) {
  for (const ext of [".png", ".svg", ".gif", ".webp", ".jpg", ".jpeg"]) {
    const filePath = path.join(dir, `${slug}${ext}`);
    try {
      await access(filePath);
      return `${slug}${ext}`;
    } catch { /* not found, try next ext */ }
  }
  return null;
}

async function fetchJson(url, options = {}) {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.error ?? `${res.status} ${res.statusText} from ${url}`);
  }
  return res.json();
}

// ──────────────────────────────────────────────
// Single combination test
// ──────────────────────────────────────────────

async function testCombination({ themeId, themeLabel, quickPickLabel, quickPickPrompt }) {
  const description = `${themeLabel}: ${quickPickPrompt}`;
  const slug = slugify(`${themeId}_${quickPickLabel}`);
  const startedAt = Date.now();

  // Skip if already generated — check for any extension
  const existingFile = await findExistingFile(OUTPUT_DIR, slug);
  if (existingFile) {
    log("info", `Skipping "${slug}" (already exists: ${existingFile})`);
    return { slug, filename: existingFile, skipped: true };
  }

  // 1. Create sticker record (always SVG format)
  log("info", `Creating "${slug}" …`);
  const record = await fetchJson(`${API_BASE_URL}/api/stickers`, {
    method: "POST",
    body: JSON.stringify({ format: "svg", theme: themeId, description }),
  });

  // 2. Trigger generation (fires async background job)
  log("info", `  Generation queued for ${record.id}`);
  await fetchJson(`${API_BASE_URL}/api/stickers/${record.id}/generate`, {
    method: "POST",
    body: JSON.stringify({ theme: themeId, description }),
  });

  // 3. Poll until complete
  const deadline = Date.now() + MAX_WAIT_MS;
  let finalRecord;
  while (Date.now() < deadline) {
    await sleep(POLL_INTERVAL_MS);
    finalRecord = await fetchJson(`${API_BASE_URL}/api/stickers/${record.id}`);
    if (finalRecord.status === "generated" && finalRecord.result?.candidates?.length) {
      break;
    }
    if (finalRecord.status === "failed") {
      throw new Error(finalRecord.error || "Generation failed");
    }
    if (finalRecord.status !== "pending" && finalRecord.status !== "generating") {
      throw new Error(`Unexpected status: ${finalRecord.status}`);
    }
  }

  if (!finalRecord?.result?.candidates?.length) {
    throw new Error("Timed out waiting for generation");
  }

  // 4. Download the first candidate image
  const firstCandidate = finalRecord.result.candidates[0];
  const previewUrl = `${API_BASE_URL}/api/stickers/${record.id}/preview/0`;
  const imageResponse = await fetch(previewUrl);
  if (!imageResponse.ok) {
    throw new Error(`Failed to download candidate image: ${imageResponse.status}`);
  }
  const imageBuffer = Buffer.from(await imageResponse.arrayBuffer());

  // 5. Determine extension and save
  const ext = path.extname(firstCandidate) || ".png";
  const filename = `${slug}${ext}`;
  await writeFile(path.join(OUTPUT_DIR, filename), imageBuffer);

  const durationMs = Date.now() - startedAt;
  log("ok", `Saved "${filename}" (${(imageBuffer.length / 1024).toFixed(1)} KB) in ${(durationMs / 1000).toFixed(1)}s`);
  return { slug, filename, sizeBytes: imageBuffer.length, durationMs };
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// ──────────────────────────────────────────────
// Concurrency runner
// ──────────────────────────────────────────────

async function runWithConcurrency(tasks, concurrency) {
  const results = [];
  const queue = [...tasks];
  let completed = 0;
  const total = tasks.length;

  async function worker() {
    while (queue.length > 0) {
      const task = queue.shift();
      const label = `[${completed + 1}/${total}]`;
      try {
        const result = await task();
        if (result.skipped) {
          results.push({ skipped: true, ...result });
          completed++;
          log("warn", `${label} SKIP — ${result.filename} (already exists)`);
        } else {
          results.push({ success: true, ...result });
          completed++;
          log("ok", `${label} PASS — ${result.filename}`);
        }
      } catch (err) {
        results.push({ success: false, slug: task._slug, error: err.message });
        completed++;
        log("error", `${label} FAIL — ${task._slug}: ${err.message}`);
      }
    }
  }

  const workers = Array.from({ length: Math.min(concurrency, total) }, () => worker());
  await Promise.all(workers);
  return results;
}

// ──────────────────────────────────────────────
// Main
// ──────────────────────────────────────────────

async function main() {
  // Build the combination list
  const combinations = [];

  for (const theme of FESTIVALS) {
    if (THEME_FILTER && !THEME_FILTER.has(theme.id)) continue;
    for (const [pickLabel, pickPrompt] of theme.picks) {
      if (QUICK_PICK_FILTER && !QUICK_PICK_FILTER.has(pickLabel)) continue;
      combinations.push({ theme, pickLabel, pickPrompt });
    }
  }

  const picksPerTheme = combinations.length / FESTIVALS.length || FESTIVALS[0]?.picks.length || 6;
  const total = combinations.length;
  console.log(`\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`);
  console.log(`  Batch Testing — Ding Ding Cat Sticker Generator`);
  console.log(`━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`);
  console.log(`  Server:    ${API_BASE_URL}`);
  console.log(`  Output:    ${OUTPUT_DIR}`);
  console.log(`  Combos:    ${total} (${FESTIVALS.length} themes × ${picksPerTheme} quick picks)`);
  console.log(`  Parallel:  ${Math.min(CONCURRENCY, total)}`);
  console.log(`━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n`);

  // Ensure output directory exists
  await mkdir(OUTPUT_DIR, { recursive: true });

  const startedAt = Date.now();

  // Build task array
  const tasks = combinations.map(({ theme, pickLabel, pickPrompt }) => {
    const fn = () =>
      testCombination({
        themeId: theme.id,
        themeLabel: theme.label,
        quickPickLabel: pickLabel,
        quickPickPrompt: pickPrompt,
      });
    fn._slug = slugify(`${theme.id}_${pickLabel}`);
    return fn;
  });

  // Run with concurrency control
  const results = await runWithConcurrency(tasks, CONCURRENCY);

  // Summary
  const passed = results.filter((r) => r.success).length;
  const skipped = results.filter((r) => r.skipped).length;
  const failed = results.filter((r) => !r.success && !r.skipped).length;
  const totalDurationMs = Date.now() - startedAt;

  console.log(`\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`);
  console.log(`  Results: ${passed} passed, ${skipped} skipped, ${failed} failed out of ${total}`);
  console.log(`  Total time: ${(totalDurationMs / 1000 / 60).toFixed(1)} minutes`);
  console.log(`  Output folder: ${OUTPUT_DIR}`);
  console.log(`━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n`);

  if (failed > 0) {
    console.log("Failed combinations:");
    for (const r of results) {
      if (!r.success && !r.skipped) console.log(`  - ${r.slug}: ${r.error}`);
    }
    console.log();
  }

  process.exit(failed > 0 ? 1 : 0);
}

main().catch((err) => {
  console.error("Fatal error:", err);
  process.exit(2);
});
