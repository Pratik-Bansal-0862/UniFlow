import { proxyBackend } from "../../../../_lib/backend";

export async function GET(request: Request) {
  const query = new URL(request.url).search;
  return proxyBackend(`/api/v1/integrations/google/calendar/events${query}`);
}

export async function POST(request: Request) {
  const body = await request.text();

  return proxyBackend("/api/v1/integrations/google/calendar/events", {
    method: "POST",
    body,
  });
}

