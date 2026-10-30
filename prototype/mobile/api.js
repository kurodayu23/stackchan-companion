// 浏览器只访问同源手机代理；真实后端路径由 mobile_proxy.py 的白名单映射。
const API_ROOT = "/mobile-api";
const DEFAULT_TIMEOUT_MS = 8000;
let pairingStatePromise = null;

// 把 HTTP 状态与可展示错误放到同一对象，页面不必各自解析网络异常。
export class ApiError extends Error {
  constructor(message, status = 0) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

// 统一发送 JSON 请求，设置超时、Cookie 和错误处理，页面只负责业务参数。
async function request(path, options = {}) {
  // AbortController 在超时后中止浏览器等待；不保证服务端已经开始的动作也被取消。
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), options.timeout ?? DEFAULT_TIMEOUT_MS);
  const method = options.method || "GET";
  const headers = { Accept: "application/json", ...(options.headers || {}) };
  // 写操作携带代理要求的 CSRF 标记；它与登录/配对凭据承担不同作用。
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
    // 先按响应类型解码，再处理 HTTP 错误，避免把文本错误页强行当 JSON。
    const contentType = response.headers.get("content-type") || "";
    const data = contentType.includes("application/json") ? await response.json() : await response.text();
    if (!response.ok) {
      const detail = typeof data === "object" && data ? data.detail : "";
      if (response.status === 401) pairingStatePromise = null;
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

// 复用正在进行的配对状态查询，减少多个页面同时初始化时的重复请求。
async function isPaired(refresh = false) {
  if (refresh) pairingStatePromise = null;
  if (!pairingStatePromise) {
    pairingStatePromise = fetch("/mobile-health", {
      credentials: "same-origin",
      cache: "no-store",
    }).then(async (response) => {
      if (!response.ok) throw new ApiError("连接暂不可用，请稍后重试", response.status);
      const health = await response.json();
      return health.paired === true;
    }).catch((error) => {
      pairingStatePromise = null;
      throw error;
    });
  }
  return pairingStatePromise;
}

export const api = {
  isPaired,
  get(path, options) {
    return request(path, options);
  },
  post(path, body = {}, options = {}) {
    return request(path, { ...options, method: "POST", body });
  },
};
