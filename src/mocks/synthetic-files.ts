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
      "\"Ultrasound clinical workflow evidence guide\",2026-05-08,Document,\"12,800\",486,412,31,22,7.4%,3.8%",
      "\"Patient monitoring outcomes briefing for ICU leaders\",2026-05-15,Video,\"11,200\",403,351,27,19,7.1%,3.6%",
      "\"Endoscopy KOL discussion on procedure standardization\",2026-05-22,Video,\"9,600\",298,276,18,14,6.3%,3.1%",
      "\"IVD analytical performance and FDA regulatory overview\",2026-05-29,Document,\"10,450\",345,302,24,17,6.6%,3.3%",
      "\"MRI clinical evidence review for radiology teams\",2026-06-05,Document,\"9,900\",307,281,21,15,6.3%,3.1%",
      "\"CT economic value framework for hospital procurement\",2026-06-12,Image,\"8,400\",218,184,12,9,5.0%,2.6%",
      "\"Digital health integration across the clinical workflow\",2026-06-19,Document,\"9,150\",284,243,20,13,6.1%,3.1%",
      "\"Surgical robotics CE pathway and patient outcomes briefing\",2026-06-26,Video,\"10,100\",343,316,25,18,6.8%,3.4%",
    ].join("\n"),
  },
};
