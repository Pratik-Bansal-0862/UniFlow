import { proxyBackend } from "../../../../_lib/backend";

export async function POST(request: Request) {
  const body = await request.text();

  return proxyBackend("/api/v1/integrations/google/gmail/drafts", {
    method: "POST",
    body,
  });
}

