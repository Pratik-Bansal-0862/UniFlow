"use client";

export default function GlobalError({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <body>
        <main
          style={{
            minHeight: "100vh",
            display: "flex",
            flexDirection: "column",
            justifyContent: "center",
            alignItems: "center",
            padding: "2rem",
            textAlign: "center",
            fontFamily: "sans-serif",
          }}
        >
          <h2>Something went wrong</h2>
          <p>
            Please try again. If the problem continues, return to the previous
            page.
          </p>
          <button
            type="button"
            onClick={() => reset()}
            style={{ padding: "0.6rem 1.2rem", cursor: "pointer" }}
          >
            Try Again
          </button>
        </main>
      </body>
    </html>
  );
}
