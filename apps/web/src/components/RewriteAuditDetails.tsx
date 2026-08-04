import type { RewriteResponse } from "../api/rewrite";
import {
  formatLatency,
  formatTokenCount,
  presentSignalLabel
} from "../presentation/rewriteNecessity";

interface RewriteAuditDetailsProps {
  response: RewriteResponse;
}

export function RewriteAuditDetails({
  response
}: RewriteAuditDetailsProps) {
  const necessity = response.rewrite_necessity;
  const execution = response.provider_execution;

  return (
    <details className="audit-panel">
      <summary>
        <span>View audit details</span>
        <span className="audit-panel__summary-meta">
          Trace {response.trace_id}
        </span>
      </summary>

      <div className="audit-panel__body">
        <section className="audit-section">
          <h3>Routing evidence</h3>

          <dl className="audit-grid">
            <div>
              <dt>Decision</dt>
              <dd>{necessity.decision}</dd>
            </div>

            <div>
              <dt>Score</dt>
              <dd>{necessity.score}/100</dd>
            </div>

            <div>
              <dt>Provider required</dt>
              <dd>
                {necessity.provider_required ? "Yes" : "No"}
              </dd>
            </div>

            <div>
              <dt>Signal count</dt>
              <dd>{necessity.signals.length}</dd>
            </div>
          </dl>

          <p className="audit-rationale">
            {necessity.rationale}
          </p>

          <div className="signal-list">
            {necessity.signals.map((signal, index) => (
              <article
                className="signal-card"
                key={`${signal.signal_type}-${index}`}
              >
                <div className="signal-card__header">
                  <strong>
                    {presentSignalLabel(signal.signal_type)}
                  </strong>
                  <span>{signal.score}/100</span>
                </div>

                <p>{signal.description}</p>

                {signal.evidence.length > 0 && (
                  <ul>
                    {signal.evidence.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                )}
              </article>
            ))}
          </div>
        </section>

        <section className="audit-section">
          <h3>Execution evidence</h3>

          <dl className="audit-grid">
            <div>
              <dt>Primary provider</dt>
              <dd>{execution.primary_provider_name}</dd>
            </div>

            <div>
              <dt>Actual provider</dt>
              <dd>{execution.actual_provider_name}</dd>
            </div>

            <div>
              <dt>Model</dt>
              <dd>{response.model_name}</dd>
            </div>

            <div>
              <dt>Prompt version</dt>
              <dd>{response.prompt_version}</dd>
            </div>

            <div>
              <dt>Latency</dt>
              <dd>{formatLatency(execution.latency_ms)}</dd>
            </div>

            <div>
              <dt>Fallback used</dt>
              <dd>{execution.fallback_used ? "Yes" : "No"}</dd>
            </div>

            <div>
              <dt>Input tokens</dt>
              <dd>
                {formatTokenCount(
                  execution.usage.input_tokens
                )}
              </dd>
            </div>

            <div>
              <dt>Output tokens</dt>
              <dd>
                {formatTokenCount(
                  execution.usage.output_tokens
                )}
              </dd>
            </div>

            <div>
              <dt>Total tokens</dt>
              <dd>
                {formatTokenCount(
                  execution.usage.total_tokens
                )}
              </dd>
            </div>

            <div>
              <dt>Provider error</dt>
              <dd>
                {execution.provider_error_category ?? "None"}
              </dd>
            </div>
          </dl>
        </section>

        <section className="audit-section">
          <h3>Safety decisions</h3>

          <dl className="audit-grid">
            <div>
              <dt>Factual verification</dt>
              <dd>{response.verification.decision}</dd>
            </div>

            <div>
              <dt>Editorial quality</dt>
              <dd>{response.editorial_quality.decision}</dd>
            </div>

            <div>
              <dt>Naturalness score</dt>
              <dd>
                {Math.round(
                  response.editorial_quality
                    .naturalness_score * 100
                )}
                %
              </dd>
            </div>

            <div>
              <dt>Remaining flags</dt>
              <dd>
                {
                  response.editorial_quality
                    .remaining_flag_count
                }
              </dd>
            </div>
          </dl>
        </section>
      </div>
    </details>
  );
}
