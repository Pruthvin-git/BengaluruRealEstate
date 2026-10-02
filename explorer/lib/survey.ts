export type SurveyHit = {
  number: string;
  village: string | null;
  clause: string;
};

const CLAUSE_RE =
  /(?:Sy\.?\s*Nos?\.?|Survey\s*Nos?\.?|S\.?\s*Nos?\.?)\s*[:.]?\s*([0-9][^.]{0,140})/gi;

const TOKEN_RE = /\b\d{1,4}(?:\/\d{1,4})?[A-Za-z]?\b/g;

function villageNear(address: string, index: number): string | null {
  const window = address.slice(Math.max(0, index - 40), index + 160);
  const after = window.match(/\b([A-Za-z][A-Za-z .'-]{1,40}?)\s+Village\b/i);
  if (after) return after[1].replace(/\s+/g, " ").trim();
  const before = window.match(/\bVillage\s*[:,]?\s*([A-Za-z][A-Za-z .'-]{1,40})/i);
  return before ? before[1].replace(/\s+/g, " ").trim() : null;
}

function tokens(clause: string): string[] {
  const found: string[] = [];
  for (const match of clause.matchAll(TOKEN_RE)) {
    const token = match[0].toUpperCase();
    const head = Number(token.split("/")[0]);
    if (!Number.isFinite(head) || head < 1 || head > 2000) continue;
    if (!found.includes(token)) found.push(token);
  }
  return found.slice(0, 8);
}

export function extractSurveys(address: string | undefined): SurveyHit[] {
  if (!address || address === "NA") return [];
  const hits: SurveyHit[] = [];
  const seen = new Set<string>();
  for (const match of address.matchAll(CLAUSE_RE)) {
    const raw = (match[1] ?? "")
      .split(/\b(?:of|village|hobli|taluk|taluka|bangalore|bengaluru|road|main)\b/i)[0]
      .replace(/\s+/g, " ")
      .trim()
      .replace(/[,;]+$/, "");
    if (raw.length < 1) continue;
    const village = villageNear(address, match.index ?? 0);
    for (const number of tokens(raw)) {
      const key = `${number}|${village ?? ""}`;
      if (seen.has(key)) continue;
      seen.add(key);
      hits.push({ number, village, clause: raw });
    }
  }
  return hits.slice(0, 8);
}

export function judgmentQuery(hit: SurveyHit, district: string, taluka: string): string {
  const place = [hit.village, taluka, district].filter(Boolean).join(" ");
  return `survey ${hit.number} ${place}`.replace(/\s+/g, " ").trim();
}
