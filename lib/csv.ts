export function parseCsv(text: string): Record<string, string>[] {
  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let quote = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quote && c === '"' && text[i + 1] === '"') {
      field += c;
      i++;
    } else if (c === '"') quote = !quote;
    else if (c === "," && !quote) {
      row.push(field);
      field = "";
    } else if ((c === "\n" || c === "\r") && !quote) {
      if (c === "\r" && text[i + 1] === "\n") i++;
      row.push(field);
      if (row.length > 1) rows.push(row);
      row = [];
      field = "";
    } else field += c;
  }
  if (field || row.length) {
    row.push(field);
    rows.push(row);
  }
  const [headers, ...body] = rows;
  if (!headers) return [];
  return body
    .map(values => Object.fromEntries(headers.map((header, index) => [header.trim(), values[index] ?? ""])))
    .filter(project => project["Registration Number"]);
}
