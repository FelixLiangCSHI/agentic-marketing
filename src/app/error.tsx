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
      <h1>The workspace could not load</h1>
      <p>Uploaded content was not retained. Try again or check local service logs.</p>
      <button className="primary-button" type="button" onClick={unstable_retry}>
        <Icon name="refresh" size={16} />
        Reload
      </button>
    </main>
  );
}
