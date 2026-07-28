export function formulaSafeCsvText(value: string): string {
  return /^[\t\r\n ]*[=+\-@]/.test(value) ? `'${value}` : value;
}

export function csvCell(value: unknown): string {
  const text =
    value === null || value === undefined
      ? ""
      : Array.isArray(value)
        ? value.join(" | ")
        : String(value);
  return `"${formulaSafeCsvText(text).replace(/"/g, '""')}"`;
}

export function csvDocument(rows: readonly (readonly unknown[])[]): string {
  return `\uFEFF${rows
    .map((row) => row.map(csvCell).join(","))
    .join("\r\n")}\r\n`;
}

export function safeFileSlug(value: string, fallback: string): string {
  const normalized = value
    .normalize("NFKC")
    .trim()
    .replace(/[<>:"/\\|?*\u0000-\u001F]/g, "-")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-")
    .replace(/[. ]+$/g, "")
    .slice(0, 64);
  const safe = normalized || fallback;
  return /^(con|prn|aux|nul|com[1-9]|lpt[1-9])$/i.test(safe)
    ? `project-${safe}`
    : safe;
}
