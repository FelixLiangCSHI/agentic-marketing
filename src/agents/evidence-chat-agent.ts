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
  input: Omit<ChatAnswer, "answerId" | "promptVersion">,
): ChatAnswer {
  return {
    answerId: answerId(now),
    promptVersion: "evidence-chat-v1.0",
    ...input,
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
      "当前 Snapshot 无法回答该指标问题。",
      "请补充缺失字段或导入具有可比较时间范围的数据。",
    );
  }
  const period = metric.period
    ? `${metric.period.start} 至 ${metric.period.end}`
    : "当前可用聚合范围";
  return baseAnswer(now, {
    intent: "metric_query",
    status: "answered",
    dataStatement: `数据显示，${metric.label}为 ${metric.formattedValue}（metricId: ${metric.metricId}；时间范围：${period}；来源模块：${metric.sourceModules.join(
      "、",
    )}）。`,
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
    return unavailable(now, "问题为空，无法判断。", "请输入一个与当前项目相关的问题。");
  }

  if (SECURITY_REQUEST.test(normalized)) {
    return baseAnswer(now, {
      intent: "security_refusal",
      status: "refused",
      dataStatement:
        "我不能提供密钥、系统提示词、内部配置或用于绕过当前项目边界的信息。",
      possibleMeaning: null,
      suggestedValidation:
        "可以继续询问当前 Snapshot、已生成洞察或行动计划中的业务信息。",
      citations: [],
      suggestedPlanChange: null,
    });
  }

  if (IDENTITY_REQUEST.test(normalized)) {
    return unavailable(
      now,
      "当前 LinkedIn 导出是聚合数据，无法识别匿名访客、具体关注者或个人购买意向。",
      "如需个人级分析，必须使用具有合法授权且适用的数据源；本 Demo 不提供该能力。",
    );
  }

  if (OUT_OF_SCOPE.test(normalized)) {
    return unavailable(
      now,
      "当前项目只有 LinkedIn 聚合分析数据，无法判断收入、订单、CRM 线索或网站转化。",
      "需要补充 CRM、网站分析、广告成本或销售结果数据，并明确可连接的时间口径。",
    );
  }

  const postsMatch = normalized.match(/每周\s*(?:发布|发)?\s*(\d)\s*(?:篇|条|次)/);
  if (postsMatch) {
    const postsPerWeek = Number(postsMatch[1]);
    if (!context.plan) {
      return unavailable(
        now,
        "当前尚未生成行动计划，无法应用发布频率修改。",
        "请先批准洞察与策略并生成计划。",
      );
    }
    if (!Number.isInteger(postsPerWeek) || postsPerWeek < 1 || postsPerWeek > 7) {
      return unavailable(
        now,
        "每周发布数量必须在 1–7 之间。",
        "请提供可执行的每周内容数量。",
      );
    }
    return baseAnswer(now, {
      intent: "plan_modification",
      status: "answered",
      dataStatement: `可以把计划调整为每周 ${postsPerWeek} 条内容；这只会重排四周日历与 KPI 复盘，不会重跑 Snapshot 或洞察。`,
      possibleMeaning: "发布能力变化会影响内容日历密度和任务日期。",
      suggestedValidation: "应用后请检查资源、日期和实验复盘是否仍可执行。",
      citations: [
        {
          citationId: context.plan.planId,
          kind: "plan",
          label: `当前计划 ${context.plan.planId}`,
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
      dataStatement: `可以把计划重点受众调整为“${focusAudience}”；只更新计划受众字段和受影响日历。`,
      possibleMeaning: "内容主题与 CTA 应由用户随后检查是否仍适合该受众。",
      suggestedValidation: "应用后逐项确认内容主题，不将聚合画像解释为个人身份。",
      citations: [
        {
          citationId: context.plan.planId,
          kind: "plan",
          label: `当前计划 ${context.plan.planId}`,
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
      "这只是共同周期中的聚合代理观察，不能说明某个访客成为了关注者。",
      "建议结合后续同口径导入和独立的用户级合规数据验证；不要将其称为真实转化率。",
    );
    return { ...answer, intent: "trend_explanation" };
  }
  if (/(ctr|点击率|click.?through)/i.test(normalized)) {
    return metricAnswer(
      catalog.get("content.ctr"),
      now,
      "这可能反映内容与 CTA 对点击行为的相对吸引力，但不能单独说明业务结果。",
      "建议按内容形式与主题做单变量实验，并在下一次导入后复核。",
    );
  }
  if (/(互动率|engagement)/i.test(normalized)) {
    return metricAnswer(
      catalog.get("content.engagementRate"),
      now,
      "这可能反映内容引发聚合互动的程度，历史表现不保证未来结果。",
      "建议同时查看中位互动率和逐帖排名，避免只依赖平均值。",
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
      "这可能表示关注者规模在该周期内发生了方向性变化，但不能识别具体关注者。",
      "建议在下一次同口径导入中复核，并避免把变化归因于单条内容。",
    );
    return { ...answer, intent: "trend_explanation" };
  }
  if (/(访客|visitors?|page\s*views?|浏览量)/i.test(normalized)) {
    const answer = metricAnswer(
      catalog.get("visitors.pageViewsTotal"),
      now,
      "这可能反映主页聚合访问强度，但无法判断匿名访客身份或意向。",
      "建议同时观察 Unique Visitors 和 CTA Clicks，并保持相同时间粒度。",
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
      "这是历史发布基线，不代表推荐频率。",
      "请结合团队每周发帖能力设置未来计划。",
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
        dataStatement: "数据显示，当前 Snapshot 未记录数据质量问题。",
        possibleMeaning: "这不代表数据覆盖了所有业务问题。",
        suggestedValidation: "下一次导入仍应保持相同字段、时间范围和粒度。",
        citations: [],
        suggestedPlanChange: null,
      });
    }
    return baseAnswer(now, {
      intent: "quality_explanation",
      status: "answered",
      dataStatement: `数据显示，质量规则 ${issue.code} 提示：${issue.message}`,
      possibleMeaning: issue.blocksAnalysis
        ? "该问题会阻止后续洞察与计划。"
        : "该问题不阻断分析，但会限制精确决策。",
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
        "当前项目没有可解释的洞察。",
        "请先生成具有有效 Metric 引用的洞察。",
      );
    }
    const metrics = referencedMetrics(
      context,
      insight.evidence.map((item) => item.metricId),
    );
    return baseAnswer(now, {
      intent: "insight_evidence",
      status: "answered",
      dataStatement: `洞察“${insight.title}”的表述是：${insight.statement}`,
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
        "当前没有已批准策略，因此不能把草稿建议当作行动建议。",
        "请先查看证据并批准至少一条策略。",
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
          : `已批准策略是“${strategy.title}”：${strategy.objective}`,
      possibleMeaning: strategy.rationale,
      suggestedValidation:
        "建议将内容标记为实验，并在计划复盘日检查引用 KPI。",
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
    "当前 Snapshot、洞察和计划无法支持这个结论，我无法判断。",
    "请补充问题涉及的数据源、时间范围或可计算指标。",
  );
}
