import type {
  EnterpriseAccessContextState
} from "../app/useEnterpriseAccessContext";

interface WorkspacePageProps {
  accessContext: EnterpriseAccessContextState;
}

export default function WorkspacePage({
  accessContext
}: WorkspacePageProps) {
  if (
    accessContext.status !== "connected" ||
    accessContext.context === null
  ) {
    return (
      <div className="enterprise-page">
        <section className="enterprise-analytics-state">
          <div>
            <h1>Workspace unavailable</h1>
            <p>
              Canonical enterprise workspace context
              is required before workspace details
              can be displayed.
            </p>
          </div>
        </section>
      </div>
    );
  }

  const {
    workspace,
    membership,
    permissions
  } = accessContext.context;

  return (
    <div className="enterprise-page">
      <section className="enterprise-analytics-hero">
        <div>
          <p className="enterprise-eyebrow">
            Admin · Workspace
          </p>

          <h1>Enterprise workspace</h1>

          <p className="enterprise-hero__description">
            Canonical workspace identity,
            membership, role, and effective
            enterprise permissions for the
            connected context.
          </p>
        </div>
      </section>

      <section className="enterprise-dashboard-section">
        <div className="enterprise-section__heading">
          <div>
            <p className="enterprise-eyebrow">
              Workspace identity
            </p>
            <h2>{workspace.name}</h2>
          </div>
        </div>

        <div className="enterprise-analytics-metric-grid">
          <article className="enterprise-analytics-metric">
            <span>Workspace ID</span>
            <strong>{workspace.workspace_id}</strong>
          </article>

          <article className="enterprise-analytics-metric">
            <span>Organization ID</span>
            <strong>{workspace.organization_id}</strong>
          </article>

          <article className="enterprise-analytics-metric">
            <span>Status</span>
            <strong>{workspace.status}</strong>
          </article>

          <article className="enterprise-analytics-metric">
            <span>Workspace version</span>
            <strong>{workspace.workspace_version}</strong>
          </article>
        </div>
      </section>

      <section className="enterprise-dashboard-section">
        <div className="enterprise-section__heading">
          <div>
            <p className="enterprise-eyebrow">
              Membership
            </p>
            <h2>Current enterprise role</h2>
          </div>
        </div>

        <div className="enterprise-analytics-metric-grid">
          <article className="enterprise-analytics-metric">
            <span>Membership ID</span>
            <strong>{membership.membership_id}</strong>
          </article>

          <article className="enterprise-analytics-metric">
            <span>User ID</span>
            <strong>{membership.user_id}</strong>
          </article>

          <article className="enterprise-analytics-metric">
            <span>Role</span>
            <strong>{membership.role}</strong>
          </article>

          <article className="enterprise-analytics-metric">
            <span>Status</span>
            <strong>{membership.status}</strong>
          </article>
        </div>
      </section>

      <section className="enterprise-dashboard-section">
        <div className="enterprise-section__heading">
          <div>
            <p className="enterprise-eyebrow">
              Authorization
            </p>
            <h2>Effective permissions</h2>
          </div>

          <p>{permissions.length} permissions</p>
        </div>

        <div className="enterprise-analytics-operation-grid">
          {permissions.map(
            (permission: string) => (
              <article
                className="enterprise-analytics-operation"
                key={permission}
              >
                <div className="enterprise-analytics-operation__header">
                  <span>{permission}</span>
                  <strong>allowed</strong>
                </div>
              </article>
            )
          )}
        </div>
      </section>
    </div>
  );
}
