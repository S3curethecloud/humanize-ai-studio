import type { RewriteResponse } from "../api/rewrite";
import { presentRewriteDecision } from "../presentation/rewriteNecessity";

interface RewriteDecisionCardProps {
  response: RewriteResponse;
}

export function RewriteDecisionCard({
  response
}: RewriteDecisionCardProps) {
  const presentation = presentRewriteDecision(
    response.rewrite_necessity
  );

  return (
    <section
      className={`decision-card decision-card--${presentation.tone}`}
      aria-labelledby="rewrite-decision-title"
    >
      <div className="decision-card__header">
        <div>
          <p className="eyebrow">Rewrite decision</p>
          <h2 id="rewrite-decision-title">
            {presentation.label}
          </h2>
        </div>

        <span className="decision-badge">
          {presentation.badge}
        </span>
      </div>

      <h3>{presentation.headline}</h3>
      <p className="decision-card__explanation">
        {presentation.explanation}
      </p>

      <div className="decision-card__status-row">
        <span>
          Factual verification
          <strong>
            {response.verification.decision.toUpperCase()}
          </strong>
        </span>

        <span>
          Editorial quality
          <strong>
            {response.editorial_quality.decision.toUpperCase()}
          </strong>
        </span>
      </div>
    </section>
  );
}
