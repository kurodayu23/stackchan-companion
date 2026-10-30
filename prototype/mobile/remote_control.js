const HEAD_SEND_INTERVAL_MS = 100;
const HEAD_SPEEDS = [100, 220, 520, 850];
const SPEED_LABELS = ["安静", "轻柔", "自然", "活泼"];
// 圆圈中心留一小块死区：手指刚落下时不要把头拽回正前方。
const JOYSTICK_DEAD_ZONE = 0.08;
const DEFAULT_SPEED_LEVEL = 2;

function clamp(value, minimum, maximum) {
  return Math.min(maximum, Math.max(minimum, value));
}

// 连接摇杆、速度圆圈、3D 预览和设备角度 API；本地预览与设备接受状态分别维护。
export function createRemoteController({ api }) {
  const joystick = document.querySelector("#joystick");
  const joystickKnob = document.querySelector("#joystickKnob");
  const poseTitle = document.querySelector("#poseTitle");
  const deviceStatus = document.querySelector("#remoteDeviceStatus");
  const canvas = document.querySelector("#robotPreviewCanvas");
  const speedDots = [...document.querySelectorAll("[data-speed-level]")];
  if (!joystick || !joystickKnob || !canvas) return null;

  let currentYaw = 0;
  let currentPitch = 45;
  let speedLevel = DEFAULT_SPEED_LEVEL;
  let joystickPointer = null;
  let previewPointer = null;
  let previewStartX = 0;
  let previewStartY = 0;
  let previewStartYaw = 0;
  let previewStartPitch = 45;
  let pendingHeadTarget = null;
  let sendTimer = null;
  let requestInFlight = false;
  let lastSentAt = 0;

  function setDeviceStatus(message, state = "idle") {
    if (!deviceStatus) return;
    deviceStatus.textContent = message;
    deviceStatus.dataset.state = state;
  }

  // 球心最多走到圆环内侧，不越出外圈；用实际像素算，换屏幕尺寸也不失准。
  function joystickLimit() {
    const knobSize = joystickKnob.offsetWidth || 46;
    return Math.max(1, (joystick.clientWidth - knobSize) / 2);
  }

  // 速度用圆圈点选：点一下就换一档，界面里不出现数字输入框或滑块。
  function setSpeedLevel(level, send = true) {
    speedLevel = clamp(Math.round(level), 0, SPEED_LABELS.length - 1);
    speedDots.forEach(dot => {
      const active = Number(dot.dataset.speedLevel) === speedLevel;
      dot.classList.toggle("is-active", active);
      dot.setAttribute("aria-checked", String(active));
    });
    window.stackChan3DPreview?.setMotionSpeed(speedLevel);
    if (send) queueHeadTarget();
  }

  // 球停在下巴指向的位置；瞳孔再往里收一点，像它正在“看”那边。
  function moveKnob(yaw, pitch) {
    const limit = joystickLimit();
    const x = (yaw / 128) * limit;
    const y = ((45 - pitch) / 42) * limit;
    joystickKnob.style.transform = `translate(${x}px, ${y}px)`;
    joystickKnob.style.setProperty("--look-x", `${(x / limit) * 5}px`);
    joystickKnob.style.setProperty("--look-y", `${(y / limit) * 5}px`);
  }

  // 先限幅并更新页面姿态；send=false 时只同步显示，不把设备状态反向再次发送。
  function applyRobotPose(yaw, pitch, updateKnob = true, send = true) {
    currentYaw = Math.round(clamp(yaw, -128, 128));
    currentPitch = Math.round(clamp(pitch, 3, 87));
    canvas.dataset.yaw = String(currentYaw);
    canvas.dataset.pitch = String(currentPitch);
    poseTitle.textContent = `左右 ${currentYaw}° · 俯仰 ${currentPitch}°`;
    joystick.setAttribute("aria-valuenow", String(currentYaw));
    joystick.setAttribute("aria-valuetext", `左右 ${currentYaw} 度，俯仰 ${currentPitch} 度`);
    if (updateKnob) moveKnob(currentYaw, currentPitch);
    window.stackChan3DPreview?.setPose(currentYaw, currentPitch);
    if (send) queueHeadTarget();
  }

  // 拖动期间不让轮询覆盖手势；这里显示后端最近头部指令，不能据此证明物理到位。
  function syncConfirmedHeadPose(event) {
    if (joystickPointer !== null || previewPointer !== null) return;
    const state = event?.detail || window.stackChanDeviceState;
    const head = state?.status?.head;
    if (!state?.status?.connected) {
      setDeviceStatus(state?.error?.status === 401 ? "手机未配对" : state?.error ? "连接暂不可用 · 正在重新连接" : "小栈未连接", "failed");
      return;
    }
    if (!Number.isFinite(Number(head?.yaw)) || !Number.isFinite(Number(head?.pitch))) {
      setDeviceStatus("小栈已连接 · 等待姿态", "idle");
      return;
    }
    if (Number.isFinite(Number(head.speed))) {
      const closestLevel = HEAD_SPEEDS.reduce((best, speed, index) => (
        Math.abs(speed - Number(head.speed)) < Math.abs(HEAD_SPEEDS[best] - Number(head.speed)) ? index : best
      ), 0);
      setSpeedLevel(closestLevel, false);
    }
    applyRobotPose(head.yaw, head.pitch, true, false);
    setDeviceStatus(`最近指令 · ${currentYaw}° / ${currentPitch}°`, "confirmed");
  }

  // 只保留最新目标并限制发送频率，避免拖动事件把旧角度堆成网络队列。
  function queueHeadTarget() {
    pendingHeadTarget = {
      yaw: currentYaw,
      pitch: currentPitch,
      speed: HEAD_SPEEDS[speedLevel],
    };
    if (requestInFlight || sendTimer !== null) return;
    const delay = Math.max(0, HEAD_SEND_INTERVAL_MS - (performance.now() - lastSentAt));
    sendTimer = window.setTimeout(() => {
      sendTimer = null;
      flushHeadTarget();
    }, delay);
  }

  // 同一时刻只发一个头部请求；完成后若有新目标，再安排下一次发送。
  async function flushHeadTarget() {
    if (requestInFlight || !pendingHeadTarget) return;
    if (!window.stackChanDeviceState?.status?.connected) {
      pendingHeadTarget = null;
      setDeviceStatus("设备未确认 · 小栈未连接", "failed");
      return;
    }
    const target = pendingHeadTarget;
    pendingHeadTarget = null;
    requestInFlight = true;
    setDeviceStatus("正在发送…", "sending");
    try {
      await api.post("/device/head", target);
      setDeviceStatus(`小栈已接受 · ${target.yaw}° / ${target.pitch}°`, "confirmed");
    } catch (error) {
      setDeviceStatus(`设备未确认 · ${error.message}`, "failed");
    } finally {
      requestInFlight = false;
      lastSentAt = performance.now();
      if (pendingHeadTarget) queueHeadTarget();
    }
  }

  // 手指在圆圈里拖：1:1 跟手，球随手指走；中心留死区，不动则保持上一次角度。
  function setJoystick(x, y) {
    const limit = joystickLimit();
    const distance = Math.hypot(x, y);
    const scale = distance > limit ? limit / distance : 1;
    const offsetX = x * scale;
    const offsetY = y * scale;
    if (distance / limit <= JOYSTICK_DEAD_ZONE) {
      moveKnob(currentYaw, currentPitch);
      return;
    }
    joystickKnob.style.transform = `translate(${offsetX}px, ${offsetY}px)`;
    joystickKnob.style.setProperty("--look-x", `${(offsetX / limit) * 5}px`);
    joystickKnob.style.setProperty("--look-y", `${(offsetY / limit) * 5}px`);
    applyRobotPose((offsetX / limit) * 128, 45 - (offsetY / limit) * 42, false);
  }

  // 捕获当前指针，拖出控件边界后仍能继续处理这次手势。
  joystick.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    joystickPointer = event.pointerId;
    joystick.setPointerCapture(event.pointerId);
    joystick.classList.add("is-dragging");
    const bounds = joystick.getBoundingClientRect();
    setJoystick(event.clientX - bounds.left - bounds.width / 2, event.clientY - bounds.top - bounds.height / 2);
  });
  joystick.addEventListener("pointermove", (event) => {
    if (joystickPointer !== event.pointerId) return;
    event.preventDefault();
    const bounds = joystick.getBoundingClientRect();
    setJoystick(event.clientX - bounds.left - bounds.width / 2, event.clientY - bounds.top - bounds.height / 2);
  });
  // 释放当前拖动状态，避免已经结束的触摸继续控制摇杆。
  function releaseJoystick(event) {
    if (joystickPointer !== event.pointerId) return;
    joystickPointer = null;
    joystick.classList.remove("is-dragging");
    flushHeadTarget();
  }
  joystick.addEventListener("pointerup", releaseJoystick);
  joystick.addEventListener("pointercancel", releaseJoystick);

  function applyKeyboardPose(event) {
    const poses = {
      ArrowLeft: [currentYaw - 8, currentPitch],
      ArrowRight: [currentYaw + 8, currentPitch],
      ArrowUp: [currentYaw, currentPitch + 3],
      ArrowDown: [currentYaw, currentPitch - 3],
      Home: [0, 45],
    };
    if (!poses[event.key]) return;
    event.preventDefault();
    applyRobotPose(...poses[event.key]);
  }
  joystick.addEventListener("keydown", applyKeyboardPose);

  canvas.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    previewPointer = event.pointerId;
    previewStartX = event.clientX;
    previewStartY = event.clientY;
    previewStartYaw = currentYaw;
    previewStartPitch = currentPitch;
    canvas.setPointerCapture(event.pointerId);
    canvas.classList.add("is-controlling");
  });
  canvas.addEventListener("pointermove", (event) => {
    if (previewPointer !== event.pointerId) return;
    event.preventDefault();
    const bounds = canvas.getBoundingClientRect();
    applyRobotPose(
      previewStartYaw + ((event.clientX - previewStartX) / bounds.width) * 256,
      previewStartPitch - ((event.clientY - previewStartY) / bounds.height) * 84,
    );
  });
  function releasePreview(event) {
    if (previewPointer !== event.pointerId) return;
    previewPointer = null;
    canvas.classList.remove("is-controlling");
    flushHeadTarget();
  }
  canvas.addEventListener("pointerup", releasePreview);
  canvas.addEventListener("pointercancel", releasePreview);
  canvas.addEventListener("keydown", applyKeyboardPose);

  speedDots.forEach(dot => {
    dot.addEventListener("click", () => setSpeedLevel(Number(dot.dataset.speedLevel)));
  });

  window.addEventListener("stackchan3dready", () => applyRobotPose(currentYaw, currentPitch, true, false));
  window.addEventListener("stackchandevicestatus", syncConfirmedHeadPose);
  window.addEventListener("stackchanremoteshow", () => {
    syncConfirmedHeadPose();
    applyRobotPose(currentYaw, currentPitch, true, false);
  });
  window.addEventListener("resize", () => applyRobotPose(currentYaw, currentPitch, true, false));
  setSpeedLevel(DEFAULT_SPEED_LEVEL, false);
  applyRobotPose(0, 45, true, false);

  return { flushHeadTarget };
}
