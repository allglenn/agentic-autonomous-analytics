import { NextRequest, NextResponse } from "next/server";

export const maxDuration = 600; // seconds — required for long-running LLM responses

const API_URL = process.env.API_URL || "http://api:8080";

export async function POST(request: NextRequest) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ detail: "Invalid request body." }, { status: 400 });
  }

  try {
    const response = await fetch(`${API_URL}/ask`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(600_000), // 10 min — LLM pipeline can take 60–120 s
    });

    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error("Error connecting to analytics API:", error);
    return NextResponse.json(
      { detail: "Failed to connect to the analytics API." },
      { status: 503 }
    );
  }
}
