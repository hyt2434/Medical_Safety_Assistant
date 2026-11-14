export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    ...init,
    credentials: "include",
    headers: { ...(init.body ? { "Content-Type": "application/json" } : {}), ...init.headers },
  });
  const body = response.status === 204 ? null : await response.json().catch(() => null);
  if (!response.ok) {
    if (response.status === 401 && path !== "/api/auth/login" && path !== "/api/auth/me")
      window.dispatchEvent(new Event("auth:expired"));
    if (response.status === 403) window.dispatchEvent(new Event("auth:refresh"));
    throw new ApiError(response.status, body?.error?.message || body?.detail || "Không thể thực hiện yêu cầu");
  }
  return body as T;
}
