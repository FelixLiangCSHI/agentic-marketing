import {
  ControlApiShapeError,
  parseApprovalViews,
  type ApprovalView,
} from "@/server/control-api-views";
import styles from "./approvals.module.css";

export const dynamic = "force-dynamic";

interface InboxState {
  kind: "unconfigured" | "denied" | "error" | "ok";
  message?: string;
  approvals?: ApprovalView[];
}

/**
 * Server-side load of the approval inbox.
 *
 * The Control API enforces authentication and RBAC; this page never fakes
 * success. Until the portal session bridge lands (DEV SSO is BLOCKED), the
 * typed 401 from the API is surfaced as a "login required" state.
 */
async function loadInbox(): Promise<InboxState> {
  const base = process.env.DMT_API_BASE_URL;
  if (!base) {
    return { kind: "unconfigured" };
  }
  try {
    const response = await fetch(`${base}/api/v1/approvals`, {
      cache: "no-store",
    });
    if (response.status === 401 || response.status === 403) {
      return { kind: "denied" };
    }
    if (!response.ok) {
      return { kind: "error", message: `Control API 返回 ${response.status}` };
    }
    return { kind: "ok", approvals: parseApprovalViews(await response.json()) };
  } catch (error) {
    if (error instanceof ControlApiShapeError) {
      return { kind: "error", message: `Control API 响应格式无效：${error.message}` };
    }
    return { kind: "error", message: "无法连接 Control API" };
  }
}

export default async function ApprovalsPage() {
  const state = await loadInbox();
  return (
    <main className={styles.container}>
      <h1>审批收件箱</h1>
      <p className={styles.hint}>
        只读视图。审批决定必须通过带身份校验的 Control API 完成；发起人不能批准自己的请求。
      </p>
      {state.kind === "unconfigured" && (
        <p className={styles.notice}>未配置 DMT_API_BASE_URL，Approval API 不可用。</p>
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
              <th>Approval</th>
              <th>Run</th>
              <th>类型</th>
              <th>发起人</th>
              <th>状态</th>
              <th>过期时间</th>
            </tr>
          </thead>
          <tbody>
            {(state.approvals ?? []).map((approval) => (
              <tr key={approval.approval_id}>
                <td>{approval.approval_id}</td>
                <td>{approval.run_id}</td>
                <td>{approval.approval_type}</td>
                <td>{approval.requester_id}</td>
                <td>{approval.status}</td>
                <td>{approval.expires_at}</td>
              </tr>
            ))}
            {(state.approvals ?? []).length === 0 && (
              <tr>
                <td colSpan={6}>暂无审批请求。</td>
              </tr>
            )}
          </tbody>
        </table>
      )}
    </main>
  );
}
