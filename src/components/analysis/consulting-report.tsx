import type { ConsultingReport as ConsultingReportData } from "@/domain/consulting-report";

interface ConsultingReportProps {
  report: ConsultingReportData;
}

function ReportList({ items }: { items: string[] }) {
  return items.length > 0 ? (
    <ul>
      {items.map((item, index) => (
        <li key={`${index}-${item}`}>{item}</li>
      ))}
    </ul>
  ) : (
    <p>No material finding is available for this section.</p>
  );
}

export function ConsultingReport({ report }: ConsultingReportProps) {
  return (
    <div className="consulting-report">
      <section>
        <h4>Executive Summary</h4>
        <p>{report.executiveSummary}</p>
      </section>
      <section>
        <h4>Key Findings</h4>
        <ReportList items={report.keyFindings} />
      </section>
      <section>
        <h4>Business Implications</h4>
        <ReportList items={report.businessImplications} />
      </section>
      <section>
        <h4>Recommendations</h4>
        <ReportList items={report.recommendations} />
      </section>
      <section>
        <h4>Confidence Level</h4>
        <p>{report.confidenceLevel}</p>
      </section>
      <section>
        <h4>Evidence</h4>
        <ReportList items={report.evidence} />
      </section>
      <section>
        <h4>Observed Trends</h4>
        <ReportList items={report.observedTrends} />
      </section>
    </div>
  );
}
