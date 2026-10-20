import { NextResponse } from "next/server";
import { cookies } from "next/headers";

const backendUrl = process.env.BACKEND_API_URL;

type RouteContext = {
  params: Promise<{ id: string }>;
};

async function proxy(
  request: Request,
  method: "GET" | "PATCH" | "DELETE",
  context: RouteContext
) {
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

    const { id } = await context.params;

    // Accept UUIDs only; never forward arbitrary path input to the backend.
    if (
      !/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(id)
    ) {
      return NextResponse.json(
        { detail: "Invalid opportunity ID." },
        { status: 400 }
      );
    }

    const target = new URL(
      `${backendUrl.replace(/\/+$/, "")}/api/v1/opportunities/${id}`
    );

    const headers: Record<string, string> = {
      Authorization: `Bearer ${token}`,
    };

    let body: string | undefined;

    if (method === "PATCH") {
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
        "Content-Type":
          response.headers.get("content-type") ?? "application/json",
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

export async function GET(request: Request, context: RouteContext) {
  return proxy(request, "GET", context);
}

export async function PATCH(request: Request, context: RouteContext) {
  return proxy(request, "PATCH", context);
}

export async function DELETE(request: Request, context: RouteContext) {
  return proxy(request, "DELETE", context);
}
