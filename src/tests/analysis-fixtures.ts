import type { AnalysisInput } from "@/domain/analysis";
import type {
  ContentRecord,
  FollowersRecord,
  LinkedInModule,
  RawCellValue,
  SourceProvenance,
  VisitorsRecord,
} from "@/domain/linkedin";

function source(
  module: LinkedInModule,
  rowNumber: number,
): SourceProvenance {
  return {
    module,
    fileName: `synthetic_${module}.csv`,
    sheetName: "Synthetic",
    rowNumber,
  };
}

export function followerRecord(
  rowNumber: number,
  values: Partial<FollowersRecord> = {},
): FollowersRecord {
  return {
    module: "followers",
    source: source("followers", rowNumber),
    rawValues: {} as Partial<Record<keyof FollowersRecord, RawCellValue>>,
    isDuplicate: false,
    issueReferences: [],
    date: null,
    totalFollowers: null,
    newFollowers: null,
    organicFollowers: null,
    sponsoredFollowers: null,
    demographicDimension: null,
    demographicValue: null,
    demographicCount: null,
    demographicPercentage: null,
    ...values,
  };
}

export function visitorRecord(
  rowNumber: number,
  values: Partial<VisitorsRecord> = {},
): VisitorsRecord {
  return {
    module: "visitors",
    source: source("visitors", rowNumber),
    rawValues: {} as Partial<Record<keyof VisitorsRecord, RawCellValue>>,
    isDuplicate: false,
    issueReferences: [],
    date: null,
    pageViews: null,
    uniqueVisitors: null,
    customButtonClicks: null,
    demographicDimension: null,
    demographicValue: null,
    demographicCount: null,
    demographicPercentage: null,
    ...values,
  };
}

export function contentRecord(
  rowNumber: number,
  values: Partial<ContentRecord> = {},
): ContentRecord {
  return {
    module: "content",
    source: source("content", rowNumber),
    rawValues: {} as Partial<Record<keyof ContentRecord, RawCellValue>>,
    isDuplicate: false,
    issueReferences: [],
    contentId: null,
    title: null,
    publishedAt: null,
    contentType: null,
    impressions: null,
    uniqueImpressions: null,
    clicks: null,
    reactions: null,
    comments: null,
    reposts: null,
    engagementRate: null,
    clickThroughRate: null,
    ...values,
  };
}

export function handVerifiedInput(): AnalysisInput {
  return {
    inputMode: "mock",
    records: {
      followers: [
        followerRecord(2, {
          date: "2026-01-01",
          totalFollowers: 100,
          newFollowers: 10,
          organicFollowers: 8,
          sponsoredFollowers: 2,
        }),
        followerRecord(3, {
          date: "2026-01-02",
          totalFollowers: 110,
          newFollowers: 10,
          organicFollowers: 6,
          sponsoredFollowers: 4,
        }),
        followerRecord(4, {
          date: "2026-01-03",
          totalFollowers: 125,
          newFollowers: 15,
          organicFollowers: 12,
          sponsoredFollowers: 3,
        }),
      ],
      visitors: [
        visitorRecord(2, {
          date: "2026-01-01",
          pageViews: 200,
          uniqueVisitors: 100,
          customButtonClicks: 5,
        }),
        visitorRecord(3, {
          date: "2026-01-02",
          pageViews: 240,
          uniqueVisitors: 120,
          customButtonClicks: 6,
        }),
        visitorRecord(4, {
          date: "2026-01-03",
          pageViews: 300,
          uniqueVisitors: 150,
          customButtonClicks: 9,
        }),
      ],
      content: [
        contentRecord(2, {
          contentId: "synthetic-1",
          title: "Synthetic A",
          publishedAt: "2026-01-01T08:00:00.000Z",
          contentType: "Document",
          impressions: 100,
          clicks: 5,
          reactions: 3,
          comments: 1,
          reposts: 1,
        }),
        contentRecord(3, {
          contentId: "synthetic-2",
          title: "Synthetic B",
          publishedAt: "2026-01-02T08:00:00.000Z",
          contentType: "Document",
          impressions: 100,
          clicks: 10,
          reactions: 5,
          comments: 3,
          reposts: 2,
        }),
        contentRecord(4, {
          contentId: "synthetic-3",
          title: "Synthetic C",
          publishedAt: "2026-01-03T08:00:00.000Z",
          contentType: "Video",
          impressions: 100,
          clicks: 50,
          reactions: 20,
          comments: 10,
          reposts: 10,
        }),
      ],
    },
  };
}
