import * as XLSX from "@e965/xlsx";

export interface SheetFixture {
  name: string;
  rows: unknown[][];
  mutate?: (sheet: XLSX.WorkSheet) => void;
}

export function csvBytes(content: string): Uint8Array {
  return new TextEncoder().encode(content);
}

function toBytes(value: unknown): Uint8Array {
  if (value instanceof Uint8Array) {
    return value.slice();
  }

  if (value instanceof ArrayBuffer) {
    return new Uint8Array(value);
  }

  if (ArrayBuffer.isView(value)) {
    return new Uint8Array(
      value.buffer,
      value.byteOffset,
      value.byteLength,
    ).slice();
  }

  throw new Error("Synthetic workbook writer returned an unknown type.");
}

export function workbookBytes(
  sheets: readonly SheetFixture[],
  bookType: "xlsx" | "biff8" = "xlsx",
): Uint8Array {
  const workbook = XLSX.utils.book_new();

  for (const fixture of sheets) {
    const sheet = XLSX.utils.aoa_to_sheet(fixture.rows);
    fixture.mutate?.(sheet);
    XLSX.utils.book_append_sheet(workbook, sheet, fixture.name);
  }

  const output: unknown = XLSX.write(workbook, {
    type: "array",
    bookType,
    compression: true,
  });

  return toBytes(output);
}
