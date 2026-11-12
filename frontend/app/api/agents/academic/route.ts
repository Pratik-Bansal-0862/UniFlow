import { NextResponse } from "next/server";
import { cookies } from "next/headers";

export async function POST(request: Request) {
  const cookieStore = await cookies();
  const token = cookieStore.get("uniflow_token")?.value;

  if (!token) {
    return NextResponse.json(
      { detail: "Please log in to use the Academic Agent." },
      { status: 401 }
    );
  }

  const backendUrl =
    process.env.BACKEND_API_URL ||
    process.env.BACKEND_URL ||
    "http://127.0.0.1:8001";

  try {
    const body = await request.json();
    const response = await fetch(`${backendUrl}/api/v1/agents/academic/plan`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(body),
      cache: "no-store",
    });

    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (err) {
    return NextResponse.json(
      { detail: "Failed to communicate with Academic Agent backend." },
      { status: 502 }
    );
  }
}