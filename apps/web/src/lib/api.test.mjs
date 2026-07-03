import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { describe, test } from "node:test";

async function loadPollGeneratedSticker() {
  const source = await readFile(new URL("./api.ts", import.meta.url), "utf8");
  const normalized = source.replace(/\r\n/g, "\n");
  const inProgressFunction = normalized.match(/function isGenerationInProgress[\s\S]*?\n}\n/)?.[0];
  const pollFunction = normalized.match(/async function pollGeneratedSticker[\s\S]*?\n}\n/)?.[0];

  assert.ok(inProgressFunction);
  assert.ok(pollFunction);

  const executableSource = `${inProgressFunction}\n${pollFunction}`
    .replaceAll(": StickerRecord", "")
    .replaceAll(": string", "")
    .replaceAll(": boolean", "")
    .replaceAll(": Promise<StickerRecord>", "");

  return (getSticker, wait, Date) => {
    return Function(
      "getSticker",
      "wait",
      "Date",
      "streamRecoveryTimeoutMs",
      "streamRecoveryPollMs",
      `${executableSource}\nreturn pollGeneratedSticker;`,
    )(getSticker, wait, Date, 12 * 60 * 1000, 2_000);
  };
}

describe("generation polling API", () => {
  test("starts generation with a POST and polls the sticker record", async () => {
    const source = await readFile(new URL("./api.ts", import.meta.url), "utf8");

    assert.match(source, /async function pollGeneratedSticker/);
    assert.match(source, /record\.status === "generated"/);
    assert.match(source, /record\.status === "pending"/);
    assert.match(source, /record\.status === "generating"/);
    assert.match(source, /!isGenerationInProgress\(record\)/);
    assert.match(source, /return request<StickerRecord>\(`\/api\/stickers\/\$\{id\}\/generate`/);
    assert.doesNotMatch(source, /text\/event-stream/);
    assert.doesNotMatch(source, /getReader\(/);
  });

  test("polling stops on non-generating terminal statuses", async () => {
    const createPollGeneratedSticker = await loadPollGeneratedSticker();
    const records = [{ status: "pending" }, { status: "approved" }];
    let pollCount = 0;
    let waitCount = 0;
    const pollGeneratedSticker = createPollGeneratedSticker(
      async () => {
        const record = records[pollCount++];

        if (!record) {
          throw new Error("Unexpected extra poll");
        }

        return record;
      },
      async () => {
        waitCount += 1;
      },
      { now: () => 0 },
    );

    await assert.rejects(() => pollGeneratedSticker("sticker-1"), /Generation stopped with status approved/);
    assert.equal(pollCount, 2);
    assert.equal(waitCount, 1);
  });
});

describe("generate and refine synchronous-first flow", () => {
  test("generateSticker returns early when already generated with candidates", async () => {
    const source = await readFile(new URL("./api.ts", import.meta.url), "utf8");

    assert.match(source, /export async function generateSticker\(/);
    assert.match(source, /const started = await startGeneration\(id, input\);/);
    assert.match(source, /if \(started\.status === "generated" && started\.result\?\.candidates\?\.length\) \{[\s\S]*return started;[\s\S]*\}/);
    assert.match(source, /return pollGeneratedSticker\(id\);/);
  });

  test("refineSticker returns early when already generated with candidates", async () => {
    const source = await readFile(new URL("./api.ts", import.meta.url), "utf8");

    assert.match(source, /export async function refineSticker\(/);
    assert.match(source, /const started = await request<StickerRecord>\(`\/api\/stickers\/\$\{id\}\/refine`/);
    assert.match(source, /if \(started\.status === "generated" && started\.result\?\.candidates\?\.length\) \{[\s\S]*return started;[\s\S]*\}/);
    assert.match(source, /return pollGeneratedSticker\(id\);/);
  });

  test("generateSticker calls onProgress with candidate count before sending request", async () => {
    const source = await readFile(new URL("./api.ts", import.meta.url), "utf8");

    assert.match(source, /onProgress\(0, input\?\.count \?\? 5, ""\);\s*const started = await startGeneration/);
  });

  test("refineSticker calls onProgress(0, 5, '') before sending request", async () => {
    const source = await readFile(new URL("./api.ts", import.meta.url), "utf8");

    assert.match(source, /onProgress\(0, 5, ""\);\s*const started = await request<StickerRecord>\(`\/api\/stickers\/\$\{id\}\/refine`/);
  });

  test("startGeneration POSTs to the correct route without unnecessary headers", async () => {
    const source = await readFile(new URL("./api.ts", import.meta.url), "utf8");

    assert.match(source, /function startGeneration\(id: string/);
    assert.match(source, /return request<StickerRecord>\(`\/api\/stickers\/\$\{id\}\/generate`/);
    assert.match(source, /method: "POST"/);
  });

  test("pollGeneratedSticker rejects when deadline is exceeded", async () => {
    const createPollGeneratedSticker = await loadPollGeneratedSticker();
    let elapsed = 0;
    const pollGeneratedSticker = createPollGeneratedSticker(
      async () => ({ status: "generating" }),
      async () => { elapsed += 2_000; },
      {
        now() { return elapsed; },
      },
    );

    await assert.rejects(() => pollGeneratedSticker("sticker-1"), /Generation timed out/);
  });
});

describe("removed feature safety checks", () => {
  test("uploadReferenceImage does not accept recordId or runId parameters", async () => {
    const source = await readFile(new URL("./api.ts", import.meta.url), "utf8");

    assert.match(source, /export function uploadReferenceImage\(/);
    assert.match(source, /fileName: string,[\s\S]*data: string,[\s\S]*theme: string,[\s\S]*description: string,/);
    assert.doesNotMatch(source, /recordId\?: string/);
    assert.doesNotMatch(source, /runId\?: string/);
  });

  test("does not export getCurrentSticker", async () => {
    const source = await readFile(new URL("./api.ts", import.meta.url), "utf8");

    assert.doesNotMatch(source, /export function getCurrentSticker/);
    assert.doesNotMatch(source, /\/api\/stickers\/current/);
  });

  test("does not use SSE or streaming for generation status", async () => {
    const source = await readFile(new URL("./api.ts", import.meta.url), "utf8");

    assert.doesNotMatch(source, /text\/event-stream/);
    assert.doesNotMatch(source, /getReader\(/);
    assert.doesNotMatch(source, /EventSource/);
  });
});
