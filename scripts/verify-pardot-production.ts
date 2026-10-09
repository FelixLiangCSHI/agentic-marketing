import { appendFile } from "node:fs/promises";

import {
  PardotProductionVerificationError,
  verifyPardotProductionConnection,
} from "@/server/channels/pardot-production-verification";

async function main(): Promise<void> {
  try {
    const report = await verifyPardotProductionConnection();
    if (process.env.GITHUB_STEP_SUMMARY) {
      await appendFile(
        process.env.GITHUB_STEP_SUMMARY,
        [
          "## Pardot production read-only verification",
          "",
          "- Salesforce OAuth: HTTP 200",
          "- Production Campaign Query: HTTP 200",
          `- First-page campaign sample count: ${report.campaignSampleCount}`,
          "- External business writes: 0",
          "- Email send permissions were not tested.",
          `- Approved commit: ${report.commitSha}`,
          `- Workflow run: ${report.workflowRunId}`,
          "",
        ].join("\n"),
      );
    }
    console.info(JSON.stringify(report));
  } catch (error) {
    console.error(JSON.stringify(
      error instanceof PardotProductionVerificationError
        ? {
            success: false,
            code: error.code,
            stage: error.stage,
            reason: error.reason,
            httpStatus: error.httpStatus,
          }
        : { success: false, code: "VERIFICATION_FAILED", reason: "unexpected_verification_failure" },
    ));
    process.exitCode = 1;
  }
}

void main();
