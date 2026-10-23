import { NextResponse } from "next/server";
import { cookies } from "next/headers";

export async function POST() {
  const token = (await cookies()).get("uniflow_token")?.value;
  if (!token) {
    return NextResponse.json({ detail: "Please sign in first." }, { status: 401 });
  }

  const backendUrl = process.env.BACKEND_API_URL?.replace(/\/+$/, "");
  if (!backendUrl) {
    return NextResponse.json({ detail: "Backend API is not configured." }, { status: 503 });
  }

  try {
    const response = await fetch(`${backendUrl}/api/v1/profile/extract`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, Accept: "application/json" },
      cache: "no-store",
    });
    const text = await response.text();
    return new NextResponse(text, {
      status: response.status,
      headers: { "Content-Type": response.headers.get("content-type") ?? "application/json", "Cache-Control": "no-store" },
    });
  } catch {
    return NextResponse.json({ detail: "Could not reach the UniFlow backend." }, { status: 502 });
  }
}
