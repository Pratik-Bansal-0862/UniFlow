import { proxyBackend } from "@/app/api/_lib/backend";

export async function POST(
  _request: Request,
  context: { params: Promise<{ action_id: string }> },
) {
  const { action_id } = await context.params;

  return proxyBackend(
    `/api/v1/integrations/google/gmail/actions/${encodeURIComponent(action_id)}/execute`,
    { method: "POST" },
  );
}

