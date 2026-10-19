
import { NextResponse } from "next/server";
import { cookies } from "next/headers";

export async function POST(request: Request) {
  try {
    const cookieStore = await cookies();
    const token = cookieStore.get("uniflow_token")?.value;

    if (!token) {
      return NextResponse.json(
        { detail: "Please log in before uploading a document." },
        { status: 401 }
      );
    }

    const incomingForm = await request.formData();
    const file = incomingForm.get("file");

    if (!(file instanceof File)) {
      return NextResponse.json(
        { detail: "Please select a document to upload." },
        { status: 400 }
      );
    }

    const outgoingForm = new FormData();
    outgoingForm.append("file", file, file.name);

    const response = await fetch(
      `${process.env.BACKEND_API_URL}/api/v1/documents`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
        },
        body: outgoingForm,
        cache: "no-store",
      }
    );

    const data = await response.json();

    return NextResponse.json(data, {
      status: response.status,
    });
  } catch {
    return NextResponse.json(
      { detail: "Could not upload the document. Check that FastAPI is running." },
      { status: 502 }
    );
  }
}
