import { NextResponse } from "next/server";
import { cookies } from "next/headers";

async function backendRequest(path: string, init?: RequestInit) {
  const token = (await cookies()).get("uniflow_token")?.value;

  if (!token) {
    return NextResponse.json(
      { detail: "Please log in to manage documents." },
      { status: 401 }
    );
  }

  try {
    const response = await fetch(
      `${process.env.BACKEND_API_URL}/api/v1/documents${path}`,
      {
        ...init,
        headers: {
          Authorization: `Bearer ${token}`,
          ...(init?.headers ?? {}),
        },
        cache: "no-store",
      }
    );

    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch {
    return NextResponse.json(
      { detail: "Could not contact the document service." },
      { status: 502 }
    );
  }
}

export async function GET() {
  return backendRequest("");
}

export async function PATCH(request: Request) {
  const body = await request.json().catch(() => null);

  if (
    !body ||
    typeof body.document_id !== "string" ||
    !["personal", "reference", "unverified"].includes(body.category)
  ) {
    return NextResponse.json(
      { detail: "A valid document_id and category are required." },
      { status: 400 }
    );
  }

  return backendRequest(
    `/${encodeURIComponent(body.document_id)}/category`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ category: body.category }),
    }
  );
}
