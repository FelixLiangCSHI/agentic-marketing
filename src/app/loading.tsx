import { Icon } from "@/components/ui/icon";

export default function Loading() {
  return (
    <main className="route-state">
      <span className="route-state__icon">
        <Icon name="spinner" size={28} className="spin" />
      </span>
      <h1>正在准备安全解析工作区</h1>
      <p>正在载入合成示例接口与字段字典…</p>
    </main>
  );
}
