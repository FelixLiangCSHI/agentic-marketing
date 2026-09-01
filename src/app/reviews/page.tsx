import {
  ControlApiShapeError,
  parseReviewViews,
  type ReviewView,
  type TrackView,
} from "@/server/control-api-views";
import styles from "./reviews.module.css";

export const dynamic = "force-dynamic";

interface InboxState {
  kind: "unconfigured" | "denied" | "error" | "ok";
  message?: string;
  reviews?: ReviewView[];
}

/**
 * Server-side load of the Medical/Marketing review inbox.
 *
 * 决策（批准/驳回）必须通过带身份校验的 Control API 完成：轨道由服务端
 * 角色决定，前端不可伪造；BLOCKED（规则失败）无法被任何人批准。
 * Portal 会话桥接依赖企业 DEV SSO App（当前 BLOCKED），因此本页为只读。
 */
async function loadInbox(): Promise<InboxState> {
  const base = process.env.DMT_API_BASE_URL;
  if (!base) {
    return { kind: "unconfigured" };
  }
  try {
    const response = await fetch(`${base}/api/v1/reviews`, {
      cache: "no-store",
    });
    if (response.status === 401 || response.status === 403) {
      return { kind: "denied" };
    }
    if (!response.ok) {
      return { kind: "error", message: `Control API 返回 ${response.status}` };
    }
    return { kind: "ok", reviews: parseReviewViews(await response.json()) };
  } catch (error) {
    if (error instanceof ControlApiShapeError) {
      return { kind: "error", message: `Control API 响应格式无效：${error.message}` };
    }
    return { kind: "error", message: "无法连接 Control API" };
  }
}

function trackLabel(track: TrackView): string {
  return track.decided_by
    ? `${track.status} (${track.decided_by})`
    : track.status;
}

export default async function ReviewsPage() {
  const state = await loadInbox();
  return (
    <main className={styles.container}>
      <h1>医学 / 市场审核</h1>
      <p className={styles.hint}>
        只读视图，内容 / Claim / 来源 / 政策版本并排展示在详情接口中。
        双轨（医学 + 市场）都批准才算通过；规则失败（BLOCKED）不能被人工批准，
        只能驳回并指定返工节点；内容变更会使旧批准全部失效。
      </p>
      {state.kind === "unconfigured" && (
        <p className={styles.notice}>未配置 DMT_API_BASE_URL，Review API 不可用。</p>
      )}
      {state.kind === "denied" && (
        <p className={styles.notice}>
          需要登录。Portal 会话桥接依赖企业 DEV SSO App（当前 BLOCKED）。
        </p>
      )}
      {state.kind === "error" && <p className={styles.notice}>{state.message}</p>}
      {state.kind === "ok" && (
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Review</th>
              <th>Run</th>
              <th>合规门</th>
              <th>医学轨</th>
              <th>市场轨</th>
              <th>状态</th>
              <th>政策版本</th>
              <th>修订</th>
            </tr>
          </thead>
          <tbody>
            {(state.reviews ?? []).map((review) => (
              <tr key={review.review_id}>
                <td>{review.review_id}</td>
                <td>{review.run_id}</td>
                <td
                  className={
                    review.automated_status === "BLOCKED"
                      ? styles.blocked
                      : styles.pass
                  }
                >
                  {review.automated_status}
                </td>
                <td>{trackLabel(review.medical)}</td>
                <td>{trackLabel(review.marketing)}</td>
                <td>{review.status}</td>
                <td>{review.policy_version}</td>
                <td>{review.revision}</td>
              </tr>
            ))}
            {(state.reviews ?? []).length === 0 && (
              <tr>
                <td colSpan={8}>暂无待审核内容。</td>
              </tr>
            )}
          </tbody>
        </table>
      )}
    </main>
  );
}
