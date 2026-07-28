import { IngestionDemo } from "@/components/ingestion-demo";
import { createSyntheticParseResults } from "@/server/parsing/synthetic-results";

export default function Home() {
  const mockResults = createSyntheticParseResults();
  return <IngestionDemo mockResults={mockResults} />;
}
