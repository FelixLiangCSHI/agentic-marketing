"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";

import {
  answerProjectQuestion,
  type EvidenceChatContext,
} from "@/agents/evidence-chat-agent";
import { Icon } from "@/components/ui/icon";
import { ConsultingReport } from "@/components/analysis/consulting-report";
import type { ChatAnswer, SuggestedPlanChange } from "@/domain/chat";

interface EvidenceChatPanelProps {
  context: EvidenceChatContext;
  onApplyPlanChange: (change: SuggestedPlanChange) => void;
}

interface ChatMessage {
  messageId: string;
  role: "user" | "agent";
  text: string;
  answer?: ChatAnswer;
}

const QUICK_QUESTIONS = [
  "How has follower growth changed recently?",
  "What are the data quality limitations?",
  "What evidence supports the insights?",
  "What should we publish next month?",
] as const;

export function EvidenceChatPanel({
  context,
  onApplyPlanChange,
}: EvidenceChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const endRef = useRef<HTMLDivElement | null>(null);
  const messageCounterRef = useRef(0);

  useEffect(
    () => () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
    },
    [],
  );

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [messages, loading]);

  function sendQuestion(question: string) {
    const trimmed = question.trim();
    if (!trimmed || loading) {
      return;
    }
    messageCounterRef.current += 1;
    const messageId = `message-${messageCounterRef.current}`;
    setMessages((current) => [
      ...current,
      { messageId, role: "user", text: trimmed },
    ]);
    setInput("");
    setLoading(true);
    timerRef.current = setTimeout(() => {
      const answer = answerProjectQuestion(context, trimmed);
      setMessages((current) => [
        ...current,
        {
          messageId: answer.answerId,
          role: "agent",
          text: answer.report.executiveSummary,
          answer,
        },
      ]);
      setLoading(false);
      timerRef.current = null;
    }, 220);
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    sendQuestion(input);
  }

  return (
    <section className="evidence-chat">
      <header className="evidence-chat__header">
        <div>
          <span className="section-label">EVIDENCE CHAT · MOCK</span>
          <h2>Evidence review</h2>
          <p>Deterministic demo responses use only the current session data.</p>
        </div>
        <span className="mode-badge mode-badge--mock">
          <Icon name="database" size={14} />
          evidence-chat-v1.0
        </span>
      </header>

      <div className="chat-quick-questions" aria-label="Suggested questions">
        {QUICK_QUESTIONS.map((question) => (
          <button
            key={question}
            type="button"
            disabled={loading}
            onClick={() => sendQuestion(question)}
          >
            {question}
          </button>
        ))}
      </div>

      <div className="chat-thread" aria-live="polite">
        {messages.map((message) => (
          <article
            key={message.messageId}
            className={`chat-message chat-message--${message.role}`}
          >
            <span className="chat-message__role">
              {message.role === "agent" ? "Evidence Review" : "You"}
            </span>
            {message.answer ? (
              <ConsultingReport report={message.answer.report} />
            ) : (
              <p>{message.text}</p>
            )}
            {message.answer && message.answer.citations.length > 0 && (
              <details className="chat-evidence">
                <summary>
                  Review evidence ({message.answer.citations.length})
                </summary>
                <ul>
                  {message.answer.citations.map((citation) => (
                    <li key={citation.citationId}>
                      <strong>{citation.label}</strong>
                      {citation.metric && (
                        <>
                          <span>
                            {citation.metric.metricId} ·{" "}
                            {citation.metric.formattedValue}
                          </span>
                          <span>
                            {citation.metric.period
                              ? `${citation.metric.period.start} — ${citation.metric.period.end}`
                              : "No date range available"}
                          </span>
                          <span>
                            Sources: {citation.metric.sourceModules.join(", ")}
                          </span>
                        </>
                      )}
                    </li>
                  ))}
                </ul>
              </details>
            )}
            {message.answer?.suggestedPlanChange && (
              <button
                className="secondary-button secondary-button--small"
                type="button"
                onClick={() => {
                  const change = message.answer?.suggestedPlanChange;
                  if (change) {
                    onApplyPlanChange(change);
                  }
                }}
              >
                <Icon name="check" size={14} />
                Apply plan change
              </button>
            )}
          </article>
        ))}
        {loading && (
          <div className="chat-loading" role="status">
            <Icon name="spinner" size={16} className="spin" />
            Reviewing current project evidence...
          </div>
        )}
        <div ref={endRef} />
      </div>

      <form className="chat-composer" onSubmit={submit}>
        <label className="visually-hidden" htmlFor="evidence-chat-input">
          Enter a question
        </label>
        <input
          id="evidence-chat-input"
          value={input}
          disabled={loading}
          maxLength={400}
          placeholder="Ask about metrics, evidence, recommendations, or plan changes..."
          onChange={(event) => setInput(event.target.value)}
        />
        <button
          className="primary-button"
          type="submit"
          disabled={loading || !input.trim()}
        >
          Review
          <Icon name="arrow" size={15} />
        </button>
      </form>
    </section>
  );
}
