import { SYNTHETIC_FILES } from "@/mocks/synthetic-files";
import {
  LINKEDIN_MODULES,
  type FileParseResult,
  type LinkedInModule,
} from "@/domain/linkedin";
import { parseSpreadsheetBytes } from "@/server/parsing/spreadsheet-parser";

export function createSyntheticParseResults(): Record<
  LinkedInModule,
  FileParseResult
> {
  const encoder = new TextEncoder();
  const results = LINKEDIN_MODULES.map((module) => {
    const definition = SYNTHETIC_FILES[module];
    const bytes = encoder.encode(definition.content);
    const parsed = parseSpreadsheetBytes({
      bytes,
      fileName: definition.fileName,
      mimeType: definition.mimeType,
      format: "csv",
      expectedModule: module,
    });
    bytes.fill(0);

    return [
      module,
      {
        ...parsed,
        parserMode: "synthetic-mock" as const,
      },
    ] as const;
  });

  return Object.fromEntries(results) as Record<
    LinkedInModule,
    FileParseResult
  >;
}
