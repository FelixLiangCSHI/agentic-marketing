import type { LinkedInModule } from "@/domain/linkedin";

export interface SyntheticFileDefinition {
  module: LinkedInModule;
  fileName: string;
  mimeType: "text/csv";
  content: string;
}

export const SYNTHETIC_FILES: Record<
  LinkedInModule,
  SyntheticFileDefinition
> = {
  followers: {
    module: "followers",
    fileName: "synthetic_followers.csv",
    mimeType: "text/csv",
    content: [
      "Synthetic demo data - not a real LinkedIn export",
      "Date,Total followers,New followers,Organic followers,Sponsored followers",
      "2026-04-01,\"4,820\",128,112,16",
      "2026-05-01,\"4,966\",146,126,20",
      "2026-06-01,\"5,137\",171,149,22",
    ].join("\n"),
  },
  visitors: {
    module: "visitors",
    fileName: "synthetic_visitors.csv",
    mimeType: "text/csv",
    content: [
      "Synthetic demo data - not a real LinkedIn export",
      "Date,Total page views,Total unique visitors,Custom button clicks",
      "2026-04-01,\"3,420\",\"2,180\",64",
      "2026-05-01,\"3,860\",\"2,410\",79",
      "2026-06-01,\"4,248\",\"2,690\",91",
    ].join("\n"),
  },
  content: {
    module: "content",
    fileName: "synthetic_content.csv",
    mimeType: "text/csv",
    content: [
      "Synthetic demo data - not a real LinkedIn export",
      "Post title,Created date,Content Type,Impressions,Clicks,Likes,Comments,Reposts,Engagement rate,Click through rate (CTR)",
      "\"Ultrasound and MRI clinical evidence for imaging workflows\",2026-05-08,Document,\"12,800\",486,412,31,22,7.4%,3.8%",
      "\"Patient monitoring and digital health outcomes for care teams\",2026-05-22,Video,\"9,600\",298,276,18,14,6.3%,3.1%",
      "\"Endoscopy IVD CT and surgical robotics regulatory briefing\",2026-06-12,Image,\"8,400\",218,184,12,9,5.0%,2.6%",
    ].join("\n"),
  },
};
