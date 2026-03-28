import { NextRequest, NextResponse } from "next/server";

/* ------------------------------------------------------------------ */
/*  Backend URL config                                                 */
/* ------------------------------------------------------------------ */
const BACKEND_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.BACKEND_URL ||
  "https://kisanmind-api-409924770511.asia-south1.run.app";

/* ------------------------------------------------------------------ */
/*  POST handler — proxy to the real backend                           */
/* ------------------------------------------------------------------ */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();

    const backendRes = await fetch(`${BACKEND_URL}/api/advisory`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(120000),
    });

    if (!backendRes.ok) {
      const errorText = await backendRes.text().catch(() => "Unknown error");
      return NextResponse.json(
        { error: `Backend returned ${backendRes.status}`, detail: errorText },
        { status: backendRes.status }
      );
    }

    const data = await backendRes.json();
    return NextResponse.json(data);
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown error";
    console.error("[advisory] Backend error:", message);
    return NextResponse.json(
      { error: "Backend unavailable", detail: message },
      { status: 502 }
    );
  }
}

export async function GET() {
  return NextResponse.json({
    service: "KisanMind Advisory API",
    version: "1.0.0",
    agents: ["SatDrishti", "MandiMitra", "MausamGuru", "VaaniSetu"],
    status: "running",
    mode: "live",
    backend: BACKEND_URL,
  });
}
