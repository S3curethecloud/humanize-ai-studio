import {
  useEffect,
  useState
} from "react";

import {
  ROUTE_METADATA,
  routeFromHash,
  routeHref,
  type AppRoute
} from "./app/navigation";
import {
  useEnterpriseAccessContext
} from "./app/useEnterpriseAccessContext";
import {
  EnterpriseShell
} from "./layout/EnterpriseShell";
import AnalyticsPage from "./pages/AnalyticsPage";
import AuditPage from "./pages/AuditPage";
import ClaimLockPage from "./pages/ClaimLockPage";
import DashboardPage from "./pages/DashboardPage";
import DocumentsPage from "./pages/DocumentsPage";
import PlaceholderPage from "./pages/PlaceholderPage";
import QuotasPage from "./pages/QuotasPage";
import RewriteStudioPage from "./pages/RewriteStudioPage";
import VoiceDnaPage from "./pages/VoiceDnaPage";
import WorkspacePage from "./pages/WorkspacePage";
import MembersPage from "./pages/MembersPage";

function resolveRoute(): AppRoute {
  return routeFromHash(
    window.location.hash
  );
}

export default function App() {
  const [activeRoute, setActiveRoute] =
    useState<AppRoute>(resolveRoute);

  const accessContext =
    useEnterpriseAccessContext();

  useEffect(() => {
    const handleHashChange = () => {
      setActiveRoute(resolveRoute());
    };

    window.addEventListener(
      "hashchange",
      handleHashChange
    );

    const normalizedHref =
      routeHref(activeRoute);

    if (
      window.location.hash !== normalizedHref
    ) {
      window.history.replaceState(
        null,
        "",
        normalizedHref
      );
    }

    return () => {
      window.removeEventListener(
        "hashchange",
        handleHashChange
      );
    };
  }, []);

  let page;

  if (activeRoute === "dashboard") {
    page = (
      <DashboardPage
        accessContext={accessContext}
      />
    );
  } else if (activeRoute === "rewrite") {
    page = (
      <RewriteStudioPage
        accessContext={accessContext}
      />
    );
  } else if (activeRoute === "documents") {
    page = (
      <DocumentsPage
        accessContext={accessContext}
      />
    );
  } else if (activeRoute === "claim-lock") {
    page = (
      <ClaimLockPage
        accessContext={accessContext}
      />
    );
  } else if (activeRoute === "analytics") {
    page = (
      <AnalyticsPage
        accessContext={accessContext}
      />
    );
  } else if (activeRoute === "audit") {
    page = (
      <AuditPage
        accessContext={accessContext}
      />
    );
  } else if (activeRoute === "voice-dna") {
    page = (
      <VoiceDnaPage
        accessContext={accessContext}
      />
    );
  } else if (activeRoute === "workspace") {
    page = (
      <WorkspacePage
        accessContext={accessContext}
      />
    );
  } else if (activeRoute === "quotas") {
    page = (
      <QuotasPage
        accessContext={accessContext}
      />
    );
  } else if (activeRoute === "members") {
    page = (
      <MembersPage
        accessContext={accessContext}
      />
    );
  } else {
    page = (
      <PlaceholderPage
        route={activeRoute}
      />
    );
  }

  const metadata =
    ROUTE_METADATA[activeRoute];

  useEffect(() => {
    document.title =
      `${metadata.label} | Humanize Enterprise`;
  }, [metadata.label]);

  return (
    <EnterpriseShell
      activeRoute={activeRoute}
      accessContext={accessContext}
    >
      {page}
    </EnterpriseShell>
  );
}
