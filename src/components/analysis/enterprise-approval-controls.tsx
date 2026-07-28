"use client";

import { useState } from "react";

import { Icon } from "@/components/ui/icon";
import type { ApprovalStatus } from "@/domain/strategy";

const APPROVAL_LABELS: Record<ApprovalStatus, string> = {
  draft: "Pending approval",
  approved: "Approved",
  revision_requested: "Revision requested",
  rejected: "Rejected",
};

interface EnterpriseApprovalControlsProps {
  recommendation: string;
  status: ApprovalStatus;
  canApprove?: boolean;
  onDecision: (status: ApprovalStatus) => void;
}

export function EnterpriseApprovalControls({
  recommendation,
  status,
  canApprove = true,
  onDecision,
}: EnterpriseApprovalControlsProps) {
  const [reviewer, setReviewer] = useState("Marketing Operations Reviewer");
  const [comments, setComments] = useState("");

  return (
    <section className="enterprise-approval">
      <dl className="enterprise-approval__summary">
        <div>
          <dt>Marketing Recommendation</dt>
          <dd>{recommendation}</dd>
        </div>
        <div>
          <dt>Approval Status</dt>
          <dd>
            <span className={`approval-status approval-status--${status}`}>
              {APPROVAL_LABELS[status]}
            </span>
          </dd>
        </div>
      </dl>
      <div className="enterprise-approval__fields">
        <label>
          Reviewer
          <input
            value={reviewer}
            onChange={(event) => setReviewer(event.target.value)}
          />
        </label>
        <label>
          Comments
          <textarea
            value={comments}
            placeholder="Add review context or required changes"
            rows={3}
            onChange={(event) => setComments(event.target.value)}
          />
        </label>
      </div>
      <div className="approval-card__actions">
        <button
          className="secondary-button secondary-button--small"
          type="button"
          disabled={status === "rejected"}
          onClick={() => onDecision("rejected")}
        >
          Rejected
        </button>
        <button
          className="secondary-button secondary-button--small"
          type="button"
          disabled={status === "revision_requested"}
          onClick={() => onDecision("revision_requested")}
        >
          Request Revision
        </button>
        <button
          className="primary-button"
          type="button"
          disabled={!canApprove || !reviewer.trim() || status === "approved"}
          onClick={() => onDecision("approved")}
        >
          <Icon name="check" size={14} />
          Approve
        </button>
      </div>
    </section>
  );
}
