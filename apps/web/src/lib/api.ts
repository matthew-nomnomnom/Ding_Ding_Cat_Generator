import type { CreateStickerInput, StickerRecord } from "@sticker-platform/shared";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { error?: string } | null;
    throw new Error(body?.error ?? `Request failed with ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export function listStickers(): Promise<StickerRecord[]> {
  return request<StickerRecord[]>("/api/stickers");
}

export function createSticker(input: CreateStickerInput): Promise<StickerRecord> {
  return request<StickerRecord>("/api/stickers", {
    body: JSON.stringify(input),
    method: "POST",
  });
}

export function getSticker(id: string): Promise<StickerRecord> {
  return request<StickerRecord>(`/api/stickers/${id}`);
}

export function generateSticker(id: string): Promise<StickerRecord> {
  return request<StickerRecord>(`/api/stickers/${id}/generate`, { method: "POST" });
}

export function rejectSticker(id: string): Promise<StickerRecord> {
  return request<StickerRecord>(`/api/stickers/${id}/reject`, { method: "POST" });
}

export function acceptSticker(id: string): Promise<{ uploaded: true; notionPageId: string }> {
  return request<{ uploaded: true; notionPageId: string }>(`/api/stickers/${id}/accept`, { method: "POST" });
}
