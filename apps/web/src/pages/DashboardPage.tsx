import {
  routeHref
} from "../app/navigation";
import {
  type EnterpriseAccessContextState
} from "../app/useEnterpriseAccessContext";

interface DashboardPageProps {
  accessContext: EnterpriseAccessContextState;
}

interface PostureItem {
  label: string;
  value: string;
  detail: string;
  tone: "ready" | "neutral" | "attention";
}

const SURFACES = [
  {
    title: "Rewrite Studio",
    description:
      "Meaning-preserving rewriting with governed provider execution, verification, and audit evidence.",
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
      "Claim Lock, audit, and EvalOps remain dedicated governed application surfaces.",
    status: "Planned",
    href: routeHref("claim-lock")
  },
  {
    title: "Operations",
    description:
      "Provider, routing, and analytics visibility stays separate from editor controls.",
    status: "Planned",
    href: routeHref("providers")
  }
] as const;

function displayRole(
  role: string
): string {
  return role
    .split(/[_-]/)
    .filter(Boolean)
    .map(
      (segment) =>
        segment.charAt(0).toUpperCase() +
        segment.slice(1)
    )
    .join(" ");
}

function workspacePosture(
  state: EnterpriseAccessContextState
): PostureItem {
  switch (state.status) {
    case "connected":
      return {
        label: "Workspace access",
        value:
          state.context?.workspace.name ??
          "Connected",
        detail:
          "Canonical workspace access context resolved.",
        tone: "ready"
      };

    case "loading":
      return {
        label: "Workspace access",
        value: "Resolving",
        detail:
          "Canonical workspace context is being resolved.",
        tone: "neutral"
      };

    case "denied":
      return {
        label: "Workspace access",
        value: "Access denied",
        detail:
          "The server denied access to the requested workspace.",
        tone: "attention"
      };

    case "invalid":
      return {
        label: "Workspace access",
        value: "Configuration required",
        detail:
          "Both workspace and user bootstrap identifiers are required.",
        tone: "attention"
      };

    case "error":
      return {
        label: "Workspace access",
        value: "Unavailable",
        detail:
          "Workspace access context could not be resolved.",
        tone: "attention"
      };

    case "unconfigured":
    default:
      return {
        label: "Workspace access",
        value: "Not connected",
        detail:
          "No workspace bootstrap context is currently configured.",
        tone: "neutral"
      };
  }
}

function rolePosture(
  state: EnterpriseAccessContextState
): PostureItem {
  if (
    state.status === "connected" &&
    state.context !== null
  ) {
    return {
      label: "Access role",
      value: displayRole(
        state.context.membership.role
      ),
      detail:
        "Role supplied by the canonical workspace membership context.",
      tone: "ready"
    };
  }

  return {
    label: "Access role",
    value: "Unresolved",
    detail:
      "No authoritative workspace role is available in the current context.",
    tone:
      state.status === "denied" ||
      state.status === "invalid" ||
      state.status === "error"
        ? "attention"
        : "neutral"
  };
}

export default function DashboardPage({
  accessContext
}: DashboardPageProps) {
  const posture: PostureItem[] = [
    workspacePosture(accessContext),
    rolePosture(accessContext),
    {
      label: "Rewrite Studio",
      value: "Available",
      detail:
        "Governed rewrite execution and evidence are active.",
      tone: "ready"
    },
    {
      label: "Control plane",
      value: "Authoritative",
      detail:
        "Routing, provider execution, and governance remain outside editor selection.",
      tone: "ready"
    }
  ];

  return (
    <div className="enterprise-page enterprise-dashboard">
      <section className="enterprise-dashboard-hero">
        <div className="enterprise-dashboard-hero__copy">
          <p className="enterprise-eyebrow">
            Governed AI Content Platform
          </p>

          <h1>
            Govern content transformation from one
            enterprise workspace.
          </h1>

          <p className="enterprise-hero__description">
            Humanize Enterprise gives business users a
            controlled application surface while provider
            routing, verification, audit evidence, and
            governance remain authoritative behind the
            workflow.
          </p>

          <div className="enterprise-dashboard-hero__actions">
            <a
              className="enterprise-primary-link"
              href={routeHref("rewrite")}
            >
              Open Rewrite Studio
            </a>

            <span className="enterprise-release-badge">
              Humanize Studio
            </span>
          </div>
        </div>

        <aside
          className="enterprise-dashboard-hero__control"
          aria-label="Platform operating model"
        >
          <p className="enterprise-eyebrow">
            Operating model
          </p>

          <strong>
            Business-facing workspace.
            Control-plane authority preserved.
          </strong>

          <p>
            Editors work with governed capabilities rather
            than selecting model providers or redefining
            routing policy.
          </p>
        </aside>
      </section>

      <section
        className="enterprise-dashboard-section"
        aria-labelledby="workspace-posture-title"
      >
        <div className="enterprise-section__heading">
          <div>
            <p className="enterprise-eyebrow">
              Workspace posture
            </p>

            <h2 id="workspace-posture-title">
              Current application context
            </h2>
          </div>

          <p>
            Only state backed by an existing governed
            contract is presented here.
          </p>
        </div>

        <div className="enterprise-posture-grid">
          {posture.map((item) => (
            <article
              className={[
                "enterprise-posture-card",
                `enterprise-posture-card--${item.tone}`
              ].join(" ")}
              key={item.label}
            >
              <span>{item.label}</span>
              <strong>{item.value}</strong>
              <p>{item.detail}</p>
            </article>
          ))}
        </div>
      </section>

      <section
        className="enterprise-dashboard-section"
        aria-labelledby="workspace-surfaces-title"
      >
        <div className="enterprise-section__heading">
          <div>
            <p className="enterprise-eyebrow">
              Application surfaces
            </p>

            <h2 id="workspace-surfaces-title">
              Operate by governed capability
            </h2>
          </div>

          <p>
            Surfaces become available only when their
            backend authority and application contract are
            intentionally bound.
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
              Editors do not select providers. Governed
              routing determines eligible execution
              targets.
            </p>
          </div>
        </article>

        <article>
          <span>02</span>

          <div>
            <h3>Evidence follows execution</h3>
            <p>
              Audit and observability report what happened
              without becoming policy or routing
              authorities.
            </p>
          </div>
        </article>

        <article>
          <span>03</span>

          <div>
            <h3>No fabricated enterprise state</h3>
            <p>
              Workspace identity, roles, quotas, metrics,
              and operational state remain unresolved until
              governed APIs provide them.
            </p>
          </div>
        </article>
      </section>
    </div>
  );
}
