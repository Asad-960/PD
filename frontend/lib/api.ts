export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 30000);
  try {
    const response = await fetch(`/api${path}`, { ...init, signal: controller.signal, headers: { "Content-Type": "application/json", ...init?.headers }, cache: "no-store" });
    if (!response.ok) {
      let detail = "The request could not be completed.";
      try {
        const problem = await response.json();
        detail = Array.isArray(problem.detail) ? problem.detail.map((item: { loc: string[]; msg: string }) => `${item.loc.filter(v => v !== "body").join(".")}: ${item.msg}`).join("\n") : problem.detail || detail;
      } catch { detail = response.status === 502 || response.status === 500 ? "The assessment service is unavailable. Check the backend connection and retry." : detail; }
      throw new Error(detail);
    }
    return await response.json() as T;
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") throw new Error("The request timed out. Check the service connection and retry.");
    throw error;
  } finally { clearTimeout(timeout); }
}
