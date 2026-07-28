"use client";

import { Icon } from "@/components/ui/icon";

export default function Error({
  unstable_retry,
}: {
  error: Error & { digest?: string };
  unstable_retry: () => void;
}) {
  return (
    <main className="route-state" role="alert">
      <span className="route-state__icon route-state__icon--error">
        <Icon name="alert" size={28} />
      </span>
      <h1>工作区暂时无法加载</h1>
      <p>上传内容不会被保留。请重试；如仍失败，请检查本地服务日志。</p>
      <button className="primary-button" type="button" onClick={unstable_retry}>
        <Icon name="refresh" size={16} />
        重新加载
      </button>
    </main>
  );
}
