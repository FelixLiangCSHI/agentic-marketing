export type ConsultingConfidenceLevel = "High" | "Medium" | "Low";

export interface ConsultingReport {
  executiveSummary: string;
  keyFindings: string[];
  businessImplications: string[];
  recommendations: string[];
  confidenceLevel: ConsultingConfidenceLevel;
  evidence: string[];
  observedTrends: string[];
}
