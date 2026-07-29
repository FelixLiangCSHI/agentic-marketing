import type { LinkedInModule } from "@/domain/linkedin";

export interface ModuleConfig {
  label: string;
  title: string;
  description: string;
  impact: string;
}

export const MODULE_CONFIG: Record<LinkedInModule, ModuleConfig> = {
  followers: {
    label: "Followers",
    title: "Follower analytics",
    description: "Follower growth and aggregate company size, industry, and seniority segments",
    impact: "Required for follower growth and audience segment analysis.",
  },
  visitors: {
    label: "Visitors",
    title: "Visitor analytics",
    description: "Page views, unique visitors, and aggregate anonymous visitor segments",
    impact: "Required to compare visitor trends and follower segments.",
  },
  content: {
    label: "Content",
    title: "Content analytics",
    description: "Post-level or daily impressions, clicks, engagement, and content formats",
    impact: "Required to evaluate content performance and publishing recommendations.",
  },
};
