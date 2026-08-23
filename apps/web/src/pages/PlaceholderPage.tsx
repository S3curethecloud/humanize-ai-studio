import {
  ROUTE_METADATA,
  type AppRoute
} from "../app/navigation";

interface PlaceholderPageProps {
  route: AppRoute;
}

export default function PlaceholderPage({
  route
}: PlaceholderPageProps) {
  const metadata = ROUTE_METADATA[route];

  return (
    <div className="enterprise-page">
      <section className="enterprise-placeholder">
        <div className="enterprise-placeholder__status">
          <span
            className="enterprise-status-dot"
            aria-hidden="true"
          />
          Governed surface reserved
        </div>

        <p className="enterprise-eyebrow">
          {metadata.group}
        </p>

        <h1>{metadata.label}</h1>

        <p className="enterprise-placeholder__description">
          {metadata.description}
        </p>

        <div className="enterprise-placeholder__boundary">
          <strong>
            Interface intentionally not activated yet
          </strong>

          <p>
            The application shell is ready for this
            capability, but controls and data will only
            appear after the corresponding governed API
            contract is explicitly integrated.
          </p>
        </div>
      </section>
    </div>
  );
}
