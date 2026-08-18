import {
  routeHref
} from "../app/navigation";

const SURFACES = [
  {
    title: "Rewrite Studio",
    description:
      "Existing governed rewrite workflow and evaluation evidence.",
    status: "Available",
    href: routeHref("rewrite")
  },
  {
    title: "Documents & Voice",
    description:
      "Enterprise document and Voice DNA interfaces are staged for controlled integration.",
    status: "Planned",
    href: routeHref("documents")
  },
  {
    title: "Governance",
    description:
      "Claim Lock, audit, and EvalOps receive dedicated governed surfaces.",
    status: "Planned",
    href: routeHref("claim-lock")
  },
  {
    title: "Operations",
    description:
      "Provider, routing, and analytics surfaces stay separate from editor controls.",
    status: "Planned",
    href: routeHref("providers")
  }
] as const;

export default function DashboardPage() {
  return (
    <div className="enterprise-page">
      <section className="enterprise-hero">
        <div>
          <p className="enterprise-eyebrow">
            Governed content operations
          </p>

          <h1>
            Enterprise content transformation,
            without exposing control-plane complexity.
          </h1>

          <p className="enterprise-hero__description">
            Work in business-facing surfaces while
            provider routing, governance, evaluation,
            evidence, and policy remain authoritative
            behind the application.
          </p>
        </div>

        <div className="enterprise-hero__actions">
          <a
            className="enterprise-primary-link"
            href={routeHref("rewrite")}
          >
            Open Rewrite Studio
          </a>

          <span className="enterprise-release-badge">
            Governed release
          </span>
        </div>
      </section>

      <section
        className="enterprise-section"
        aria-labelledby="workspace-surfaces-title"
      >
        <div className="enterprise-section__heading">
          <div>
            <p className="enterprise-eyebrow">
              Workspace surfaces
            </p>
            <h2 id="workspace-surfaces-title">
              Operate by capability
            </h2>
          </div>

          <p>
            Interfaces are activated only when their
            governed backend contract is intentionally
            bound to the UI.
          </p>
        </div>

        <div className="enterprise-capability-grid">
          {SURFACES.map((surface) => (
            <a
              className="enterprise-capability-card"
              href={surface.href}
              key={surface.title}
            >
              <div className="enterprise-capability-card__header">
                <span>{surface.status}</span>
              </div>

              <h3>{surface.title}</h3>
              <p>{surface.description}</p>

              <strong>
                View surface
                <span aria-hidden="true"> →</span>
              </strong>
            </a>
          ))}
        </div>
      </section>

      <section className="enterprise-principles">
        <article>
          <span>01</span>
          <div>
            <h3>Authoritative routing</h3>
            <p>
              Editors do not select model providers.
              Governed routing remains a control-plane
              responsibility.
            </p>
          </div>
        </article>

        <article>
          <span>02</span>
          <div>
            <h3>Evidence follows execution</h3>
            <p>
              Audit and observability surfaces expose
              evidence without becoming policy or routing
              authorities.
            </p>
          </div>
        </article>

        <article>
          <span>03</span>
          <div>
            <h3>No fabricated enterprise state</h3>
            <p>
              Workspace identity, membership, quotas, and
              roles remain visibly unresolved until their
              governed APIs are wired.
            </p>
          </div>
        </article>
      </section>
    </div>
  );
}
