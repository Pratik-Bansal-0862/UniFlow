import { proxyBackend } from "@/app/api/_lib/backend";

export async function POST(
  request: Request,
  context: { params: Promise<{ approval_id: string }> },
) {
  const { approval_id } = await context.params;
  const body = await request.text();

  return proxyBackend(
    `/api/v1/approvals/${encodeURIComponent(approval_id)}/decision`,
    { method: "POST", body },
  );
}

