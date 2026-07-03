const STORAGE_KEY = "ding-sessions";
const MAX_SESSIONS = 10;

export interface SavedSession {
  id: string;
  prompt: string;
  festival: string;
  quickPick: string;
  time: number;
}

export function loadSessions(): SavedSession[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((s) => s && typeof s.id === "string");
  } catch {
    return [];
  }
}

export function saveSession(session: SavedSession): void {
  try {
    const sessions = loadSessions().filter((s) => s.id !== session.id);
    sessions.unshift(session);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions.slice(0, MAX_SESSIONS)));
  } catch {
    // localStorage may be full or disabled
  }
}

export function removeSession(id: string): void {
  try {
    const sessions = loadSessions().filter((s) => s.id !== id);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
  } catch {
    // ignore
  }
}
