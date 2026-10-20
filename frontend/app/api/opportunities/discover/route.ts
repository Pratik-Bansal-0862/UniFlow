import { NextResponse } from "next/server";
import { cookies } from "next/headers";

export async function POST() {
  const cookieStore = await cookies();
  const token = cookieStore.get("uniflow_token")?.value;

  if (!token) {
    return NextResponse.json(
      { detail: "Please sign in to discover opportunities." },
      { status: 401 },
    );
  }

  const backendUrl = process.env.BACKEND_API_URL;
  if (!backendUrl) {
    return NextResponse.json(
      { detail: "Backend API is not configured." },
      { status: 503 },
    );
  }

  try {
    const response = await fetch(
      `${backendUrl.replace(/\/+$/, "")}/api/v1/opportunities/discover`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: "application/json",
        },
        cache: "no-store",
      },
    );

    const contentType = response.headers.get("content-type") ?? "";
    let body: unknown;

    if (contentType.includes("application/json")) {
      body = await response.json().catch(() => ({
        detail: "The backend returned malformed JSON.",
      }));
    } else {
      body = {
        detail: `Backend returned HTTP ${response.status} with a non-JSON response. Check the backend terminal for the underlying error.`,
      };
    }

    return NextResponse.json(body, { status: response.status });
  } catch {
    return NextResponse.json(
      { detail: "Unable to reach the backend. Please try again later." },
      { status: 502 },
    );
  }
}

