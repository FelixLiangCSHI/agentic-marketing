import type {
  ContentField,
  FollowersField,
  LinkedInModule,
  StandardField,
  VisitorsField,
} from "@/domain/linkedin";

interface AliasEntry<TField extends StandardField> {
  field: TField;
  aliases: readonly string[];
  preferredAliases?: readonly string[];
}

export const FIELD_LABELS: Record<StandardField, string> = {
  date: "日期",
  totalFollowers: "关注者总数",
  newFollowers: "新增关注者",
  organicFollowers: "自然关注者",
  sponsoredFollowers: "付费关注者",
  demographicDimension: "画像维度",
  demographicValue: "画像值",
  demographicCount: "画像数量",
  demographicPercentage: "画像占比",
  pageViews: "页面浏览量",
  uniqueVisitors: "独立访客",
  customButtonClicks: "自定义按钮点击",
  contentId: "内容 ID",
  title: "内容标题",
  publishedAt: "发布时间",
  contentType: "内容类型",
  impressions: "展示次数",
  uniqueImpressions: "独立展示次数",
  clicks: "点击次数",
  reactions: "互动反应",
  comments: "评论数",
  reposts: "转发数",
  engagementRate: "互动率",
  clickThroughRate: "点击率",
};

const SHARED_DEMOGRAPHIC_VALUE_ALIASES = [
  "top demographics",
  "demographic value",
  "location",
  "country",
  "region",
  "job function",
  "seniority",
  "industry",
  "company size",
] as const;

const FOLLOWERS_ALIASES: readonly AliasEntry<FollowersField>[] = [
  { field: "date", aliases: ["date", "day", "日期"] },
  {
    field: "totalFollowers",
    aliases: ["total followers", "lifetime followers", "follower count"],
  },
  {
    field: "newFollowers",
    aliases: ["new followers", "followers gained", "follower gains"],
  },
  {
    field: "organicFollowers",
    aliases: ["organic followers", "organic follower count"],
  },
  {
    field: "sponsoredFollowers",
    aliases: [
      "sponsored followers",
      "paid followers",
      "sponsored follower count",
    ],
  },
  {
    field: "demographicDimension",
    aliases: ["demographic dimension", "dimension"],
  },
  {
    field: "demographicValue",
    aliases: SHARED_DEMOGRAPHIC_VALUE_ALIASES,
  },
  {
    field: "demographicCount",
    aliases: ["demographic count", "count", "total followers"],
  },
  {
    field: "demographicPercentage",
    aliases: [
      "demographic percentage",
      "percentage",
      "percent",
      "followers percentage",
      "% of followers",
    ],
  },
];

const VISITORS_ALIASES: readonly AliasEntry<VisitorsField>[] = [
  { field: "date", aliases: ["date", "day", "日期"] },
  {
    field: "pageViews",
    aliases: [
      "page views",
      "total page views",
      "total page views (total)",
      "overview page views (total)",
    ],
    preferredAliases: ["total page views (total)", "total page views"],
  },
  {
    field: "uniqueVisitors",
    aliases: [
      "unique visitors",
      "total unique visitors",
      "total unique visitors (total)",
      "overview unique visitors (total)",
    ],
    preferredAliases: [
      "total unique visitors (total)",
      "total unique visitors",
    ],
  },
  {
    field: "customButtonClicks",
    aliases: [
      "custom button clicks",
      "custom button click",
      "button clicks",
    ],
  },
  {
    field: "demographicDimension",
    aliases: ["demographic dimension", "dimension"],
  },
  {
    field: "demographicValue",
    aliases: SHARED_DEMOGRAPHIC_VALUE_ALIASES,
  },
  {
    field: "demographicCount",
    aliases: [
      "demographic count",
      "count",
      "total views",
      "total visitors",
    ],
  },
  {
    field: "demographicPercentage",
    aliases: [
      "demographic percentage",
      "percentage",
      "percent",
      "visitors percentage",
      "% of visitors",
    ],
  },
];

const CONTENT_ALIASES: readonly AliasEntry<ContentField>[] = [
  {
    field: "contentId",
    aliases: ["content id", "post id", "update id", "content urn", "urn"],
  },
  {
    field: "title",
    aliases: ["title", "post title", "content title", "update title"],
  },
  {
    field: "publishedAt",
    aliases: [
      "published at",
      "published date",
      "created date",
      "post date",
      "date",
    ],
  },
  {
    field: "contentType",
    aliases: ["content type", "post type", "media type"],
  },
  {
    field: "impressions",
    aliases: ["impressions", "impressions (total)", "total impressions"],
    preferredAliases: ["impressions (total)", "total impressions"],
  },
  {
    field: "uniqueImpressions",
    aliases: [
      "unique impressions",
      "unique impressions (total)",
      "unique impressions (organic)",
    ],
    preferredAliases: ["unique impressions (total)", "unique impressions"],
  },
  {
    field: "clicks",
    aliases: ["clicks", "clicks (total)", "total clicks", "link clicks"],
    preferredAliases: ["clicks (total)", "total clicks"],
  },
  {
    field: "reactions",
    aliases: [
      "reactions",
      "reactions (total)",
      "total reactions",
      "likes",
    ],
    preferredAliases: ["reactions (total)", "total reactions"],
  },
  {
    field: "comments",
    aliases: ["comments", "comments (total)", "total comments"],
    preferredAliases: ["comments (total)", "total comments"],
  },
  {
    field: "reposts",
    aliases: [
      "reposts",
      "reposts (total)",
      "total reposts",
      "shares",
    ],
    preferredAliases: ["reposts (total)", "total reposts"],
  },
  {
    field: "engagementRate",
    aliases: [
      "engagement rate",
      "engagement rate (total)",
      "total engagement rate",
    ],
    preferredAliases: [
      "engagement rate (total)",
      "total engagement rate",
    ],
  },
  {
    field: "clickThroughRate",
    aliases: [
      "click through rate",
      "click through rate (ctr)",
      "click-through rate",
      "ctr",
    ],
  },
];

export const MODULE_FIELDS: Record<
  LinkedInModule,
  readonly StandardField[]
> = {
  followers: FOLLOWERS_ALIASES.map(({ field }) => field),
  visitors: VISITORS_ALIASES.map(({ field }) => field),
  content: CONTENT_ALIASES.map(({ field }) => field),
};

export const MODULE_LABELS: Record<LinkedInModule, string> = {
  followers: "Followers",
  visitors: "Visitors",
  content: "Content",
};

const STANDARD_FIELD_NAMES = new Set<string>(
  Object.values(MODULE_FIELDS).flat(),
);

export function normalizeHeader(value: string): string {
  return value
    .replace(/^\uFEFF/, "")
    .trim()
    .toLocaleLowerCase("en-US")
    .replace(/[_/]+/g, " ")
    .replace(/\s+/g, " ");
}

export interface HeaderFieldCandidate {
  field: StandardField;
  priority: number;
}

function entriesForModule(
  module: LinkedInModule,
): readonly AliasEntry<StandardField>[] {
  if (module === "followers") {
    return FOLLOWERS_ALIASES;
  }

  if (module === "visitors") {
    return VISITORS_ALIASES;
  }

  return CONTENT_ALIASES;
}

export function getHeaderCandidates(
  module: LinkedInModule,
  rawHeader: string,
): HeaderFieldCandidate[] {
  const normalized = normalizeHeader(rawHeader);

  return entriesForModule(module).flatMap((entry) => {
    const aliases = entry.aliases.map(normalizeHeader);
    const aliasIndex = aliases.indexOf(normalized);

    if (aliasIndex === -1) {
      return [];
    }

    const preferred = entry.preferredAliases
      ?.map(normalizeHeader)
      .includes(normalized);

    return [
      {
        field: entry.field,
        priority: preferred ? 100 : 80 - aliasIndex,
      },
    ];
  });
}

export function isFieldForModule(
  module: LinkedInModule,
  field: StandardField,
): boolean {
  return MODULE_FIELDS[module].includes(field);
}

export function isStandardField(value: unknown): value is StandardField {
  return typeof value === "string" && STANDARD_FIELD_NAMES.has(value);
}

export function getDemographicDimension(sheetName: string): string | null {
  const normalized = normalizeHeader(sheetName);
  const dimensions = [
    ["location", "Location"],
    ["country", "Country"],
    ["region", "Region"],
    ["job function", "Job function"],
    ["seniority", "Seniority"],
    ["industry", "Industry"],
    ["company size", "Company size"],
  ] as const;

  return (
    dimensions.find(([keyword]) => normalized.includes(keyword))?.[1] ?? null
  );
}

export function getMappingOverrideKey(
  sheetName: string,
  columnIndex: number,
  rawHeader: string,
): string {
  return `${sheetName}::${columnIndex}::${normalizeHeader(rawHeader)}`;
}
