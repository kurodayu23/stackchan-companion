// mobile-v2 API 层：浏览器只访问同源手机代理，真实后端路径由代理白名单映射。
const API_ROOT = "/mobile-api";
const DEFAULT_TIMEOUT_MS = 8000;

export class ApiError extends Error {
  constructor(message, status = 0) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request(path, options = {}) {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), options.timeout ?? DEFAULT_TIMEOUT_MS);
  const method = options.method || "GET";
  const headers = { Accept: "application/json", ...(options.headers || {}) };
  if (method !== "GET") Object.assign(headers, { "X-StackChan-CSRF": "1" });
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  try {
    const response = await fetch(`${API_ROOT}${path}`, {
      method,
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      credentials: "same-origin",
      cache: "no-store",
      signal: controller.signal,
    });
    const contentType = response.headers.get("content-type") || "";
    const data = contentType.includes("application/json") ? await response.json() : await response.text();
    if (!response.ok) {
      const detail = typeof data === "object" && data ? data.detail : "";
      throw new ApiError(detail || `请求失败（${response.status}）`, response.status);
    }
    return data;
  } catch (error) {
    if (error.name === "AbortError") throw new ApiError("请求超时，请检查连接", 504);
    if (error instanceof ApiError) throw error;
    throw new ApiError("连接暂不可用，请稍后重试", 0);
  } finally {
    window.clearTimeout(timeout);
  }
}

export const api = {
  get(path, options) { return request(path, options); },
  post(path, body = {}, options = {}) { return request(path, { ...options, method: "POST", body }); },
};