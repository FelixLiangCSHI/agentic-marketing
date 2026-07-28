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
    title: "关注者分析",
    description: "关注者增长趋势与公司规模、行业、职级等聚合画像",
    impact: "缺少后将无法分析关注者增长和受众画像。",
  },
  visitors: {
    label: "Visitors",
    title: "访客分析",
    description: "页面浏览、独立访客与匿名聚合访客画像",
    impact: "缺少后将无法比较访客趋势与关注者画像。",
  },
  content: {
    label: "Content",
    title: "内容分析",
    description: "逐帖或日级展示、点击、互动与内容类型指标",
    impact: "缺少后将无法判断内容表现或形成发布建议。",
  },
};
