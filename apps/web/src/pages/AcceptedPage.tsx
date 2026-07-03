import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { StickerRecord } from "@sticker-platform/shared";
import { listAllStickers } from "../lib/api";
import { FESTIVALS } from "./GeneratePage";

function getAssetUrl(filePath: string): string {
  const assetBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "";
  const normalizedPath = filePath.replace(/\\/g, "/");
  if (normalizedPath.startsWith("data/generated/")) {
    return `${assetBaseUrl}/${normalizedPath.replace(/^data\//, "")}`;
  }
  if (normalizedPath.startsWith(".runtime/generated/")) {
    return `${assetBaseUrl}/${normalizedPath.replace(/^\.runtime\//, "runtime/")}`;
  }
  return `${assetBaseUrl}/${normalizedPath}`;
}

function getImageUrl(record: StickerRecord): string | null {
  const fileUrl = record.result?.fileUrl;
  const localPath = record.result?.localPath;
  const selectedPath = record.result?.selectedPath;
  const path = fileUrl || localPath || selectedPath;
  if (!path) return null;
  return getAssetUrl(path);
}

function getThemeLabel(themeId: string): string {
  const festival = FESTIVALS.find((f) => f.id === themeId);
  return festival?.label ?? themeId;
}

const THEME_TABS = ["all", ...FESTIVALS.map((f) => f.id)];

export function AcceptedPage() {
  const navigate = useNavigate();
  const [records, setRecords] = useState<StickerRecord[]>([]);
  const [activeTab, setActiveTab] = useState("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lightboxImage, setLightboxImage] = useState<string | null>(null);

  const fetchRecords = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const all = await listAllStickers();
      const accepted = all.filter(
        (r) => r.status === "accepted" || r.status === "uploaded",
      );
      setRecords(accepted);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load accepted stickers");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchRecords();
  }, [fetchRecords]);

  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape" && lightboxImage) {
        setLightboxImage(null);
      }
    };
    window.addEventListener("keydown", handleEscape);
    return () => window.removeEventListener("keydown", handleEscape);
  }, [lightboxImage]);

  const filtered =
    activeTab === "all"
      ? records
      : records.filter((r) => r.theme === activeTab);

  return (
    <main className="page-shell">
      <nav className="topbar">
        <img className="brand-logo" src="/TramPlus_4C_BLK-01.png" alt="TramPlus" />
        <div className="topbar-meta">
          <button type="button" className="topbar-nav-link" onClick={() => navigate("/")}>Generator</button>
          <span className="topbar-nav-link active">Gallery</span>
        </div>
      </nav>

      <section className="gallery-section">
        <div className="gallery-head">
          <span className="eyebrow">Gallery</span>
          <h2 className="card-title">Accepted Stickers</h2>
          <p className="helper-text">
            {records.length} accepted sticker{records.length !== 1 ? "s" : ""} across {new Set(records.map((r) => r.theme)).size} theme{new Set(records.map((r) => r.theme)).size !== 1 ? "s" : ""}
          </p>
        </div>

        <div className="theme-tabs">
          {THEME_TABS.map((tabId) => (
            <button
              key={tabId}
              className={activeTab === tabId ? "theme-tab active" : "theme-tab"}
              type="button"
              onClick={() => setActiveTab(tabId)}
            >
              {tabId === "all" ? "All" : getThemeLabel(tabId)}
              {tabId === "all" ? (
                <span className="tab-count">{records.length}</span>
              ) : (
                <span className="tab-count">
                  {records.filter((r) => r.theme === tabId).length}
                </span>
              )}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="loading-state">
            <div className="spinner" />
            <p>Loading accepted stickers...</p>
          </div>
        ) : error ? (
          <p className="form-message error">{error}</p>
        ) : filtered.length === 0 ? (
          <div className="empty-state gallery-empty">
            <div className="empty-icon">T+</div>
            <p>
              {activeTab === "all"
                ? "No accepted stickers yet. Generate and accept some stickers to see them here."
                : `No accepted stickers in ${getThemeLabel(activeTab)} yet.`}
            </p>
          </div>
        ) : (
          <div className="accepted-grid">
            {filtered.map((record) => {
              const imgUrl = getImageUrl(record);
              return (
                <button
                  key={record.id}
                  className="accepted-card"
                  type="button"
                  onClick={() => imgUrl && setLightboxImage(imgUrl)}
                  aria-label={`View ${record.description}`}
                >
                  {imgUrl ? (
                    <img src={imgUrl} alt={record.description} loading="lazy" />
                  ) : (
                    <div className="accepted-placeholder">No image</div>
                  )}
                  <div className="accepted-label">
                    {record.description.slice(0, 40)}
                    {record.description.length > 40 ? "…" : ""}
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </section>

      <footer className="footer-mark">TramPlus Ding Ding Cat AI Image Generator · Built for a crisp, premium brand experience</footer>

      {lightboxImage ? (
        <div className="lightbox-overlay" onClick={() => setLightboxImage(null)}>
          <button className="lightbox-close" onClick={() => setLightboxImage(null)} aria-label="Close lightbox">✕</button>
          <img className="lightbox-image" src={lightboxImage} alt="Enlarged sticker" onClick={(e) => e.stopPropagation()} />
        </div>
      ) : null}
    </main>
  );
}
