import { randomUUID } from "node:crypto";
import { access, readFile } from "node:fs/promises";
import path from "node:path";
import { describe, test } from "node:test";
import assert from "node:assert/strict";
import {
  createStickerRecord,
  deleteStickerCache,
  getStickerRecord,
  updateStickerRecord,
} from "./stickerStorage.js";

const projectRoot = path.resolve(process.cwd(), "../..");

async function exists(filePath: string): Promise<boolean> {
  return access(filePath).then(
    () => true,
    () => false,
  );
}

describe("stickerStorage", () => {
  test("creates, updates, and deletes a cached JSON record", async () => {
    const suffix = randomUUID();
    const record = await createStickerRecord({
      format: "svg",
      theme: `test theme ${suffix}`,
      description: "storage lifecycle test",
    });

    assert.equal(record.status, "pending");
    assert.equal(record.cachePath, `data/history/test-theme-${suffix}/storage-lifecycle-test/request.json`);

    const absoluteCachePath = path.join(projectRoot, record.cachePath);
    assert.equal(await exists(absoluteCachePath), true);

    const updated = await updateStickerRecord(record.id, { status: "rejected" });
    assert.equal(updated.status, "rejected");

    const cachedJson = JSON.parse(await readFile(absoluteCachePath, "utf8")) as { status: string };
    assert.equal(cachedJson.status, "rejected");

    await deleteStickerCache(record.id);

    assert.equal(await getStickerRecord(record.id), undefined);
    assert.equal(await exists(path.dirname(path.dirname(absoluteCachePath))), false);
  });

  test("rejects duplicate theme and description cache paths", async () => {
    const suffix = randomUUID();
    const input = {
      format: "svg" as const,
      theme: `duplicate ${suffix}`,
      description: "duplicate test",
    };

    const record = await createStickerRecord(input);

    await assert.rejects(() => createStickerRecord(input), /Sticker cache already exists/);
    await deleteStickerCache(record.id);
  });
});
