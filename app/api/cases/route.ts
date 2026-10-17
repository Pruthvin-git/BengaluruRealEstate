import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

function clean(value: string): string {
  return value
    .replace(/<[^>]+>/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&#39;|&apos;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/\s+/g, " ")
    .trim();
}

export async function GET(request: NextRequest) {
  const query = (request.nextUrl.searchParams.get("q") ?? "").replace(/\s+/g, " ").trim();
  if (query.length < 6 || query.length > 180) {
    return NextResponse.json({ error: "Survey search needs a survey number and a place." }, { status: 400 });
  }
  const formInput = `${query} doctypes:karnataka`;
  const searchUrl = `https://indiankanoon.org/search/?formInput=${encodeURIComponent(formInput)}`;
  const response = await fetch(searchUrl, {
    headers: {
      "User-Agent": "Mozilla/5.0 (compatible; KRERA-explorer/1.0; personal research)",
      Accept: "text/html",
    },
    cache: "no-store",
  });
  if (!response.ok) {
    return NextResponse.json(
      {
        query,
        searchUrl,
        results: [],
        error: `Indian Kanoon returned ${response.status}. Open the search link instead.`,
      },
      { status: 200 },
    );
  }
  const html = await response.text();
  const results: { title: string; url: string; snippet: string }[] = [];
  const blocks = html.split('class="result_title"').slice(1, 9);
  for (const block of blocks) {
    const link = block.match(/href\s*=\s*["']([^"']+)["'][^>]*>([\s\S]*?)<\/a>/i);
    if (!link) continue;
    const snippetMatch = block.match(/class="hltext"[\s\S]*?<\/div>/i);
    const path = link[1];
    results.push({
      title: clean(link[2]),
      url: path.startsWith("http") ? path : `https://indiankanoon.org${path.startsWith("/") ? path : `/${path}`}`,
      snippet: snippetMatch ? clean(snippetMatch[0]).slice(0, 280) : "",
    });
  }
  return NextResponse.json({
    query,
    searchUrl,
    results,
    note: "Published Karnataka judgments whose text matched this survey wording. A hit is not proof the case is about that plot.",
  });
}
