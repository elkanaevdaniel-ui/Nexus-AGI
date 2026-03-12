import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.LEADGEN_BACKEND_URL || "http://localhost:8082";
const API_KEY = process.env.LEADGEN_API_KEY || "";

// Only forward these headers to the backend — prevent header injection
const ALLOWED_HEADERS = new Set(["content-type", "accept", "accept-language"]);

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  return proxyRequest(request, await params);
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  return proxyRequest(request, await params);
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  return proxyRequest(request, await params);
}

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  return proxyRequest(request, await params);
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  return proxyRequest(request, await params);
}

async function proxyRequest(
  request: NextRequest,
  params: { path: string[] },
) {
  const path = params.path.join("/");
  const url = new URL(`/api/${path}`, BACKEND_URL);

  // Forward query params
  request.nextUrl.searchParams.forEach((value, key) => {
    url.searchParams.set(key, value);
  });

  // Whitelist headers — only forward safe ones, inject API key server-side
  const headers: Record<string, string> = {};
  request.headers.forEach((value, key) => {
    if (ALLOWED_HEADERS.has(key.toLowerCase())) {
      headers[key] = value;
    }
  });
  if (API_KEY) {
    headers["x-api-key"] = API_KEY;
  }

  const init: RequestInit = {
    method: request.method,
    headers,
  };

  if (request.method !== "GET" && request.method !== "HEAD") {
    const body = await request.text();
    if (body) {
      init.body = body;
    }
  }

  try {
    const response = await fetch(url.toString(), init);
    const responseBody = await response.text();

    return new NextResponse(responseBody || null, {
      status: response.status,
      headers: {
        "content-type": response.headers.get("content-type") || "application/json",
      },
    });
  } catch {
    return NextResponse.json(
      { detail: "Backend service unavailable" },
      { status: 502 },
    );
  }
}
