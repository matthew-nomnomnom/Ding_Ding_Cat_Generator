# Reference Upload Notion Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make user reference image uploads succeed only after the file is saved to the Notion `reference` database.

**Architecture:** Keep the current Vite React JSON upload flow and Express route. Change the server route so Notion persistence is mandatory and the successful response includes the Notion page id returned by `uploadDataFolderFile`.

**Tech Stack:** Vite, React, TypeScript, Express 5, Zod, Node test runner, Notion REST API through the existing `apps/server/src/services/notion.ts` service.

## Global Constraints

- Preserve the existing upload UI and API endpoint: `POST /api/stickers/upload-reference`.
- Keep runtime local file storage because generation uses the returned runtime path.
- Do not replace the JSON data URL upload with multipart form upload in this change.
- Do not add retry queues or background Notion sync.
- A missing `NOTION_TOKEN` or `NOTION_DATABASE_ID` must fail the upload request.
- A Notion API error must fail the upload request.
- The successful upload response must include `notionPageId` with `path` and optional `blobPathname`.
- Do not commit unless the user explicitly asks for a commit.

---

## File Structure

- Modify: `apps/server/src/routes/stickers.ts`
  - Responsibility: validate reference upload payloads, write runtime upload files, call Notion persistence, and return the upload response.
- Modify: `apps/server/src/routes/upload-reference.test.ts`
  - Responsibility: verify schema behavior and strict upload route behavior.
- Modify: `apps/web/src/lib/api.ts`
  - Responsibility: keep frontend response typing aligned with the route by adding `notionPageId` to `uploadReferenceImage` return type.

### Task 1: Strict Notion Persistence For Reference Uploads

**Files:**
- Modify: `apps/server/src/routes/upload-reference.test.ts`
- Modify: `apps/server/src/routes/stickers.ts`
- Modify: `apps/web/src/lib/api.ts`

**Interfaces:**
- Consumes: `uploadDataFolderFile(file: DataFolderFile): Promise<string>` from `apps/server/src/services/notion.ts`.
- Produces: `POST /api/stickers/upload-reference` response shape `{ path: string; blobPathname?: string; notionPageId: string }`.
- Produces: frontend function `uploadReferenceImage(fileName: string, data: string, theme: string, description: string): Promise<{ path: string; blobPathname?: string; notionPageId: string }>`.

- [ ] **Step 1: Write the failing route test for missing Notion configuration**

Replace the existing `POST /api/stickers/upload-reference` test in `apps/server/src/routes/upload-reference.test.ts` with this stricter test. Keep the imports and schema tests already in the file.

```ts
describe("POST /api/stickers/upload-reference", () => {
  test("fails when Notion is not configured", async () => {
    const originalNotionToken = config.notionToken;
    const originalNotionDatabaseId = config.notionDatabaseId;
    config.notionToken = "";
    config.notionDatabaseId = "";

    const server = createServer(app);
    await new Promise<void>((resolve) => server.listen(0, resolve));
    const baseUrl = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;

    try {
      const uploadResponse = await fetch(`${baseUrl}/api/stickers/upload-reference`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          fileName: "cat.png",
          data: `data:image/png;base64,${testPngBase64}`,
          theme: "reference route",
          description: "stores reference in notion",
        }),
      });

      assert.equal(uploadResponse.status, 500);
      const body = (await uploadResponse.json()) as { error?: string };
      assert.match(body.error ?? "", /Notion is not configured|NOTION_TOKEN|NOTION_DATABASE_ID/);
    } finally {
      config.notionToken = originalNotionToken;
      config.notionDatabaseId = originalNotionDatabaseId;
      await new Promise<void>((resolve, reject) => server.close((error) => (error ? reject(error) : resolve())));
    }
  });
});
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run: `npm run test --workspace apps/server -- src/routes/upload-reference.test.ts`

Expected: FAIL because the route currently returns `200` when Notion is not configured.

- [ ] **Step 3: Make Notion configuration mandatory inside the upload route**

In `apps/server/src/routes/stickers.ts`, add a small assertion helper after `withoutCandidatePreviews`.

```ts
function assertNotionConfigured(): void {
  if (!config.notionToken || !config.notionDatabaseId) {
    throw Object.assign(new Error("Notion is not configured"), { statusCode: 500 });
  }
}
```

Then update the `/upload-reference` route so it calls the helper before writing files and so it no longer swallows `uploadDataFolderFile` errors. Replace the current `try { await uploadDataFolderFile(...) } catch { ... }` block with this code.

```ts
    assertNotionConfigured();

    const contentName = await getAvailableNotionContentName("reference", themeSlug, descriptionSlug, safeExtension);
    const notionPageId = await uploadDataFolderFile({
      group: "reference",
      category: themeSlug,
      content: contentName,
      relativePath,
      absolutePath: filePath,
      data: body,
      sizeBytes: body.byteLength,
      updatedAt: new Date().toISOString(),
    });

    if (notionPageId === "notion-not-configured") {
      throw Object.assign(new Error("Notion is not configured"), { statusCode: 500 });
    }

    res.json({ path: relativePath, blobPathname, notionPageId });
```

Remove the old `res.json({ path: relativePath, blobPathname });` line because the route now responds with `notionPageId`.

- [ ] **Step 4: Run the focused test and verify it passes**

Run: `npm run test --workspace apps/server -- src/routes/upload-reference.test.ts`

Expected: PASS for all `upload-reference.test.ts` tests.

- [ ] **Step 5: Update frontend upload response typing**

In `apps/web/src/lib/api.ts`, change the `uploadReferenceImage` return type and request type from this:

```ts
): Promise<{ path: string; blobPathname?: string }> {
  return request<{ path: string; blobPathname?: string }>("/api/stickers/upload-reference", {
```

to this:

```ts
): Promise<{ path: string; blobPathname?: string; notionPageId: string }> {
  return request<{ path: string; blobPathname?: string; notionPageId: string }>("/api/stickers/upload-reference", {
```

No UI change is required because `GeneratePage.tsx` only needs `path` and `blobPathname` to continue generation after upload success.

- [ ] **Step 6: Run full verification**

Run: `npm run typecheck`

Expected: PASS.

Run: `npm run test`

Expected: PASS.

- [ ] **Step 7: Inspect changed files**

Run: `git diff -- apps/server/src/routes/stickers.ts apps/server/src/routes/upload-reference.test.ts apps/web/src/lib/api.ts docs/superpowers/specs/2026-06-24-reference-upload-notion-design.md docs/superpowers/plans/2026-06-24-reference-upload-notion.md`

Expected: Diff only contains the strict Notion upload changes, the approved spec, and this plan.

## Self-Review

- Spec coverage: The plan covers mandatory Notion persistence, missing config failure, Notion error propagation, successful `notionPageId` response typing, preservation of runtime local storage, and no multipart/retry/sync changes.
- Placeholder scan: No placeholders remain.
- Type consistency: The route and frontend both use `{ path: string; blobPathname?: string; notionPageId: string }`; the helper returns `void`; `uploadDataFolderFile` remains unchanged.
