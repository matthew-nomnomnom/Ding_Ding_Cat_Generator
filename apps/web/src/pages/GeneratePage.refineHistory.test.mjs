import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { describe, test } from "node:test";

async function loadSource() {
  return readFile(new URL("./GeneratePage.tsx", import.meta.url), "utf8");
}

describe("refine history session", () => {
  test("declares refineHistory state with correct shape (no legacy HistoryItem)", async () => {
    const source = await loadSource();

    assert.match(source, /const \[refineHistory, setRefineHistory\] = useState<\{/);
    assert.match(source, /previewUrl: string;/);
    assert.match(source, /description: string;/);
    assert.match(source, /subtitle: string;/);
    assert.match(source, /time: number;/);
    assert.match(source, /record: StickerRecord;/);
    assert.match(source, /previews: Record<string, string>;/);
    assert.doesNotMatch(source, /interface HistoryItem/);
    assert.doesNotMatch(source, /const \[history, setHistory\]/);
  });

  test("restoreFromHistory restores record, previews, selectedPath, description, theme and closes refine panel", async () => {
    const source = await loadSource();

    assert.match(source, /function restoreFromHistory\(item: typeof refineHistory\[number\]\) \{/);
    assert.match(source, /setRecord\(item\.record\);/);
    assert.match(source, /setCandidatePreviews\(item\.previews\);/);
    assert.match(source, /setSelectedPath\(item\.record\.result\?\.selectedPath \?\? item\.record\.result\?\.candidates\?\.\[0\] \?\? null\);/);
    assert.match(source, /setShowRefinePanel\(false\);/);
    assert.match(source, /setDescription\(item\.description\);/);
    assert.match(source, /setFestivalId\(item\.record\.theme === "general" \? "" : item\.record\.theme\);/);
  });

  test("scrollRefineHistory uses scrollRef and .refine-thumb selector with smooth scroll", async () => {
    const source = await loadSource();

    assert.match(source, /function scrollRefineHistory\(direction: "left" \| "right"\) \{/);
    assert.match(source, /const container = scrollRef\.current;/);
    assert.match(source, /container\.querySelector\("\.refine-thumb"\)/);
    assert.match(source, /container\.scrollBy\(\{[\s\S]*left: direction === "left" \? -itemWidth : itemWidth,[\s\S]*behavior: "smooth"/);
    assert.match(source, /const gap = 10;/);
    assert.match(source, /const itemWidth = thumb \? thumb\.offsetWidth \+ gap : 95;/);
  });

  test("previewsRef captures candidate previews before react state update", async () => {
    const source = await loadSource();

    assert.match(source, /const previewsRef = useRef<Record<string, string>>\(\{\}\);/);
    assert.match(source, /previewsRef\.current\[candidate\] = preview;/);
    assert.match(source, /previews: \{ \.\.\.previewsRef\.current \}/);
  });

  test("replaces old History sidebar heading with Refine History", async () => {
    const source = await loadSource();

    assert.match(source, /<h2>Refine History<\/h2>/);
    assert.doesNotMatch(source, /Recent Ding Ding Cat generations/);
    assert.match(source, /<span>\{refineHistory\.length\}<\/span> items/);
  });

  test("empty state shows guidance text when refineHistory is empty", async () => {
    const source = await loadSource();

    assert.match(source, /refineHistory\.length === 0/);
    assert.match(source, /Refined images will appear here\. Use the Refine button to iterate on your design\./);
    assert.doesNotMatch(source, /No generations yet\. Your Ding Ding Cat results will appear here/);
  });

  test("renders refine-scroll-wrapper with left and right arrow buttons", async () => {
    const source = await loadSource();

    assert.match(source, /className="refine-scroll-wrapper"/);
    assert.match(source, /className="refine-scroll-btn refine-scroll-left"/);
    assert.match(source, /className="refine-scroll-btn refine-scroll-right"/);
    assert.match(source, /aria-label="Scroll left"/);
    assert.match(source, /aria-label="Scroll right"/);
    assert.match(source, /className="refine-scroll-container"[^>]*ref=\{scrollRef\}/);
  });

  test("refine-thumb buttons are disabled when busy", async () => {
    const source = await loadSource();

    assert.match(source, /className="refine-scroll-btn refine-scroll-left"[^>]*disabled=\{busy\}/);
    assert.match(source, /className="refine-scroll-btn refine-scroll-right"[^>]*disabled=\{busy\}/);
    assert.match(source, /className="refine-thumb"[^>]*disabled=\{busy\}/);
  });

  test("refine-thumb click restores history, double-click opens lightbox", async () => {
    const source = await loadSource();

    assert.match(source, /onClick=\{\(\) => restoreFromHistory\(item\)\}/);
    assert.match(source, /onDoubleClick=\{\(e\) => \{ e\.stopPropagation\(\); setLightboxImage\(item\.previewUrl\); \}\}/);
    assert.match(source, /<img[\s\S]*src=\{item\.previewUrl\}[\s\S]*alt=\{item\.description\}/);
    assert.match(source, /<div className="thumb-subtitle">\{item\.subtitle\}<\/div>/);
  });

  test("history entries are prepended using spread before existing array", async () => {
    const source = await loadSource();

    const prependMatches = source.match(/setRefineHistory\(\(prev\) => \[\{[\s\S]*?\}, \.\.\.prev\]\)/g);
    assert.ok(prependMatches, "Expected setRefineHistory to prepend entries using [...prev]");
    assert.ok(prependMatches.length >= 2, "Expected at least 2 prepend sites (generate + refine)");
  });

  test("handleGenerate adds refine history entry with reference image or candidate preview", async () => {
    const source = await loadSource();

    assert.match(source, /historyPreviewUrl = photoPreview;/);
    assert.match(source, /previewUrl: historyPreviewUrl \|\| getCandidatePreviewUrl\(generatedRecord, generatedRecord\.result\?\.candidates\?\.\[0\] \?\? "", prev/);
    assert.match(source, /subtitle: historyPreviewUrl \? "Reference image" : prompt/);
    assert.match(source, /subtitle: historyPreviewUrl \? "Reference image" : prompt/);
  });

  test("handleRefine captures selected candidate preview for history entry", async () => {
    const source = await loadSource();

    assert.match(source, /const refinePreviewUrl = selectedCandidate[\s\S]*\? getCandidatePreviewUrl\(record, selectedCandidate, candidatePreviews\)/);
    assert.match(source, /if \(refinePreviewUrl\) \{[\s\S]*previewUrl: refinePreviewUrl,/);
    assert.match(source, /subtitle: refinementRequirement\.trim\(\),/);
    assert.match(source, /description: record\.description,/);
  });

  test("does not import or reference getCurrentSticker", async () => {
    const source = await loadSource();

    assert.doesNotMatch(source, /getCurrentSticker/);
  });

  test("does not have a polling useEffect for generation status", async () => {
    const source = await loadSource();

    assert.doesNotMatch(source, /useEffect\(\(\) => \{\s*if \(!record \|\| record\.status !== "generating"\) return;/);
    assert.doesNotMatch(source, /window\.setInterval\(async \(\) => \{\s*try \{\s*const latest = await getSticker\(/);
  });

  test("does not have a restoreCurrentRun useEffect", async () => {
    const source = await loadSource();

    assert.doesNotMatch(source, /async function restoreCurrentRun\(\)/);
    assert.doesNotMatch(source, /getCurrentSticker\(\)/);
  });

  test("session restore uses getCandidatePreviewUrl instead of transparent GIF fallback", async () => {
    const source = await loadSource();

    assert.match(source, /previewUrl: getCandidatePreviewUrl\(rec, firstCandidate, previewsMap\)/);
    assert.doesNotMatch(source, /data:image\/gif;base64,R0lGODlhAQAB/);
  });

  test("session restore populates previews from server-side candidatePreviews", async () => {
    const source = await loadSource();

    assert.match(source, /const previewsMap = rec\.result\?\.candidatePreviews \?\? \{\};/);
    assert.match(source, /previews: previewsMap/);
  });

  test("session restore auto-restores latest session into main controls", async () => {
    const source = await loadSource();

    assert.match(source, /setRecord\(latest\.record\);/);
    assert.match(source, /setCandidatePreviews\(latest\.previews\);/);
    assert.match(source, /setDescription\(latest\.description\);/);
    assert.match(source, /setFestivalId\(latest\.record\.theme === "general" \? "" : latest\.record\.theme\);/);
  });
});
