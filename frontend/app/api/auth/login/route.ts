import { NextResponse } from "next/server";
import { cookies } from "next/headers";

export async function POST(request: Request) {
  try {
    const form = await request.formData();
    const username = String(form.get("username") ?? "");
    const password = String(form.get("password") ?? "");

    const body = new URLSearchParams({ username, password });

    const response = await fetch(
      `${process.env.BACKEND_API_URL}/api/v1/auth/login`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
        body,
        cache: "no-store",
      }
    );

    const data = await response.json();

    if (!response.ok) {
      return NextResponse.json(data, {
        status: response.status,
      });
    }

    const cookieStore = await cookies();

    cookieStore.set("uniflow_token", data.access_token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/",
      maxAge: 60 * 60,
    });

    return NextResponse.json({ message: "Login successful" });
  } catch {
    return NextResponse.json(
      { detail: "Cannot reach the backend. Is FastAPI running?" },
      { status: 502 }
    );
  }
}