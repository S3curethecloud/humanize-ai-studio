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
import DashboardPage from "./pages/DashboardPage";
import PlaceholderPage from "./pages/PlaceholderPage";
import RewriteStudioPage from "./pages/RewriteStudioPage";

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
    page = <RewriteStudioPage />;
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
