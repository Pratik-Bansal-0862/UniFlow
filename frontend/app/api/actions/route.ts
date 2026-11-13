import { proxyBackend } from "../_lib/backend";

export async function GET() {
  return proxyBackend("/api/v1/actions");
}
