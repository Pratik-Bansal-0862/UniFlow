import { NextResponse } from "next/server";
import { cookies } from "next/headers";

export async function proxyBackend(
  path: string,
  init: RequestInit = {},
) {
  try {
    const cookieStore = await cookies();
    const token = cookieStore.get("uniflow_token")?.value;

    if (!token) {
      return NextResponse.json(
        { detail: "Please sign in first." },
        { status: 401 },
      );
    }

    const response = await fetch(
      `${process.env.BACKEND_API_URL}${path}`,
      {
        ...init,
        headers: {
          Authorization: `Bearer ${token}`,
          ...(init.body ? { "Content-Type": "application/json" } : {}),
          ...init.headers,
        },
        cache: "no-store",
      },
    );

    const text = await response.text();
    let data: unknown;

    try {
      data = text ? JSON.parse(text) : {};
    } catch {
      data = { detail: text || "The backend returned an invalid response." };
    }

    return NextResponse.json(data, { status: response.status });
  } catch {
    return NextResponse.json(
      { detail: "Cannot reach the backend. Check that FastAPI is running." },
      { status: 502 },
    );
  }
}
