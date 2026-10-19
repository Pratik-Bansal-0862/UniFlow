import { NextResponse } from "next/server";
import { cookies } from "next/headers";

export async function POST(request: Request) {
  try {
    const cookieStore = await cookies();
    const token = cookieStore.get("uniflow_token")?.value;

    if (!token) {
      return NextResponse.json(
        { detail: "Please sign in before creating a plan." },
        { status: 401 },
      );
    }

    const body: unknown = await request.json();

    if (
      typeof body !== "object" ||
      body === null ||
      !("objective" in body) ||
      typeof body.objective !== "string" ||
      !body.objective.trim() ||
      body.objective.length > 2000
    ) {
      return NextResponse.json(
        { detail: "Enter an objective of 1–2000 characters." },
        { status: 422 },
      );
    }

    const response = await fetch(
      `${process.env.BACKEND_API_URL}/api/v1/orchestrator/plan`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
        cache: "no-store",
      },
    );

    const data: unknown = await response.json();

    return NextResponse.json(data, { status: response.status });
  } catch {
    return NextResponse.json(
      { detail: "Could not create a plan. Check that FastAPI is running." },
      { status: 502 },
    );
  }
}
