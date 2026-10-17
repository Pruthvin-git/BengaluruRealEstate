export function normName(value: string | undefined): string {
  return (value ?? "")
    .toUpperCase()
    .replace(/&/g, " AND ")
    .replace(/[^A-Z0-9]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export type NamedCount = { name: string; count: number; href: string };

export type NameIndex = {
  exact: Map<string, NamedCount>;
  byToken: Map<string, NamedCount[]>;
};

export function indexByName(items: NamedCount[]): NameIndex {
  const exact = new Map<string, NamedCount>();
  const byToken = new Map<string, NamedCount[]>();
  for (const item of items) {
    const key = normName(item.name);
    if (!key) continue;
    const prev = exact.get(key);
    if (!prev || item.count > prev.count) exact.set(key, item);
    const token = key.split(" ")[0];
    if (token.length < 4) continue;
    const bucket = byToken.get(token);
    if (bucket) bucket.push(item);
    else byToken.set(token, [item]);
  }
  return { exact, byToken };
}

export function lookupName(index: NameIndex, name: string | undefined): NamedCount | null {
  const key = normName(name);
  if (!key || key.length < 3) return null;
  const exact = index.exact.get(key);
  if (exact) return exact;
  if (key.length < 8) return null;
  const bucket = index.byToken.get(key.split(" ")[0]) ?? [];
  let found: NamedCount | null = null;
  for (const item of bucket) {
    const candidate = normName(item.name);
    if (candidate.length < 8) continue;
    const shorter = key.length < candidate.length ? key : candidate;
    const longer = key.length < candidate.length ? candidate : key;
    if (longer.includes(shorter) && shorter.length / longer.length >= 0.72) {
      if (!found || item.count > found.count) found = item;
    }
  }
  return found;
}
