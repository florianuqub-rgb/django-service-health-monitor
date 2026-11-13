import { DurableObject } from "cloudflare:workers";

const PORT = 8000;
const PREVIEW_IDLE_MS = 30 * 60 * 1000;

export class PreviewContainer extends DurableObject {
  async fetch(request) {
    const container = this.ctx.container;
    if (!container) return new Response("Container binding unavailable", { status: 503 });
    if (!this.env.DJANGO_SECRET_KEY || !this.env.SERVICE_TOKEN_KEY || !this.env.PREVIEW_ADMIN_PASSWORD) {
      return new Response("Preview secrets are not configured", { status: 503 });
    }

    const incoming = new URL(request.url);
    if (!container.running) {
      container.start({
        image: container.images.base,
        instance: "basic",
        enableInternet: true,
        env: {
          DJANGO_DEBUG: "0",
          DJANGO_SECRET_KEY: this.env.DJANGO_SECRET_KEY,
          SERVICE_TOKEN_KEY: this.env.SERVICE_TOKEN_KEY,
          PREVIEW_ADMIN_USERNAME: "previewadmin",
          PREVIEW_ADMIN_PASSWORD: this.env.PREVIEW_ADMIN_PASSWORD,
          DJANGO_ALLOWED_HOSTS: `container,${incoming.hostname}`,
          DJANGO_CSRF_TRUSTED_ORIGINS: incoming.origin,
          CELERY_BROKER_URL: "redis://127.0.0.1:6379/0",
          CF_PREVIEW: "1",
        },
      });
    }
    await container.setInactivityTimeout(PREVIEW_IDLE_MS);

    const port = container.getTcpPort(PORT);
    for (let attempt = 0; attempt < 100; attempt++) {
      try {
        const response = await port.fetch("http://container/healthz/", {
          signal: AbortSignal.timeout(1000),
        });
        await response.body?.cancel();
        if (response.ok) break;
      } catch {
        // The image may still be starting.
      }
      if (attempt === 99) return new Response("Preview container did not become ready", { status: 503 });
      await scheduler.wait(200);
    }

    incoming.protocol = "http:";
    incoming.host = "container";
    const forwarded = new Request(incoming, request);
    forwarded.headers.delete("host");
    forwarded.headers.set("x-forwarded-proto", "https");
    return port.fetch(forwarded);
  }
}

export default {
  async fetch(request, env) {
    if (new URL(request.url).pathname === "/") {
      return Response.redirect(new URL("/api/", request.url), 302);
    }
    return env.PREVIEW.getByName("singleton").fetch(request);
  },
};
