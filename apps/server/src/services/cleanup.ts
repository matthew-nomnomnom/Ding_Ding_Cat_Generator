import type { StickerRecord } from "@sticker-platform/shared";
import { readdir, rm, stat } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { config } from "../config.js";

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../../..");
const runtimeGeneratedRoot = config.runtimeGeneratedRoot;

const ORPHAN_MAX_AGE_MS = 12 * 60 * 60 * 1000;

export async function deleteStickerGeneratedFiles(record: StickerRecord): Promise<void> {
  const candidates = record.result?.candidates;
  if (!candidates || candidates.length === 0) return;

  for (const candidatePath of candidates) {
    if (!candidatePath.startsWith(".runtime/generated/")) continue;

    const relativePath = path.relative(".runtime/generated", candidatePath);
    const trialRelPath = path.dirname(relativePath);
    const trialDir = path.join(runtimeGeneratedRoot, trialRelPath);

    try {
      const s = await stat(trialDir);
      if (s.isDirectory()) {
        await rm(trialDir, { recursive: true, force: true });
        await removeEmptyParentDirs(trialDir);
        return;
      }
    } catch {
      continue;
    }
  }
}

async function removeEmptyParentDirs(dir: string): Promise<void> {
  let current = path.dirname(dir);
  while (current.startsWith(runtimeGeneratedRoot) && current !== runtimeGeneratedRoot) {
    try {
      const entries = await readdir(current);
      if (entries.length > 0) return;
      await rm(current, { force: true, recursive: true });
    } catch {
      return;
    }
    current = path.dirname(current);
  }
}

export async function cleanupOrphanedTrials(): Promise<number> {
  const now = Date.now();
  let removed = 0;

  try {
    const themes = await readdir(runtimeGeneratedRoot, { withFileTypes: true });
    for (const themeDir of themes) {
      if (!themeDir.isDirectory()) continue;
      const themePath = path.join(runtimeGeneratedRoot, themeDir.name);

      const motions = await readdir(themePath, { withFileTypes: true }).catch(() => []);
      for (const motionDir of motions) {
        if (!motionDir.isDirectory()) continue;
        const motionPath = path.join(themePath, motionDir.name);

        const trials = await readdir(motionPath, { withFileTypes: true }).catch(() => []);
        for (const trialDir of trials) {
          if (!trialDir.isDirectory() || !trialDir.name.startsWith("trial-")) continue;
          const trialPath = path.join(motionPath, trialDir.name);

          try {
            const s = await stat(trialPath);
            if (now - s.mtimeMs > ORPHAN_MAX_AGE_MS) {
              await rm(trialPath, { recursive: true, force: true });
              removed++;
            }
          } catch {
            continue;
          }
        }

        const remaining = await readdir(motionPath).catch(() => []);
        if (remaining.length === 0) {
          await rm(motionPath, { recursive: true, force: true });
        }
      }

      const remaining = await readdir(themePath).catch(() => []);
      if (remaining.length === 0) {
        await rm(themePath, { recursive: true, force: true });
      }
    }
  } catch {
    // runtimeGeneratedRoot may not exist yet
  }

  return removed;
}

export async function cleanupAllRuntimeFiles(record: StickerRecord): Promise<void> {
  await deleteStickerGeneratedFiles(record);
}
