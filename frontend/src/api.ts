export type Service = {
  id: string;
  name: string;
  upstream_base_url: string;
  created_at: string;
  updated_at: string;
};

export type ApiKey = {
  id: string;
  service_id: string;
  name: string;
  key_prefix: string;
  created_at: string;
  revoked_at: string | null;
  secret?: string | null;
};

export type Summary = {
  total_requests: number;
  successful_requests: number;
  failed_requests: number;
  success_rate_percent: number;
  average_duration_ms: number;
  requests_remaining: number;
  request_limit_per_key: number;
};

export type DailyUsage = {
  date: string;
  total_requests: number;
  successful_requests: number;
  failed_requests: number;
  average_duration_ms: number;
};

type RequestOptions = RequestInit & { token?: string | null };
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { token, headers, ...init } = options;
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers,
    },
  });
  if (!response.ok) {
    if (response.status === 401 && typeof window !== "undefined") {
      window.dispatchEvent(new Event("devmeter:unauthorized"));
    }
    const body = await response.json().catch(() => ({}));
    const message = response.status === 401
      ? "Your session has expired. Please sign in again."
      : body.detail ?? `Request failed with status ${response.status}`;
    throw new Error(message);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const api = {
  login: (username: string, password: string) =>
    request<{ access_token: string; expires_at: string }>("/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  me: (token: string) => request<{ username: string }>("/v1/auth/me", { token }),
  services: (token: string) => request<Service[]>("/v1/services", { token }),
  createService: (token: string, body: { name: string; upstream_base_url: string }) =>
    request<Service>("/v1/services", { method: "POST", token, body: JSON.stringify(body) }),
  keys: (token: string, serviceId: string) =>
    request<ApiKey[]>(`/v1/services/${serviceId}/keys`, { token }),
  createKey: (token: string, serviceId: string, name: string) =>
    request<ApiKey>(`/v1/services/${serviceId}/keys`, {
      method: "POST",
      token,
      body: JSON.stringify({ name }),
    }),
  revokeKey: (token: string, keyId: string) =>
    request<void>(`/v1/keys/${keyId}`, { method: "DELETE", token }),
  summary: (token: string, serviceId: string) =>
    request<Summary>(`/v1/services/${serviceId}/usage/summary`, { token }),
  daily: (token: string, serviceId: string, start?: string, end?: string) => {
    const params = new URLSearchParams();
    if (start) params.set("start_date", start);
    if (end) params.set("end_date", end);
    const query = params.toString();
    return request<DailyUsage[]>(
      `/v1/services/${serviceId}/usage/daily${query ? `?${query}` : ""}`,
      { token },
    );
  },
  gateway: (key: string, serviceId: string, body: unknown) =>
    request<unknown>(`/v1/gateway/${serviceId}`, {
      method: "POST",
      token: key,
      body: JSON.stringify(body),
    }),
};
