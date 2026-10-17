import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const ALLOWED = "https://rera.karnataka.gov.in/complaintReportWiseList?";

function textOf(cell: string): string {
  return cell
    .replace(/<br\s*\/?>/gi, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/\s+/g, " ")
    .trim();
}

function hrefOf(cell: string): string {
  const match = cell.match(/href\s*=\s*["']([^"']+)["']/i);
  if (!match) return "";
  const href = match[1];
  if (href.startsWith("http")) return href;
  if (href.startsWith("/")) return `https://rera.karnataka.gov.in${href}`;
  return `https://rera.karnataka.gov.in/${href}`;
}

export async function GET(request: NextRequest) {
  const href = request.nextUrl.searchParams.get("href") ?? "";
  if (!href.startsWith(ALLOWED)) {
    return NextResponse.json({ error: "Only K-RERA complaint lists can be loaded." }, { status: 400 });
  }
  const response = await fetch(href, {
    headers: { "User-Agent": "Mozilla/5.0", Accept: "text/html" },
    cache: "no-store",
  });
  if (!response.ok) {
    return NextResponse.json({ error: `K-RERA returned ${response.status}` }, { status: 502 });
  }
  const html = await response.text();
  const rows: Record<string, string>[] = [];
  for (const tr of html.match(/<tr[\s\S]*?<\/tr>/gi) ?? []) {
    const cells = [...tr.matchAll(/<td[\s\S]*?<\/td>/gi)].map(match => match[0]);
    if (cells.length < 6) continue;
    const values = cells.map(textOf);
    if (!/\d/.test(values[1] ?? "") && !/CMP/i.test(values[1] ?? "")) continue;
    rows.push({
      complaintNo: values[1] ?? "",
      promoter: values[2] ?? "",
      project: values[3] ?? "",
      complainant: values[4] ?? "",
      status: values[5] ?? "",
      complaintDate: values[6] ?? "",
      disposedDate: values[7] ?? "",
      proceedingHref: hrefOf(cells[1] ?? ""),
      orderHref: hrefOf(cells[8] ?? ""),
    });
  }
  const title = textOf((html.match(/<h1[\s\S]*?<\/h1>/i) ?? [""])[0]).replace(/^Complaints List for\s*/i, "");
  return NextResponse.json({ title, href, rows });
}
