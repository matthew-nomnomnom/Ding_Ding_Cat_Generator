# Reference Upload Notion Persistence Design

## Goal

When a user uploads a reference image, the upload succeeds only after the file is saved to the Notion `reference` database. A missing Notion configuration or Notion API failure must fail the upload request so the frontend can stop generation and show the error.

## Current Behavior

The web app reads the selected image as a data URL and posts JSON to `POST /api/stickers/upload-reference`. The server validates the payload, writes the image to runtime upload storage, optionally uploads it to Blob storage, and then attempts to write a `reference` row in Notion. The Notion write is currently wrapped in a swallowed `catch`, so the API can return success even when Notion persistence did not happen.

## Selected Approach

Use strict Notion persistence for the existing upload route.

The frontend API shape remains mostly unchanged: users still choose an image before generation, and generation only starts after the reference upload returns successfully. The backend keeps writing the runtime file because generation uses the returned runtime path. The backend also keeps the existing Notion data model, using the `reference` child database and the existing `uploadDataFolderFile` service.

The required behavior change is that `POST /api/stickers/upload-reference` must not swallow Notion errors. It should return success only after `uploadDataFolderFile` resolves with a real Notion page id. The JSON response should include `notionPageId` along with the existing `path` and optional `blobPathname`.

## Error Handling

If `NOTION_TOKEN` or `NOTION_DATABASE_ID` is missing, the upload route should fail instead of returning `notion-not-configured`. If Notion rejects the file upload, database lookup, page creation, or page update, Express error handling should return an error response and the frontend should show the existing error message.

Runtime local files may remain after a failed Notion upload. That is acceptable for this change because the user-visible contract is that generation will not continue unless Notion persistence succeeds.

## Testing

Update the upload route tests so they verify strict persistence behavior:

- A missing Notion configuration causes `POST /api/stickers/upload-reference` to fail.
- The route response type includes a `notionPageId` when Notion persistence succeeds.

Existing schema validation tests should continue to pass.

## Out Of Scope

- Replacing the JSON data URL upload with multipart form upload.
- Removing runtime local file storage.
- Adding retry queues or background Notion sync.
- Changing the Notion database schema beyond using the existing `reference` table.
