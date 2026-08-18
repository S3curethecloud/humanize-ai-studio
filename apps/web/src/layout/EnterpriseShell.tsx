import {
  type ReactNode
} from "react";

import {
  NAVIGATION_GROUPS,
  ROUTE_METADATA,
  routeHref,
  type AppRoute
} from "../app/navigation";
import {
  type EnterpriseAccessContextState
} from "../app/useEnterpriseAccessContext";

interface EnterpriseShellProps {
  activeRoute: AppRoute;
  accessContext: EnterpriseAccessContextState;
  children: ReactNode;
}

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

function workspaceLabel(
  state: EnterpriseAccessContextState
): string {
  switch (state.status) {
    case "connected":
      return (
        state.context?.workspace.name ??
        "Unavailable"
      );
    case "loading":
      return "Resolving...";
    case "denied":
      return "Access denied";
    case "invalid":
      return "Configuration required";
    case "error":
      return "Unavailable";
    case "unconfigured":
    default:
      return "Not connected";
  }
}

function roleLabel(
  state: EnterpriseAccessContextState
): string {
  if (
    state.status === "connected" &&
    state.context !== null
  ) {
    return displayRole(
      state.context.membership.role
    );
  }

  if (state.status === "loading") {
    return "Resolving...";
  }

  return "Unresolved";
}

export function EnterpriseShell({
  activeRoute,
  accessContext,
  children
}: EnterpriseShellProps) {
  const activeMetadata =
    ROUTE_METADATA[activeRoute];

  return (
    <div className="enterprise-app">
      <aside className="enterprise-sidebar">
        <div className="enterprise-brand">
          <span
            className="enterprise-brand__mark"
            aria-hidden="true"
          >
            H
          </span>

          <div className="enterprise-brand__copy">
            <strong>Humanize AI</strong>
            <span>Enterprise</span>
          </div>
        </div>

        <nav
          className="enterprise-navigation"
          aria-label="Primary navigation"
        >
          {NAVIGATION_GROUPS.map((group) => (
            <section
              className="enterprise-nav-group"
              key={group.label}
            >
              <h2>{group.label}</h2>

              <div className="enterprise-nav-group__items">
                {group.items.map((item) => {
                  const isActive =
                    item.route === activeRoute;

                  return (
                    <a
                      className={[
                        "enterprise-nav-item",
                        isActive
                          ? "enterprise-nav-item--active"
                          : ""
                      ]
                        .filter(Boolean)
                        .join(" ")}
                      href={routeHref(item.route)}
                      key={item.route}
                      aria-current={
                        isActive ? "page" : undefined
                      }
                    >
                      <span
                        className="enterprise-nav-item__marker"
                        aria-hidden="true"
                      />

                      <span className="enterprise-nav-item__label">
                        {item.label}
                      </span>

                      {item.availability === "planned" && (
                        <span className="enterprise-nav-item__planned">
                          Planned
                        </span>
                      )}
                    </a>
                  );
                })}
              </div>
            </section>
          ))}
        </nav>

        <div className="enterprise-sidebar__footer">
          <span
            className="enterprise-status-dot"
            aria-hidden="true"
          />
          <div>
            <strong>Governed workspace</strong>
            <span>
              Control-plane release active
            </span>
          </div>
        </div>
      </aside>

      <section className="enterprise-main">
        <header className="enterprise-topbar">
          <div className="enterprise-topbar__page">
            <span>{activeMetadata.group}</span>
            <strong>{activeMetadata.label}</strong>
          </div>

          <div
            className="enterprise-topbar__context"
            aria-live="polite"
            title={
              accessContext.message ??
              undefined
            }
          >
            <div className="enterprise-context-card">
              <span>Workspace context</span>
              <strong>
                {workspaceLabel(accessContext)}
              </strong>
            </div>

            <div className="enterprise-context-card">
              <span>Access role</span>
              <strong>
                {roleLabel(accessContext)}
              </strong>
            </div>
          </div>
        </header>

        <main className="enterprise-content">
          {children}
        </main>
      </section>
    </div>
  );
}
