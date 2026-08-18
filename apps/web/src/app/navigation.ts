export type AppRoute =
  | "dashboard"
  | "rewrite"
  | "documents"
  | "voice-dna"
  | "claim-lock"
  | "audit"
  | "evalops"
  | "providers"
  | "routing"
  | "analytics"
  | "workspace"
  | "members"
  | "quotas"
  | "policies"
  | "settings";

export type NavigationAvailability =
  | "available"
  | "planned";

export interface RouteMetadata {
  label: string;
  group: string;
  description: string;
  availability: NavigationAvailability;
}

export interface NavigationItem {
  route: AppRoute;
  label: string;
  availability: NavigationAvailability;
}

export interface NavigationGroup {
  label: string;
  items: NavigationItem[];
}

export const ROUTE_METADATA: Record<
  AppRoute,
  RouteMetadata
> = {
  dashboard: {
    label: "Dashboard",
    group: "Home",
    description:
      "Enterprise content operations and governed workspace overview.",
    availability: "available"
  },
  rewrite: {
    label: "Rewrite Studio",
    group: "Work",
    description:
      "Meaning-preserving rewriting with existing governed evaluation controls.",
    availability: "available"
  },
  documents: {
    label: "Documents",
    group: "Work",
    description:
      "Governed document workspace and version-oriented content operations.",
    availability: "planned"
  },
  "voice-dna": {
    label: "Voice DNA",
    group: "Work",
    description:
      "Voice profile governance, analysis, and controlled writing guidance.",
    availability: "planned"
  },
  "claim-lock": {
    label: "Claim Lock",
    group: "Governance",
    description:
      "Protected-fact and claim-preservation governance.",
    availability: "planned"
  },
  audit: {
    label: "Audit",
    group: "Governance",
    description:
      "Workspace-scoped evidence and governed activity review.",
    availability: "planned"
  },
  evalops: {
    label: "EvalOps",
    group: "Governance",
    description:
      "Evaluation datasets, runs, evidence, and quality-gate operations.",
    availability: "planned"
  },
  providers: {
    label: "Providers",
    group: "Operations",
    description:
      "Administrative visibility into configured model-provider targets.",
    availability: "planned"
  },
  routing: {
    label: "Routing",
    group: "Operations",
    description:
      "Governed provider-routing policy and execution evidence.",
    availability: "planned"
  },
  analytics: {
    label: "Analytics",
    group: "Operations",
    description:
      "Workspace operational and content-transformation analytics.",
    availability: "planned"
  },
  workspace: {
    label: "Workspace",
    group: "Admin",
    description:
      "Enterprise workspace configuration and governance context.",
    availability: "planned"
  },
  members: {
    label: "Members & Roles",
    group: "Admin",
    description:
      "Membership lifecycle and role-based access administration.",
    availability: "planned"
  },
  quotas: {
    label: "Quotas",
    group: "Admin",
    description:
      "Workspace quota policy, limits, and governed administration.",
    availability: "planned"
  },
  policies: {
    label: "Policies",
    group: "Admin",
    description:
      "Enterprise policy surfaces for governed content operations.",
    availability: "planned"
  },
  settings: {
    label: "Settings",
    group: "Admin",
    description:
      "Application and workspace-level configuration surfaces.",
    availability: "planned"
  }
};

export const NAVIGATION_GROUPS: NavigationGroup[] = [
  {
    label: "Home",
    items: [
      {
        route: "dashboard",
        label: "Dashboard",
        availability: "available"
      }
    ]
  },
  {
    label: "Work",
    items: [
      {
        route: "rewrite",
        label: "Rewrite Studio",
        availability: "available"
      },
      {
        route: "documents",
        label: "Documents",
        availability: "planned"
      },
      {
        route: "voice-dna",
        label: "Voice DNA",
        availability: "planned"
      }
    ]
  },
  {
    label: "Governance",
    items: [
      {
        route: "claim-lock",
        label: "Claim Lock",
        availability: "planned"
      },
      {
        route: "audit",
        label: "Audit",
        availability: "planned"
      },
      {
        route: "evalops",
        label: "EvalOps",
        availability: "planned"
      }
    ]
  },
  {
    label: "Operations",
    items: [
      {
        route: "providers",
        label: "Providers",
        availability: "planned"
      },
      {
        route: "routing",
        label: "Routing",
        availability: "planned"
      },
      {
        route: "analytics",
        label: "Analytics",
        availability: "planned"
      }
    ]
  },
  {
    label: "Admin",
    items: [
      {
        route: "workspace",
        label: "Workspace",
        availability: "planned"
      },
      {
        route: "members",
        label: "Members & Roles",
        availability: "planned"
      },
      {
        route: "quotas",
        label: "Quotas",
        availability: "planned"
      },
      {
        route: "policies",
        label: "Policies",
        availability: "planned"
      },
      {
        route: "settings",
        label: "Settings",
        availability: "planned"
      }
    ]
  }
];

export function routeHref(
  route: AppRoute
): string {
  return `#/${route}`;
}

export function routeFromHash(
  hash: string
): AppRoute {
  const candidate = hash
    .replace(/^#\/?/, "")
    .trim();

  if (
    Object.prototype.hasOwnProperty.call(
      ROUTE_METADATA,
      candidate
    )
  ) {
    return candidate as AppRoute;
  }

  return "dashboard";
}
