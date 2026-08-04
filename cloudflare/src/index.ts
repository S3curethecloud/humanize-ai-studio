import {
  Container,
  getContainer,
} from "@cloudflare/containers";

interface Env {
  API_CONTAINER: DurableObjectNamespace<HumanizeApiContainer>;
  ASSETS: Fetcher;
}

export class HumanizeApiContainer extends Container {
  defaultPort = 8000;
  requiredPorts = [8000];
  sleepAfter = "10m";
  enableInternet = true;

  envVars = {
    API_HOST: "0.0.0.0",
    API_PORT: "8000",
    HUMANIZE_REWRITE_PROVIDER: "deterministic",
    CLOUDFLARE_AI_FALLBACK_ENABLED: "true",
    CLOUDFLARE_AI_MODEL: "@cf/openai/gpt-oss-20b",
    CLOUDFLARE_AI_TIMEOUT_SECONDS: "30",
  };

  override onStart(): void {
    console.log(
      JSON.stringify({
        event: "humanize_api_container_started",
        timestamp: new Date().toISOString(),
      }),
    );
  }

  override onStop(): void {
    console.log(
      JSON.stringify({
        event: "humanize_api_container_stopped",
        timestamp: new Date().toISOString(),
      }),
    );
  }

  override onError(error: unknown): void {
    console.error(
      JSON.stringify({
        event: "humanize_api_container_error",
        timestamp: new Date().toISOString(),
        error:
          error instanceof Error
            ? error.message
            : String(error),
      }),
    );
  }
}

function isApiRequest(pathname: string): boolean {
  return (
    pathname.startsWith("/api/") ||
    pathname === "/health" ||
    pathname === "/ready" ||
    pathname === "/metrics"
  );
}

export default {
  async fetch(
    request: Request,
    env: Env,
  ): Promise<Response> {
    const url = new URL(request.url);

    if (!isApiRequest(url.pathname)) {
      return env.ASSETS.fetch(request);
    }

    const container = getContainer(
      env.API_CONTAINER,
      "humanize-api-primary",
    );

    return container.fetch(request);
  },
};
