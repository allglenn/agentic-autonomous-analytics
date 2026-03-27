import { NextRequest, NextResponse } from "next/server";
import { request as undiciRequest } from "undici";

export const maxDuration = 600; // seconds

const API_URL = process.env.API_URL || "http://api:8080";

export async function POST(req: NextRequest) {
  const reqId = crypto.randomUUID().slice(0, 8);
  const started = Date.now();
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    console.warn(`[api/ask:${reqId}] invalid_json_body`);
    return NextResponse.json({ detail: "Invalid request body." }, { status: 400 });
  }

  try {
    const question =
      body && typeof body === "object" && "question" in body
        ? String((body as { question?: unknown }).question ?? "")
        : "";
    console.info(
      `[api/ask:${reqId}] proxy_start target=${API_URL}/ask question_len=${question.length}`
    );
    // Use undici directly so we can set headersTimeout/bodyTimeout independently.
    // The global fetch in Node.js 18/20 hardcodes headersTimeout=300 s which is
    // too short for a multi-step LLM pipeline.
    const { statusCode, body: responseBody } = await undiciRequest(`${API_URL}/ask`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
      headersTimeout: 600_000, // 10 min
      bodyTimeout: 600_000,
    });

    const data = await responseBody.json();
    console.info(
      `[api/ask:${reqId}] proxy_done status=${statusCode} elapsed_ms=${Date.now() - started}`
    );
    return NextResponse.json(data, { status: statusCode });
  } catch (error) {
    console.error(
      `[api/ask:${reqId}] proxy_failed elapsed_ms=${Date.now() - started}`,
      error
    );
    return NextResponse.json(
      { detail: "Failed to connect to the analytics API." },
      { status: 503 }
    );
  }
}
