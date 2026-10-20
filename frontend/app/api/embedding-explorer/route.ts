import { NextResponse } from "next/server";
import { cookies } from "next/headers";

export async function GET(request: Request) {
  const cookieStore = await cookies();
  const token = cookieStore.get("uniflow_token")?.value;
  if (!token) {
    return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });
  }

  const incomingUrl = new URL(request.url);
  const requestedLimit = incomingUrl.searchParams.get("limit") ?? "500";
  const parsedLimit = Number.parseInt(requestedLimit, 10);
  const limit = Number.isFinite(parsedLimit) ? Math.min(1500, Math.max(1, parsedLimit)) : 500;
  const backendUrl = process.env.BACKEND_API_URL;
  if (!backendUrl) {
    return NextResponse.json({ detail: "Backend URL is not configured" }, { status: 503 });
  }

  try {
    const response = await fetch(`${backendUrl.replace(/\/$/, "")}/api/v1/embedding-explorer?limit=${limit}`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    const body = await response.json().catch(() => ({ detail: "Invalid backend response" }));
    return NextResponse.json(body, { status: response.status });
  } catch {
    return NextResponse.json({ detail: "Embedding explorer backend unavailable" }, { status: 502 });
  }
}
