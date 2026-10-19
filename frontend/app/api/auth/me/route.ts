import { NextResponse } from "next/server";
import { cookies } from "next/headers";

export async function GET() {
  try {
    const cookieStore = await cookies();
    const token = cookieStore.get("uniflow_token")?.value;

    if (!token) {
      return NextResponse.json(
        { detail: "Please log in first." },
        { status: 401 }
      );
    }

    const response = await fetch(
      `${process.env.BACKEND_API_URL}/api/v1/auth/me`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
        cache: "no-store",
      }
    );

    const data = await response.json();

    return NextResponse.json(data, {
      status: response.status,
    });
  } catch {
    return NextResponse.json(
      { detail: "Cannot reach the backend. Is FastAPI running?" },
      { status: 502 }
    );
  }
}