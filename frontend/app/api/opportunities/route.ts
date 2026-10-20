import { NextResponse } from "next/server";
import { cookies } from "next/headers";

const backendUrl = process.env.BACKEND_API_URL;

async function proxy(request: Request, method: string) {
  try {
    const token = (await cookies()).get("uniflow_token")?.value;

    if (!token) {
      return NextResponse.json(
        { detail: "Please log in to access your opportunities." },
        { status: 401 }
      );
    }

    if (!backendUrl) {
      return NextResponse.json(
        { detail: "The backend URL is not configured." },
        { status: 503 }
      );
    }

    const incomingUrl = new URL(request.url);
    const target = new URL(`${backendUrl}/api/v1/opportunities`);
    target.search = incomingUrl.search;

    const headers: Record<string, string> = {
      Authorization: `Bearer ${token}`,
    };

    let body: string | undefined;
    if (method === "POST") {
      body = await request.text();
      headers["Content-Type"] = "application/json";
    }

    const response = await fetch(target, {
      method,
      headers,
      body,
      cache: "no-store",
    });

    if (response.status === 204) {
      return new NextResponse(null, { status: 204 });
    }

    const text = await response.text();
    return new NextResponse(text, {
      status: response.status,
      headers: {
        "Content-Type": response.headers.get("content-type") ?? "application/json",
        "Cache-Control": "no-store",
      },
    });
  } catch {
    return NextResponse.json(
      { detail: "Could not reach the UniFlow backend." },
      { status: 502 }
    );
  }
}

export async function GET(request: Request) {
  return proxy(request, "GET");
}

export async function POST(request: Request) {
  return proxy(request, "POST");
}
