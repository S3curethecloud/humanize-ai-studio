import {
  type ReactNode
} from "react";

import {
  NAVIGATION_GROUPS,
  ROUTE_METADATA,
  routeHref,
  type AppRoute
} from "../app/navigation";

interface EnterpriseShellProps {
  activeRoute: AppRoute;
  children: ReactNode;
}

export function EnterpriseShell({
  activeRoute,
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

          <div className="enterprise-topbar__context">
            <div className="enterprise-context-card">
              <span>Workspace context</span>
              <strong>Not connected</strong>
            </div>

            <div className="enterprise-context-card">
              <span>Session role</span>
              <strong>Unresolved</strong>
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
