export type PardotMode = "mock" | "api";

export type PardotEmailStatus =
  | "eligible"
  | "do_not_email"
  | "opted_out";

export interface PardotProspect {
  id: number;
  firstName: string | null;
  lastName: string | null;
  email: string;
  company: string | null;
  emailStatus: PardotEmailStatus;
}

export interface PardotProspectSearchResult {
  mode: PardotMode;
  prospects: readonly PardotProspect[];
  truncated: boolean;
}

export interface PardotCampaign {
  id: number;
  name: string;
}

export interface PardotCampaignQueryResult {
  mode: PardotMode;
  campaigns: readonly PardotCampaign[];
  nextAfterId: number | null;
}
