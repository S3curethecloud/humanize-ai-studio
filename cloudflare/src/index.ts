import {
  Container,
  getContainer,
} from "@cloudflare/containers";
import { env } from "cloudflare:workers";

interface WorkerEnv {
  API_CONTAINER: DurableObjectNamespace<HumanizeApiContainer>;
  ASSETS: Fetcher;
  CLOUDFLARE_API_TOKEN: string;
}

export class HumanizeApiContainer extends Container {
  defaultPort = 8000;
  requiredPorts = [8000];
  sleepAfter = "10m";
  enableInternet = true;

  envVars = {
    API_HOST: "0.0.0.0",
    API_PORT: "8000",
    HUMANIZE_REWRITE_PROVIDER: "cloudflare",
    CLOUDFLARE_ACCOUNT_ID:
      "15405b0703a8372dfa942f9e685a2903",
    CLOUDFLARE_API_TOKEN:
      env.CLOUDFLARE_API_TOKEN,
    CLOUDFLARE_AI_MODEL:
      "@cf/meta/llama-3.3-70b-instruct-fp8-fast",
    CLOUDFLARE_AI_TIMEOUT_SECONDS: "30",
    CLOUDFLARE_AI_FALLBACK_ENABLED: "true",
  };

  override onStart(): void {
    console.log(
      JSON.stringify({
        event: "humanize_api_container_started",
        timestamp: new Date().toISOString(),
        provider: "cloudflare",
        container_identity: "humanize-api-primary-v5",
        token_configured:
          Boolean(env.CLOUDFLARE_API_TOKEN),
      }),
    );
  }

  override onStop(): void {
    console.log(
      JSON.stringify({
        event: "humanize_api_container_stopped",
        timestamp: new Date().toISOString(),
        container_identity: "humanize-api-primary-v5",
      }),
    );
  }

  override onError(error: unknown): void {
    console.error(
      JSON.stringify({
        event: "humanize_api_container_error",
        timestamp: new Date().toISOString(),
        container_identity: "humanize-api-primary-v5",
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
    workerEnv: WorkerEnv,
  ): Promise<Response> {
    const url = new URL(request.url);

    if (!isApiRequest(url.pathname)) {
      return workerEnv.ASSETS.fetch(request);
    }

    const container = getContainer(
      workerEnv.API_CONTAINER,
      "humanize-api-primary-v5",
    );

    return container.fetch(request);
  },
};
