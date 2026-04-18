export type HealthResponse = {
  status: "ok";
  service: string;
  environment: string;
};

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function fetchHealth(baseUrl: string): Promise<HealthResponse> {
  const url = `${baseUrl.replace(/\/$/, "")}/health`;
  const response = await fetch(url, { cache: "no-store" });

  if (!response.ok) {
    throw new ApiError(`Request failed with status ${response.status}`, response.status);
  }

  const data: unknown = await response.json();
  if (!isHealthResponse(data)) {
    throw new ApiError("Unexpected response shape from /health");
  }

  return data;
}

function isHealthResponse(value: unknown): value is HealthResponse {
  if (typeof value !== "object" || value === null) return false;
  const record = value as Record<string, unknown>;
  return (
    record.status === "ok" &&
    typeof record.service === "string" &&
    typeof record.environment === "string"
  );
}
