const FRAME_INTERVAL_MS = 900;
const CAMERA_FRAME_URL = "/mobile-api/device/camera/latest.jpg";

// 摄像头面板：能开就静默自动开，平时画面完全不出现，用户点开才拉流。
export function createCameraPanelController({ api }) {
  const panel = document.querySelector("#cameraPanel");
  const toggle = document.querySelector("#cameraPanelToggle");
  const closeButton = document.querySelector("#cameraPanelClose");
  const frame = document.querySelector("#cameraFrame");
  const frameState = document.querySelector("#cameraFrameState");
  if (!panel || !toggle || !closeButton || !frame || !frameState) return null;

  let opened = false;
  let timer = null;
  let objectUrl = "";
  let starting = false;

  function setState(message) {
    frameState.textContent = message;
    frameState.hidden = false;
  }

  function clearFrame() {
    if (objectUrl) {
      URL.revokeObjectURL(objectUrl);
      objectUrl = "";
    }
    frame.removeAttribute("src");
  }

  // 拉一帧：设备离线或还没出画面时给出明确说法，而不是留一个黑框。
  async function pullFrame() {
    try {
      const response = await fetch(CAMERA_FRAME_URL, { credentials: "same-origin", cache: "no-store" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const blob = await response.blob();
      if (!blob.size) throw new Error("empty frame");
      if (objectUrl) URL.revokeObjectURL(objectUrl);
      objectUrl = URL.createObjectURL(blob);
      frame.src = objectUrl;
      frameState.hidden = true;
    } catch (error) {
      setState("小栈还没有传来画面。等它上线，或确认它在「语音聊天」里。");
    }
  }

  function startPolling() {
    stopPolling();
    pullFrame();
    timer = window.setInterval(pullFrame, FRAME_INTERVAL_MS);
  }

  function stopPolling() {
    if (timer === null) return;
    window.clearInterval(timer);
    timer = null;
  }

  function open() {
    if (opened) return;
    opened = true;
    panel.hidden = false;
    toggle.setAttribute("aria-expanded", "true");
    setState("正在向小栈要画面…");
    startPolling();
  }

  function close() {
    if (!opened) return;
    opened = false;
    panel.hidden = true;
    toggle.setAttribute("aria-expanded", "false");
    stopPolling();
    clearFrame();
  }

  toggle.addEventListener("click", () => (opened ? close() : open()));
  closeButton.addEventListener("click", close);
  panel.addEventListener("click", (event) => {
    if (event.target === panel) close();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && opened) close();
  });

  // 能启动就自动启动：设备不在可取像状态是常态，失败一律静默，不打扰用户。
  async function autoStart() {
    if (starting) return;
    starting = true;
    try {
      await api.post("/device/camera-preview/start", {}, { timeout: 6000 });
    } catch (error) {
      // 忽略：设备未上线或未进入取像模式时，这里拿不到画面属于预期。
    } finally {
      starting = false;
    }
  }

  autoStart();

  return { open, close, autoStart };
}
