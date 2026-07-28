import { metricCatalog } from "@/analysis/metric-catalog";
import type { ActionPlan } from "@/domain/action-plan";
import type { AnalysisSnapshot, Metric } from "@/domain/analysis";
import type {
  ChatAnswer,
  ChatEvidenceCitation,
  ChatMetricCitation,
} from "@/domain/chat";
import type {
  EvidenceInsight,
  StrategyRecommendation,
} from "@/domain/strategy";

export interface EvidenceChatContext {
  snapshot: AnalysisSnapshot;
  insights: EvidenceInsight[];
  strategies: StrategyRecommendation[];
  plan: ActionPlan | null;
}

const SECURITY_REQUEST =
  /(system\s*prompt|系统提示词|提示词全文|api\s*key|密钥|secret|内部配置|开发者指令|忽略.{0,8}(之前|以上|规则)|reveal.{0,12}(prompt|config|secret))/i;
const IDENTITY_REQUEST =
  /(识别|告诉我|列出|找到).{0,12}(匿名访客|具体访客|具体关注者|个人身份|购买意向)/i;
const OUT_OF_SCOPE =
  /(销售额|收入|营收|订单|成交|pipeline|crm|网站转化|广告花费|预算回报|roi)/i;

function answerId(now: Date): string {
  return `answer-${now.toISOString().replace(/\D/g, "")}`;
}

function metricCitation(metric: Metric): ChatMetricCitation {
  return {
    metricId: metric.metricId,
    label: metric.label,
    formattedValue: metric.formattedValue,
    period: metric.period,
    sourceModules: metric.sourceModules,
    sourceReferences: metric.sourceReferences,
  };
}

function citation(metric: Metric): ChatEvidenceCitation {
  return {
    citationId: `metric-${metric.metricId}`,
    kind: "metric",
    label: `${metric.label} · ${metric.metricId}`,
    metric: metricCitation(metric),
  };
}

function baseAnswer(
  now: Date,
  input: Omit<ChatAnswer, "answerId" | "promptVersion" | "report"> & {
    dataStatement: string;
    possibleMeaning: string | null;
    suggestedValidation: string | null;
  },
): ChatAnswer {
  const {
    dataStatement,
    possibleMeaning,
    suggestedValidation,
    citations,
    ...answer
  } = input;
  return {
    answerId: answerId(now),
    promptVersion: "evidence-chat-v1.0",
    ...answer,
    citations,
    report: {
      executiveSummary: dataStatement,
      keyFindings: [dataStatement],
      businessImplications: possibleMeaning ? [possibleMeaning] : [],
      recommendations: suggestedValidation ? [suggestedValidation] : [],
      confidenceLevel: input.status === "answered" ? "Medium" : "Low",
      evidence: citations.map((item) => item.label),
      observedTrends:
        input.intent === "trend_explanation" && possibleMeaning
          ? [possibleMeaning]
          : [
              "No confirmed time-series trend is available beyond the cited analysis period.",
            ],
    },
  };
}

function unavailable(
  now: Date,
  statement: string,
  validation: string,
): ChatAnswer {
  return baseAnswer(now, {
    intent: "unavailable",
    status: "unavailable",
    dataStatement: statement,
    possibleMeaning: null,
    suggestedValidation: validation,
    citations: [],
    suggestedPlanChange: null,
  });
}

function metricAnswer(
  metric: Metric | undefined,
  now: Date,
  possibleMeaning: string,
  suggestedValidation: string,
): ChatAnswer {
  if (!metric || metric.reliability === "unavailable" || metric.value === null) {
    return unavailable(
      now,
      "The current snapshot does not support this metric.",
      "Provide the missing fields or import data with a comparable analysis period.",
    );
  }
  const period = metric.period
    ? `${metric.period.start} to ${metric.period.end}`
    : "current aggregate range";
  return baseAnswer(now, {
    intent: "metric_query",
    status: "answered",
    dataStatement: `${metric.label} is ${metric.formattedValue} (metricId: ${metric.metricId}; period: ${period}; source modules: ${metric.sourceModules.join(
      ", ",
    )}).`,
    possibleMeaning,
    suggestedValidation,
    citations: [citation(metric)],
    suggestedPlanChange: null,
  });
}

function referencedMetrics(
  context: EvidenceChatContext,
  metricIds: readonly string[],
): Metric[] {
  const catalog = metricCatalog(context.snapshot);
  return metricIds.flatMap((metricId) => {
    const metric = catalog.get(metricId);
    return metric ? [metric] : [];
  });
}

export function answerProjectQuestion(
  context: EvidenceChatContext,
  question: string,
  now: Date = new Date(),
): ChatAnswer {
  const normalized = question.trim();
  if (!normalized) {
    return unavailable(now, "No question was provided.", "Submit a question related to the current project.");
  }

  if (SECURITY_REQUEST.test(normalized)) {
    return baseAnswer(now, {
      intent: "security_refusal",
      status: "refused",
      dataStatement:
        "The request concerns restricted credentials, system instructions, or internal configuration and cannot be fulfilled.",
      possibleMeaning: null,
      suggestedValidation:
        "Limit requests to business information in the current snapshot, approved findings, or action plan.",
      citations: [],
      suggestedPlanChange: null,
    });
  }

  if (IDENTITY_REQUEST.test(normalized)) {
    return unavailable(
      now,
      "The LinkedIn export contains aggregate data and cannot identify anonymous visitors, individual followers, or purchase intent.",
      "Individual-level analysis requires an authorized and applicable data source; this capability is outside the current scope.",
    );
  }

  if (OUT_OF_SCOPE.test(normalized)) {
    return unavailable(
      now,
      "The project contains aggregate LinkedIn data and does not support conclusions about revenue, orders, CRM leads, or website conversions.",
      "Add CRM, web analytics, advertising cost, or sales outcome data with aligned reporting periods.",
    );
  }

  const postsMatch = normalized.match(/每周\s*(?:发布|发)?\s*(\d)\s*(?:篇|条|次)/);
  if (postsMatch) {
    const postsPerWeek = Number(postsMatch[1]);
    if (!context.plan) {
      return unavailable(
        now,
        "A publishing-frequency change cannot be applied because no action plan exists.",
        "Approve the findings and strategy, then generate an action plan.",
      );
    }
    if (!Number.isInteger(postsPerWeek) || postsPerWeek < 1 || postsPerWeek > 7) {
      return unavailable(
        now,
        "Weekly publishing volume must be between one and seven items.",
        "Set an operationally achievable weekly content volume.",
      );
    }
    return baseAnswer(now, {
      intent: "plan_modification",
      status: "answered",
      dataStatement: `The plan change sets weekly publishing volume to ${postsPerWeek} items and reschedules the four-week calendar and KPI reviews without recalculating the snapshot or findings.`,
      possibleMeaning: "Publishing capacity affects calendar density and task dates.",
      suggestedValidation: "Confirm resource capacity, dates, and experiment reviews after applying the change.",
      citations: [
        {
          citationId: context.plan.planId,
          kind: "plan",
          label: `Current plan ${context.plan.planId}`,
          metric: null,
        },
      ],
      suggestedPlanChange: { type: "posts_per_week", postsPerWeek },
    });
  }

  const audienceMatch = normalized.match(
    /(?:重点受众|目标受众)\s*(?:改为|设为|调整为|是)?\s*[:：]?\s*(.{2,80})$/i,
  );
  if (audienceMatch && context.plan) {
    const focusAudience = audienceMatch[1].trim();
    return baseAnswer(now, {
      intent: "plan_modification",
      status: "answered",
      dataStatement: `The plan change sets the priority audience to “${focusAudience}” and updates the audience field and affected calendar entries.`,
      possibleMeaning: "Content topics and CTAs require alignment with the revised audience.",
      suggestedValidation: "Review each content topic after applying the change and do not interpret aggregate profiles as individual identities.",
      citations: [
        {
          citationId: context.plan.planId,
          kind: "plan",
          label: `Current plan ${context.plan.planId}`,
          metric: null,
        },
      ],
      suggestedPlanChange: { type: "focus_audience", focusAudience },
    });
  }

  const catalog = metricCatalog(context.snapshot);
  if (/(proxy|代理比率|转化率|访客.*关注者|visitor.*follower)/i.test(normalized)) {
    const metric = catalog.get("cross.visitorToFollowerProxy");
    const answer = metricAnswer(
      metric,
      now,
      "The metric is an aggregate proxy for a shared period and does not demonstrate that an individual visitor became a follower.",
      "Validate with subsequent like-for-like imports and independently authorized user-level data; classify the metric separately from a verified conversion rate.",
    );
    return { ...answer, intent: "trend_explanation" };
  }
  if (/(ctr|点击率|click.?through)/i.test(normalized)) {
    return metricAnswer(
      catalog.get("content.ctr"),
      now,
      "The metric indicates the relative ability of content and CTAs to attract clicks; it does not establish a business outcome.",
      "Run single-variable tests by content format and topic, then review the next comparable import.",
    );
  }
  if (/(互动率|engagement)/i.test(normalized)) {
    return metricAnswer(
      catalog.get("content.engagementRate"),
      now,
      "The metric quantifies aggregate interaction with content; historical performance does not guarantee future results.",
      "Review median engagement and post-level rankings alongside the average.",
    );
  }
  if (
    /(关注者|followers?).*(增长|变化|趋势|growth|change|trend)|增长.*关注者/i.test(
      normalized,
    )
  ) {
    const answer = metricAnswer(
      catalog.get("followers.netGrowth"),
      now,
      "The metric identifies the direction of follower change during the period without identifying individual followers.",
      "Confirm the direction in the next like-for-like import and avoid attribution to a single content item.",
    );
    return { ...answer, intent: "trend_explanation" };
  }
  if (/(访客|visitors?|page\s*views?|浏览量)/i.test(normalized)) {
    const answer = metricAnswer(
      catalog.get("visitors.pageViewsTotal"),
      now,
      "The metric quantifies aggregate page traffic without identifying anonymous visitors or intent.",
      "Track Unique Visitors and CTA Clicks using the same time granularity.",
    );
    return {
      ...answer,
      intent: /(趋势|变化|怎么样)/.test(normalized)
        ? "trend_explanation"
        : "metric_query",
    };
  }
  if (/(发布|内容数量|发了多少)/i.test(normalized) && !/(建议|应该|计划)/i.test(normalized)) {
    return metricAnswer(
      catalog.get("content.publishedCount"),
      now,
      "The metric is a historical publishing baseline, not a recommended frequency.",
      "Set future volume against the team's weekly publishing capacity.",
    );
  }

  if (
    /(数据质量|质量问题|为什么.*不可用|可靠性|data quality|quality issue|reliability)/i.test(
      normalized,
    )
  ) {
    const blocking = context.snapshot.quality.issues.find(
      (issue) => issue.blocksAnalysis,
    );
    const issue = blocking ?? context.snapshot.quality.issues[0];
    if (!issue) {
      return baseAnswer(now, {
        intent: "quality_explanation",
        status: "answered",
        dataStatement: "The current snapshot contains no recorded data-quality issues.",
        possibleMeaning: "The absence of recorded issues does not establish coverage of every business question.",
        suggestedValidation: "Maintain consistent fields, reporting periods, and granularity in the next import.",
        citations: [],
        suggestedPlanChange: null,
      });
    }
    return baseAnswer(now, {
      intent: "quality_explanation",
      status: "answered",
      dataStatement: `Data-quality rule ${issue.code} reports: ${issue.message}`,
      possibleMeaning: issue.blocksAnalysis
        ? "The issue blocks downstream findings and planning."
        : "The issue does not block analysis but limits decision precision.",
      suggestedValidation: issue.suggestedAction,
      citations: [
        {
          citationId: `quality-${issue.code}`,
          kind: "quality",
          label: `${issue.code} · ${issue.module}`,
          metric: null,
        },
      ],
      suggestedPlanChange: null,
    });
  }

  if (/(洞察.*证据|为什么.*洞察|证据是什么)/i.test(normalized)) {
    const insight =
      context.insights.find((item) => item.approvalStatus === "approved") ??
      context.insights[0];
    if (!insight) {
      return unavailable(
        now,
        "The project contains no reportable findings.",
        "Generate findings with valid metric references.",
      );
    }
    const metrics = referencedMetrics(
      context,
      insight.evidence.map((item) => item.metricId),
    );
    return baseAnswer(now, {
      intent: "insight_evidence",
      status: "answered",
      dataStatement: `${insight.title}: ${insight.statement}`,
      possibleMeaning: insight.possibleMeaning,
      suggestedValidation: insight.suggestedValidation,
      citations: [
        {
          citationId: insight.insightId,
          kind: "insight",
          label: insight.title,
          metric: null,
        },
        ...metrics.map(citation),
      ],
      suggestedPlanChange: null,
    });
  }

  if (
    /(建议|应该发布什么|内容方向|下个月.*发布|what.*publish|next month)/i.test(
      normalized,
    )
  ) {
    const strategy = context.strategies.find(
      (item) => item.approvalStatus === "approved",
    );
    if (!strategy) {
      return unavailable(
        now,
        "No approved strategy is available; draft recommendations are not classified as approved actions.",
        "Review the evidence and approve at least one strategy.",
      );
    }
    const metrics = referencedMetrics(context, strategy.metricIds);
    const planItems =
      context.plan?.contentCalendar
        .filter((item) => item.status !== "rejected")
        .slice(0, 2)
        .map((item) => `${item.date}：${item.topic}`) ?? [];
    return baseAnswer(now, {
      intent: "content_recommendation",
      status: "answered",
      dataStatement:
        planItems.length > 0
          ? `已批准策略“${strategy.title}”对应的近期安排包括：${planItems.join(
              "；",
            )}。`
          : `Approved strategy — ${strategy.title}: ${strategy.objective}`,
      possibleMeaning: strategy.rationale,
      suggestedValidation:
        "Classify the content as an experiment and review the cited KPIs on the scheduled review date.",
      citations: [
        {
          citationId: strategy.strategyId,
          kind: "strategy",
          label: strategy.title,
          metric: null,
        },
        ...metrics.map(citation),
      ],
      suggestedPlanChange: null,
    });
  }

  return unavailable(
    now,
    "The current snapshot, findings, and plan do not support the requested conclusion.",
    "Add the relevant data source, reporting period, or measurable metric.",
  );
}
