import { Icon } from "@/components/ui/icon";

export default function Loading() {
  return (
    <main className="route-state">
      <span className="route-state__icon">
        <Icon name="spinner" size={28} className="spin" />
      </span>
      <h1>Preparing the secure analysis workspace</h1>
      <p>Loading demo data and field definitions...</p>
    </main>
  );
}
