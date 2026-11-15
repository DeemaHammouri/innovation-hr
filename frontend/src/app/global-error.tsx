"use client";

/** Last resort when even the root layout fails: static text in both languages, no dependencies. */
export default function GlobalError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <html lang="en">
      <body style={{ fontFamily: "system-ui, sans-serif", margin: 0, minHeight: "100dvh", display: "grid", placeItems: "center", background: "#f5f7fb", color: "#0b1b3a", padding: 16 }}>
        <main style={{ maxWidth: 420, textAlign: "center" }}>
          <h1 style={{ fontSize: 22 }}>Something went wrong · حدث خطأ ما</h1>
          <p style={{ color: "#4a5a78" }}>Your work is safe. Try again. · عملك محفوظ. حاول مرة أخرى.</p>
          <button type="button" onClick={reset} style={{ marginTop: 16, minHeight: 44, padding: "0 20px", borderRadius: 10, border: 0, background: "#0a6be0", color: "#fff", fontSize: 16 }}>
            Try again · حاول مرة أخرى
          </button>
        </main>
      </body>
    </html>
  );
}
