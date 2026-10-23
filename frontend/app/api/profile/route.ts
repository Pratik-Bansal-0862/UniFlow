import { NextResponse } from "next/server";
import { cookies } from "next/headers";

async function proxy(method: "GET" | "PUT", body?: unknown) {
  const token = (await cookies()).get("uniflow_token")?.value;
  if (!token) {
    return NextResponse.json({ detail: "Please sign in first." }, { status: 401 });
  }

  const backendUrl = process.env.BACKEND_API_URL?.replace(/\/+$/, "");
  if (!backendUrl) {
    return NextResponse.json({ detail: "Backend API is not configured." }, { status: 503 });
  }

  try {
    const response = await fetch(`${backendUrl}/api/v1/profile`, {
      method,
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/json",
        ...(body === undefined ? {} : { "Content-Type": "application/json" }),
      },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      cache: "no-store",
    });
    const text = await response.text();
    return new NextResponse(text, {
      status: response.status,
      headers: {
        "Content-Type": response.headers.get("content-type") ?? "application/json",
        "Cache-Control": "no-store",
      },
    });
  } catch {
    return NextResponse.json({ detail: "Could not reach the UniFlow backend." }, { status: 502 });
  }
}

export async function GET() {
  return proxy("GET");
}

export async function PUT(request: Request) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ detail: "Invalid JSON body." }, { status: 400 });
  }
  return proxy("PUT", body);
}
