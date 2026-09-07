export type Expense = { id: number; cycle_id: number; amount: string; description: string; category: string; created_at: string };
export type Cycle = { id: number; amount: string; credited_at: string; is_current: boolean; status: string;
  total_expenses: string; remaining_balance: string; category_summary: { category: string; amount: string }[] };
export type Page<T> = { count: number; next: string | null; previous: string | null; results: T[] };
export type Dashboard = { cycle: Cycle | null; can_add_expense: boolean; can_credit_salary: boolean; recent_expenses: Expense[] };

export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); }
}
function message(data: unknown): string {
  if (typeof data === "string") return data;
  if (Array.isArray(data)) return data.map(message).join(" ");
  if (data && typeof data === "object")
    return Object.entries(data).map(([key, value]) => `${key === "detail" || key === "non_field_errors" ? "" : key + ": "}${message(value)}`).join(" ");
  return "The request could not be completed.";
}
export async function api<T>(path: string, method = "GET", data?: unknown): Promise<T> {
  const headers: Record<string, string> = {};
  if (method !== "GET") {
    // Refresh after login rotation and across tabs; this is a CSRF token, not a session secret.
    const csrf = await api<{ csrfToken: string }>("/auth/csrf/");
    headers["X-CSRFToken"] = csrf.csrfToken;
    headers["Content-Type"] = "application/json";
  }
  let response: Response;
  try {
    response = await fetch(`/api${path}`, { method, headers, credentials: "same-origin",
      cache: "no-store", body: data === undefined ? undefined : JSON.stringify(data) });
  } catch {
    throw new ApiError("Cannot reach the server. Check your connection and try again.", 0);
  }
  const body = response.status === 204 ? undefined : await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(body ? message(body) : "The request failed. Refresh and try again.", response.status);
  return body as T;
}
export const currency = (amount: string | number) => new Intl.NumberFormat("en-IN",
  { style: "currency", currency: "INR", minimumFractionDigits: 2 }).format(Number(amount));
export const date = (value: string) => new Intl.DateTimeFormat("en-IN",
  { dateStyle: "medium" }).format(new Date(value));
