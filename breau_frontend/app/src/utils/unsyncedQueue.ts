// src/utils/unsyncedQueue.ts
type Item = { id: string; payload: any; createdAt: number; endpoint: string; method: string };

const keyFor = (userId: string) => `breau.queue.${userId || "default-user"}`;

function load(userId: string): Item[] {
  try {
    const raw = localStorage.getItem(keyFor(userId));
    return raw ? (JSON.parse(raw) as Item[]) : [];
  } catch {
    return [];
  }
}

function save(userId: string, items: Item[]) {
  try { localStorage.setItem(keyFor(userId), JSON.stringify(items)); } catch {}
}

export function enqueue(userId: string, payload: any, endpoint: string, method = "POST"): string {
  const id = `q_${Math.random().toString(36).slice(2)}_${Date.now().toString(36)}`;
  const items = load(userId);
  items.push({ id, payload, createdAt: Date.now(), endpoint, method });
  save(userId, items);
  return id;
}

export function peek(userId: string): Item | undefined {
  return load(userId)[0];
}

export function shift(userId: string): Item | undefined {
  const items = load(userId);
  const x = items.shift();
  save(userId, items);
  return x;
}

export function clearQueue(userId: string) {
  save(userId, []);
}

export function size(userId: string) {
  return load(userId).length;
}
