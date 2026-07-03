import { app } from "./app.js";
import { config } from "./config.js";
import { cleanupOrphanedTrials } from "./services/cleanup.js";

app.listen(config.port, () => {
  console.log(`Sticker server listening on http://localhost:${config.port}`);
  console.log(`Nano Banana generation: ${config.nanoBananaApiKey ? "configured" : "not configured, using placeholder"}`);
  console.log(`Notion sync: ${config.notionToken && config.notionDatabaseId ? "configured" : "not configured"}`);

  void cleanupOrphanedTrials().then((count) => {
    if (count > 0) console.log(`Orphan cleanup: removed ${count} stale trial directories`);
  });
});
