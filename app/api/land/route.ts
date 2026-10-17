import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const CLAUSE_RE =
  /(?:Sy\.?\s*Nos?\.?|Survey\s*Nos?\.?|S\.?\s*Nos?\.?)\s*[:.]?\s*[0-9][^.]{0,120}/gi;

export async function GET(request: NextRequest) {
  const action = request.nextUrl.searchParams.get("action") ?? "";
  if (!/^\d{1,8}$/.test(action)) {
    return NextResponse.json({ error: "Missing K-RERA action id." }, { status: 400 });
  }
  const response = await fetch("https://rera.karnataka.gov.in/projectDetails", {
    method: "POST",
    headers: {
      "User-Agent": "Mozilla/5.0",
      "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
      "X-Requested-With": "XMLHttpRequest",
      Origin: "https://rera.karnataka.gov.in",
      Referer: "https://rera.karnataka.gov.in/projectViewDetails",
    },
    body: `action=${action}`,
    cache: "no-store",
  });
  if (!response.ok) {
    return NextResponse.json({ error: `K-RERA returned ${response.status}` }, { status: 502 });
  }
  const html = await response.text();
  const plain = html
    .replace(/<script[\s\S]*?<\/script>/gi, " ")
    .replace(/<style[\s\S]*?<\/style>/gi, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/\s+/g, " ");
  const bySurvey = new Map<string, string>();
  for (const item of plain.match(CLAUSE_RE) ?? []) {
    const clause = item.replace(/\s+/g, " ").trim();
    const token = clause.match(/\d{1,4}(?:\/\d{1,4})?/)?.[0] ?? clause;
    const prev = bySurvey.get(token);
    if (!prev || clause.length > prev.length) bySurvey.set(token, clause);
  }
  const clauses = [...bySurvey.values()].slice(0, 6);
  return NextResponse.json({
    action,
    clauses,
    portal: "https://rera.karnataka.gov.in/viewAllProjects",
  });
}
