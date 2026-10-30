import { api } from "./api.js";

const TITLES = {
  device: "设备详情",
  companion: "陪伴方式",
  voice: "声音与语气",
  "auto-response": "自动回应",
  network: "Wi-Fi 与网络",
  display: "屏幕与亮度",
  memory: "对话与记忆",
  help: "使用帮助",
  about: "关于小栈",
};

const MEMORY_LABELS = {
  likes: "喜欢的事",
  dislikes: "不喜欢的事",
  goals: "目标",
  important: "重要信息",
  relationship: "相处方式",
  giver: "来自蒋磊的设定",
  temporary: "临时记忆",
  conversation_notes: "对话摘要",
  insights: "相处观察",
};

const LIGHTING_PRESETS = [
  { id: "warm", label: "暖白", color: "#ffd7ad", rgb: { red: 168, green: 118, blue: 82 } },
  { id: "white", label: "柔白", color: "#fff7ea", rgb: { red: 168, green: 158, blue: 142 } },
  { id: "blue", label: "蓝色", color: "#9bc3ff", rgb: { red: 82, green: 122, blue: 168 } },
  { id: "pink", label: "粉色", color: "#ffb3ca", rgb: { red: 168, green: 96, blue: 128 } },
  { id: "green", label: "绿色", color: "#a7e998", rgb: { red: 92, green: 168, blue: 102 } },
  { id: "off", label: "关闭", color: "#d6d7da", rgb: { red: 0, green: 0, blue: 0 } },
];

// 缺失的设备字段显示明确占位内容，不把未上报状态猜成正常值。
function displayValue(value, fallback = "未上报") {
  return value === null || value === undefined || value === "" ? fallback : String(value);
}

// 将接口给出的连接时长转换为适合阅读的文字。
function formatConnectedTime(seconds) {
  const total = Number(seconds);
  if (!Number.isFinite(total) || total < 0) return "未上报";
  if (total < 60) return `${Math.round(total)} 秒`;
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  return hours ? `${hours} 小时 ${minutes} 分` : `${minutes} 分钟`;
}

// 同时更新开关视觉状态和可访问性属性，保持两种读取方式一致。
function setSwitch(button, checked) {
  button.setAttribute("aria-checked", String(Boolean(checked)));
  button.classList.toggle("is-on", Boolean(checked));
}

function syncDynamicRange(input) {
  const minimum = Number(input.min || 0);
  const maximum = Number(input.max || 100);
  const progress = ((Number(input.value) - minimum) / Math.max(1, maximum - minimum)) * 100;
  input.style.setProperty("--range", `${progress}%`);
}

// 设置页面控制器：组织设备信息、配置编辑与页面事件，局部状态由闭包保存。
export function createSettingsController({ activateSettings }) {
  const detail = document.querySelector("#settingsDetail");
  const title = document.querySelector("#settingsDetailTitle");
  const body = document.querySelector("#settingsDetailBody");
  const detailSync = document.querySelector("#settingsDetailSync");
  const status = document.querySelector("#settingsDetailStatus");
  const saveArea = document.querySelector("#settingsSaveArea");
  const saveButton = document.querySelector("#settingsSaveButton");
  const backButton = document.querySelector("#settingsBackButton");
  let activeRoute = null;
  let returnTarget = null;
  let settingsScroll = 0;
  let canPopHistory = false;
  let renderGeneration = 0;
  let saveAction = null;
  let confirmedExperience = null;
  let confirmedBrightness = null;
  let confirmedLighting = null;
  let cameraRefreshTimer = null;
  let firmwareRefreshTimer = null;

  function stopCameraRefresh() {
    if (cameraRefreshTimer === null) return;
    window.clearInterval(cameraRefreshTimer);
    cameraRefreshTimer = null;
  }

  function stopFirmwareRefresh() {
    if (firmwareRefreshTimer === null) return;
    window.clearTimeout(firmwareRefreshTimer);
    firmwareRefreshTimer = null;
  }

  function startFirmwareRefresh(updateState) {
    stopFirmwareRefresh();
    if (!["queued", "accepted", "downloading", "verifying", "rebooting"].includes(updateState)) return;
    firmwareRefreshTimer = window.setTimeout(() => {
      firmwareRefreshTimer = null;
      if (activeRoute === "firmware" && document.visibilityState === "visible") renderActiveRoute();
    }, 3000);
  }

  function syncDetailConnection(state = window.stackChanDeviceState) {
    const lastSeen = Number(state?.status?.last_seen_seconds);
    const networkAge = Number(state?.status?.network?.age_seconds);
    const connected = Boolean(
      state?.status?.connected
      && (!Number.isFinite(lastSeen) || lastSeen <= 12)
      && (!state?.status?.network?.connected || !Number.isFinite(networkAge) || networkAge <= 30),
    );
    const error = state?.error;
    detailSync.dataset.state = error ? "error" : connected ? "online" : "offline";
    detailSync.textContent = error?.status === 401
      ? "需要先完成手机配对"
      : error
        ? "连接暂不可用 · 正在重新连接"
      : connected
        ? "小栈已连接"
        : "小栈未连接";
    body.querySelectorAll("[data-requires-device]").forEach((control) => {
      control.disabled = !connected || control.dataset.uiBusy === "true";
    });
    const device = state?.status || {};
    const network = device.network || {};
    const camera = device.camera || {};
    const music = device.music || {};
    const liveValues = {
      connection: connected ? "已连接 · 工作状态正常" : "当前未连接",
      connectedTime: formatConnectedTime(device.connected_seconds),
      ssid: connected ? displayValue(network.ssid) : "设备离线",
      ip: connected ? displayValue(network.ip) : "设备离线",
      firmware: displayValue(network.firmwareVersion || network.firmware_version),
      camera: camera.available ? (camera.streaming ? "正在预览" : "可用") : "未上报",
      music: music.state === "playing" ? displayValue(music.title, "正在播放") : "当前未播放",
      ota: network.otaSupported || network.ota_supported ? "设备支持" : "未上报",
      rssi: Number.isFinite(Number(network.rssi)) ? `${network.rssi} dBm` : "未上报",
      channel: displayValue(network.channel),
    };
    body.querySelectorAll("[data-live-field]").forEach((node) => {
      const value = liveValues[node.dataset.liveField];
      if (value !== undefined) node.textContent = value;
    });
    const connection = body.querySelector("[data-live-field='connection']");
    if (connection) connection.dataset.tone = connected ? "success" : "muted";
    const networkState = body.querySelector("[data-live-network-state]");
    if (networkState) {
      networkState.textContent = connected && network.connected ? "已连接" : "未连接";
      networkState.dataset.tone = connected && network.connected ? "success" : "muted";
    }
  }

  function setDetailStatus(message = "", tone = "") {
    status.textContent = message;
    status.dataset.tone = tone;
  }

  function setDetailError(error) {
    const message = error?.message || "读取失败，请稍后再试";
    if ([0, 401, 502, 504].includes(Number(error?.status))) {
      detailSync.dataset.state = "error";
      detailSync.textContent = message;
      setDetailStatus("");
      return;
    }
    setDetailStatus(message, "error");
  }

  function configureSave(action = null, { label = "保存设置", disabled = false, visible = Boolean(action) } = {}) {
    saveAction = action;
    saveArea.hidden = !visible;
    saveButton.textContent = label;
    saveButton.disabled = disabled || !action;
  }

  saveButton.addEventListener("click", async () => {
    const action = saveAction;
    if (!action || saveButton.disabled) return;
    saveButton.disabled = true;
    setDetailStatus("正在保存…");
    try {
      await action();
      setDetailStatus("设置已保存", "success");
    } catch (error) {
      setDetailError(error);
    } finally {
      if (action === saveAction) saveButton.disabled = false;
    }
  });

  function setDetailOpen(open) {
    document.body.classList.toggle("settings-detail-open", open);
    detail.hidden = !open;
    document.querySelectorAll("[data-screen]").forEach((screen) => {
      if (open) screen.hidden = true;
    });
  }

  function appendInfoList(container, rows) {
    const list = document.createElement("dl");
    list.className = "settings-info-list";
    rows.forEach(([label, value, tone = "", liveField = ""]) => {
      const row = document.createElement("div");
      row.className = "settings-info-row";
      const term = document.createElement("dt");
      term.textContent = label;
      const description = document.createElement("dd");
      description.textContent = displayValue(value);
      if (tone) description.dataset.tone = tone;
      if (liveField) description.dataset.liveField = liveField;
      row.append(term, description);
      list.append(row);
    });
    container.append(list);
  }

  function makeCurrentCheck(route, generation) {
    return () => activeRoute === route && renderGeneration === generation;
  }

  async function renderDevice(isCurrent) {
    const [deviceResult, firmwareResult] = await Promise.allSettled([
      api.get("/device/status"),
      api.get("/firmware/status"),
    ]);
    if (!isCurrent()) return;
    if (deviceResult.status === "rejected") throw deviceResult.reason;
    const device = deviceResult.value;
    const firmware = firmwareResult.status === "fulfilled" ? firmwareResult.value : null;
    const network = device.network || {};
    const camera = device.camera || {};
    const music = device.music || {};
    body.innerHTML = `
      <section class="settings-card settings-device-hero">
        <div class="settings-device-mark" aria-hidden="true">⌁</div>
        <div><p class="settings-eyebrow">设备</p><h2>小栈</h2><p id="deviceConnectionSummary" data-live-field="connection"></p></div>
      </section>
      <section id="deviceInfoCard" class="settings-card"><h2>设备状态</h2></section>
      <section id="deviceCapabilityCard" class="settings-card"><h2>实时能力</h2></section>`;
    const connection = document.querySelector("#deviceConnectionSummary");
    connection.textContent = device.connected ? "已连接 · 工作状态正常" : "当前未连接";
    connection.dataset.tone = device.connected ? "success" : "muted";
    appendInfoList(document.querySelector("#deviceInfoCard"), [
      ["连接时长", formatConnectedTime(device.connected_seconds), "", "connectedTime"],
      ["小栈电量", "设备未上报"],
      ["当前网络", network.ssid, "", "ssid"],
      ["IP 地址", network.ip, "", "ip"],
      ["固件版本", network.firmwareVersion || network.firmware_version || firmware?.device?.current_version, "", "firmware"],
    ]);
    appendInfoList(document.querySelector("#deviceCapabilityCard"), [
      ["摄像头", camera.available ? (camera.streaming ? "正在预览" : "可用") : "未上报", "", "camera"],
      ["音乐", music.state === "playing" ? displayValue(music.title, "正在播放") : "当前未播放", "", "music"],
      ["无线更新", network.otaSupported || network.ota_supported ? "设备支持" : "未上报", "", "ota"],
    ]);
    setDetailStatus("");
  }

  async function renderCompanion(isCurrent) {
    const response = await api.get("/experience");
    if (!isCurrent()) return;
    confirmedExperience = response;
    const persona = response.persona || {};
    const reaction = response.reaction || {};
    body.innerHTML = `
      <section class="settings-card">
        <p class="settings-eyebrow">我们怎么称呼彼此</p>
        <label class="setting-field" for="companionAddress">你的称呼
          <input id="companionAddress" name="address_name" type="text" maxlength="20" autocomplete="off" placeholder="例如：依婵…">
        </label>
        <label class="setting-field" for="companionStyle">陪伴风格
          <select id="companionStyle" name="companion_style">
            <option value="lively">活泼温暖</option>
            <option value="gentle">安静温柔</option>
          </select>
        </label>
      </section>
      <section class="settings-card">
        <div class="settings-range-heading"><div><h2>回应活泼程度</h2><p>调整动作与回应节奏</p></div><output id="livelinessValue"></output></div>
        <input id="livelinessRange" type="range" min="0" max="3" step="1" aria-label="回应活泼程度">
        <div class="settings-range-labels" aria-hidden="true"><span>安静</span><span>自然</span><span>活泼</span></div>
      </section>`;
    const addressInput = document.querySelector("#companionAddress");
    const styleSelect = document.querySelector("#companionStyle");
    const livelinessInput = document.querySelector("#livelinessRange");
    const livelinessOutput = document.querySelector("#livelinessValue");
    addressInput.value = displayValue(persona.address_name, "依婵");
    if (!["lively", "gentle"].includes(persona.style)) {
      const current = document.createElement("option");
      current.value = persona.style || "current";
      current.textContent = `当前模式（${displayValue(persona.style)}）`;
      current.disabled = true;
      styleSelect.prepend(current);
    }
    styleSelect.value = persona.style || "lively";
    livelinessInput.value = String(Number.isInteger(reaction.liveliness_level) ? reaction.liveliness_level : 2);
    const updateLiveliness = () => {
      const labels = ["安静", "轻柔", "自然", "活泼"];
      livelinessOutput.textContent = labels[Number(livelinessInput.value)] || "自然";
      syncDynamicRange(livelinessInput);
    };
    livelinessInput.addEventListener("input", updateLiveliness);
    updateLiveliness();
    configureSave(async () => {
      const previous = confirmedExperience;
      const nextName = addressInput.value.trim();
      if (!nextName) {
        addressInput.focus();
        throw new Error("请输入 1–20 个字的称呼");
      }
      const personaPatch = { address_name: nextName };
      if (["lively", "gentle"].includes(styleSelect.value)) personaPatch.style = styleSelect.value;
      try {
        const response = await api.post("/experience", {
          persona: personaPatch,
          reaction: { liveliness_level: Number(livelinessInput.value) },
        });
        confirmedExperience = response;
      } catch (error) {
        addressInput.value = displayValue(previous?.persona?.address_name, "依婵");
        styleSelect.value = previous?.persona?.style || "lively";
        livelinessInput.value = String(previous?.reaction?.liveliness_level ?? 2);
        updateLiveliness();
        throw error;
      }
    });
    setDetailStatus("");
  }

  async function renderVoice(isCurrent) {
    const [voiceResponse, experience] = await Promise.all([
      api.get("/device/factory-voices"),
      api.get("/experience"),
    ]);
    if (!isCurrent()) return;
    const voices = Array.isArray(voiceResponse.voices) ? voiceResponse.voices : [];
    const selectSupported = voiceResponse.select_supported === true;
    const currentProfile = experience.voice?.profile || "未上报";
    const currentVoice = voices.find((voice) => voice.id === currentProfile);
    body.innerHTML = `
      <section class="settings-card">
        <p class="settings-eyebrow">当前声音</p><h2 id="currentVoiceName"></h2>
        <p class="settings-note">浏览小栈中已有的声音。</p>
      </section>
      <section class="settings-card">
        <label class="setting-field" for="voiceSearch">浏览声音</label>
        <div id="voiceCombobox" class="voice-combobox" role="combobox" aria-expanded="false" aria-haspopup="listbox" aria-controls="voiceOptionList">
          <input id="voiceSearch" name="voice_search" type="search" autocomplete="off" spellcheck="false" placeholder="搜索名称或编号…">
          <button id="voiceToggle" type="button" aria-label="展开声音列表"><span aria-hidden="true">⌄</span></button>
        </div>
        <div id="voiceOptionList" class="voice-option-list" role="listbox" aria-label="可用声音" hidden></div>
        <p id="voiceCapabilityNote" class="settings-callout"></p>
        <button class="secondary-action voice-unavailable" type="button" disabled></button>
      </section>`;
    const currentName = document.querySelector("#currentVoiceName");
    const combobox = document.querySelector("#voiceCombobox");
    const search = document.querySelector("#voiceSearch");
    const toggle = document.querySelector("#voiceToggle");
    const optionList = document.querySelector("#voiceOptionList");
    const capability = document.querySelector("#voiceCapabilityNote");
    const unavailable = document.querySelector(".voice-unavailable");
    currentName.textContent = currentVoice
      ? `${displayValue(currentVoice.label, currentVoice.id)} · ${currentVoice.id}`
      : currentProfile;
    capability.textContent = selectSupported
      ? "当前版本可浏览声音列表，选择功能尚未开放。"
      : "可搜索并浏览声音；当前小栈暂不支持切换。";
    unavailable.textContent = "暂不可切换";
    search.hidden = !(voices.length > 8);
    if (search.hidden) search.placeholder = "展开声音列表…";

    const setExpanded = (expanded) => {
      combobox.setAttribute("aria-expanded", String(expanded));
      optionList.hidden = !expanded;
      toggle.setAttribute("aria-label", expanded ? "收起声音列表" : "展开声音列表");
    };
    const renderOptions = () => {
      const query = search.value.trim().toLocaleLowerCase("zh-CN");
      const filtered = voices.filter((voice) => `${voice.label || ""} ${voice.id || ""}`.toLocaleLowerCase("zh-CN").includes(query));
      optionList.replaceChildren();
      if (!filtered.length) {
        const empty = document.createElement("p");
        empty.className = "voice-empty";
        empty.textContent = "没有匹配的声音";
        optionList.append(empty);
        return;
      }
      filtered.forEach((voice) => {
        const option = document.createElement("div");
        option.className = "voice-option";
        option.setAttribute("role", "option");
        option.setAttribute("aria-disabled", "true");
        option.setAttribute("aria-selected", String(voice.id === currentProfile));
        const label = document.createElement("strong");
        label.textContent = displayValue(voice.label, voice.id);
        const id = document.createElement("small");
        id.textContent = displayValue(voice.id);
        option.append(label, id);
        optionList.append(option);
      });
    };
    toggle.addEventListener("click", () => setExpanded(combobox.getAttribute("aria-expanded") !== "true"));
    search.addEventListener("focus", () => setExpanded(true));
    search.addEventListener("input", () => {
      renderOptions();
      setExpanded(true);
    });
    search.addEventListener("keydown", (event) => {
      if (event.key === "Escape") setExpanded(false);
    });
    renderOptions();
    setDetailStatus("");
  }

  async function updateExperienceToggle(button, section, key) {
    const previousValue = button.getAttribute("aria-checked") === "true";
    const nextValue = !previousValue;
    setSwitch(button, nextValue);
    button.disabled = true;
    setDetailStatus("正在发送…");
    try {
      const response = await api.post("/experience", { [section]: { [key]: nextValue } });
      confirmedExperience = response;
      setDetailStatus("设置已确认", "success");
      return response;
    } catch (error) {
      setSwitch(button, previousValue);
      setDetailError(error);
      return null;
    } finally {
      button.disabled = false;
    }
  }

  function syncReactionSwitches(reaction) {
    body.querySelectorAll("[data-reaction-key]").forEach((button) => {
      setSwitch(button, reaction[button.dataset.reactionKey] === true);
    });
  }

  async function renderAutoResponse(isCurrent) {
    const response = await api.get("/experience");
    if (!isCurrent()) return;
    confirmedExperience = response;
    const reaction = response.reaction || {};
    body.innerHTML = `
      <section class="settings-card">
        <div class="settings-card-heading"><div><h2>自动回应</h2><p>小栈根据当前设备能力做出轻量反应</p></div></div>
        <div class="settings-switch-list">
          <div class="settings-switch-row"><div><strong>听到你叫“小栈”时</strong><small>允许小栈主动看向附近</small></div><button type="button" class="settings-switch" role="switch" aria-label="听到称呼时自动环顾" data-reaction-key="auto_gaze_enabled"></button></div>
          <div class="settings-switch-row"><div><strong>检测到你正在看它时</strong><small>根据摄像头状态调整面向</small></div><button type="button" class="settings-switch" role="switch" aria-label="人物跟随" data-reaction-key="visual_tracking_enabled"></button></div>
          <div class="settings-switch-row"><div><strong>回应前的轻提示</strong><small>思考时给出短暂表情反馈</small></div><button type="button" class="settings-switch" role="switch" aria-label="思考提示" data-reaction-key="thinking_cue_enabled"></button></div>
        </div>
      </section>
      `;
    syncReactionSwitches(reaction);
    body.querySelectorAll("[data-reaction-key]").forEach((button) => {
      const key = button.dataset.reactionKey;
      button.addEventListener("click", async () => {
        const switches = [...body.querySelectorAll("[data-reaction-key]")];
        switches.forEach((control) => control.disabled = true);
        const updated = await updateExperienceToggle(button, "reaction", key);
        if (updated) syncReactionSwitches(updated.reaction || {});
        switches.forEach((control) => control.disabled = false);
      });
    });
    setDetailStatus("");
  }

  function decodeBase64(value) {
    const binary = window.atob(value);
    return Uint8Array.from(binary, (character) => character.charCodeAt(0));
  }

  function encodeBase64(value) {
    const bytes = new Uint8Array(value);
    let binary = "";
    bytes.forEach((byte) => { binary += String.fromCharCode(byte); });
    return window.btoa(binary);
  }

  async function encryptNetworkPassword(password) {
    if (!window.crypto?.subtle) throw new Error("当前浏览器不支持安全配网，请更新浏览器后重试");
    const keyInfo = await api.get("/device/network/key");
    if (keyInfo.algorithm !== "RSA-OAEP-256") throw new Error("安全配网暂不可用，请稍后重试");
    const publicKey = await window.crypto.subtle.importKey(
      "spki",
      decodeBase64(keyInfo.public_key),
      { name: "RSA-OAEP", hash: "SHA-256" },
      false,
      ["encrypt"],
    );
    const ciphertext = await window.crypto.subtle.encrypt(
      { name: "RSA-OAEP" },
      publicKey,
      new TextEncoder().encode(password),
    );
    return { key_id: keyInfo.key_id, password_ciphertext: encodeBase64(ciphertext) };
  }

  function renderNetworkList(container, networks, onSelect) {
    container.replaceChildren();
    if (!networks.length) {
      const empty = document.createElement("p");
      empty.className = "settings-empty";
      empty.textContent = "没有扫描到可显示的 Wi-Fi";
      container.append(empty);
      return;
    }
    networks.forEach((network) => {
      const row = document.createElement("button");
      row.type = "button";
      row.className = "network-item";
      const icon = document.createElement("span");
      icon.className = "network-signal";
      icon.textContent = "◔";
      icon.setAttribute("aria-hidden", "true");
      const copy = document.createElement("span");
      const name = document.createElement("strong");
      name.textContent = displayValue(network.ssid, "隐藏网络");
      const meta = document.createElement("small");
      const security = network.open ? "开放网络" : "需要密码";
      meta.textContent = `${security} · 信号 ${displayValue(network.signal, "未知")}%`;
      copy.append(name, meta);
      row.append(icon, copy);
      row.addEventListener("click", () => onSelect(network, row));
      container.append(row);
    });
  }

  async function renderNetwork(isCurrent) {
    const response = await api.get("/device/status");
    if (!isCurrent()) return;
    const network = response.network || {};
    body.innerHTML = `
      <section id="networkCurrentCard" class="settings-card"><div class="settings-card-heading"><div><p class="settings-eyebrow">当前网络</p><h2 id="networkName"></h2></div><span id="networkState" class="settings-state"></span></div></section>
      <section class="settings-card">
        <div class="settings-card-heading"><div><h2>附近网络</h2><p>选择一个网络，让小栈主动连接</p></div><button id="scanNetworkButton" class="settings-inline-action" type="button">重新扫描</button></div>
        <div id="networkList" class="network-list"><p class="settings-empty">点击“重新扫描”读取附近网络</p></div>
      </section>
      <section id="networkConnectCard" class="settings-card network-connect-card" hidden>
        <p class="settings-eyebrow">连接到</p><h2 id="networkSelectedName"></h2>
        <label class="setting-field">Wi-Fi 密码<input id="networkPassword" type="password" autocomplete="new-password" maxlength="64" placeholder="开放网络可留空"></label>
        <button id="networkConnectButton" class="primary-action" type="button">连接小栈</button>
        <p id="networkProvisionState" class="network-provision-state" role="status" aria-live="polite"></p>
      </section>`;
    const networkName = document.querySelector("#networkName");
    networkName.dataset.liveField = "ssid";
    networkName.textContent = displayValue(network.ssid, "未连接 Wi-Fi");
    const state = document.querySelector("#networkState");
    state.dataset.liveNetworkState = "";
    state.textContent = network.connected ? "已连接" : "未连接";
    state.dataset.tone = network.connected ? "success" : "muted";
    appendInfoList(document.querySelector("#networkCurrentCard"), [
      ["信号强度", Number.isFinite(Number(network.rssi)) ? `${network.rssi} dBm` : "未上报", "", "rssi"],
      ["小栈 IP", network.ip, "", "ip"],
      ["频道", network.channel, "", "channel"],
    ]);
    const scanButton = document.querySelector("#scanNetworkButton");
    const networkList = document.querySelector("#networkList");
    const connectCard = document.querySelector("#networkConnectCard");
    const selectedName = document.querySelector("#networkSelectedName");
    const passwordInput = document.querySelector("#networkPassword");
    const connectButton = document.querySelector("#networkConnectButton");
    const provisionState = document.querySelector("#networkProvisionState");
    let selectedNetwork = null;

    const selectNetwork = (item, row) => {
      selectedNetwork = item;
      networkList.querySelectorAll(".network-item").forEach((button) => button.classList.remove("is-selected"));
      row.classList.add("is-selected");
      selectedName.textContent = displayValue(item.ssid, "隐藏网络");
      passwordInput.disabled = item.open === true;
      passwordInput.value = "";
      connectCard.hidden = false;
      provisionState.textContent = "准备连接";
      provisionState.dataset.tone = "";
    };

    const waitUntilOnline = async (targetSsid) => {
      const deadline = Date.now() + 45000;
      provisionState.textContent = "正在等待小栈上线…";
      while (Date.now() < deadline) {
        await new Promise((resolve) => window.setTimeout(resolve, 1800));
        try {
          const latest = await api.post("/device/network/status");
          if (latest.network?.connected && latest.network.ssid === targetSsid) return latest.network;
        } catch (_error) {
          // Switching Wi-Fi temporarily closes the device session; keep waiting within the deadline.
        }
      }
      throw new Error("连接超时，请检查密码和信号后重试");
    };

    connectButton.addEventListener("click", async () => {
      if (!selectedNetwork?.ssid) return;
      connectButton.disabled = true;
      scanButton.disabled = true;
      provisionState.textContent = "正在安全发送网络信息…";
      provisionState.dataset.tone = "";
      const password = passwordInput.value;
      try {
        const encrypted = await encryptNetworkPassword(password);
        passwordInput.value = "";
        await api.post("/device/network/connect", { ssid: selectedNetwork.ssid, ...encrypted }, {
          headers: { "X-StackChan-Confirm": "connect-wifi" },
          timeout: 12000,
        });
        provisionState.textContent = "小栈正在切换网络…";
        const online = await waitUntilOnline(selectedNetwork.ssid);
        provisionState.textContent = "已上线";
        provisionState.dataset.tone = "success";
        networkName.textContent = displayValue(online.ssid);
        state.textContent = "已连接";
        state.dataset.tone = "success";
      } catch (error) {
        provisionState.textContent = error?.message || "连接失败，请稍后重试";
        provisionState.dataset.tone = "error";
      } finally {
        passwordInput.value = "";
        connectButton.disabled = false;
        scanButton.disabled = false;
      }
    });

    scanButton.addEventListener("click", async () => {
      scanButton.dataset.uiBusy = "true";
      scanButton.disabled = true;
      scanButton.textContent = "扫描中…";
      setDetailStatus("正在扫描附近 Wi-Fi…");
      try {
        const result = await api.post("/device/network/scan");
        if (result.ok === false) throw new Error("Wi-Fi 扫描失败，请确认小栈连接");
        const networks = Array.isArray(result.wifi_scan?.networks) ? result.wifi_scan.networks : [];
        renderNetworkList(networkList, networks, selectNetwork);
        setDetailStatus(`扫描完成，共 ${networks.length} 个网络`, "success");
      } catch (error) {
        setDetailError(error);
      } finally {
        scanButton.dataset.uiBusy = "false";
        scanButton.textContent = "重新扫描";
        syncDetailConnection();
      }
    });
    setDetailStatus("");
  }

  async function renderDisplay(isCurrent) {
    const device = await api.get("/device/status");
    if (!isCurrent()) return;
    const initialValue = confirmedBrightness ?? 60;
    body.innerHTML = `
      <section class="settings-card settings-display-preview" aria-hidden="true"><div><span>⌒</span><span>‿</span></div></section>
      <section class="settings-card">
        <div class="settings-range-heading"><div><h2>屏幕亮度</h2><p>调整后显示最近一次设定</p></div><output id="brightnessValue"></output></div>
        <input id="brightnessRange" type="range" min="1" max="100" step="1" aria-label="屏幕亮度" data-requires-device>
      </section>`;
    const input = document.querySelector("#brightnessRange");
    const output = document.querySelector("#brightnessValue");
    input.value = String(initialValue);
    input.disabled = !device.connected;
    output.textContent = confirmedBrightness === null ? "未上报" : `${confirmedBrightness}%`;
    syncDynamicRange(input);
    input.addEventListener("input", () => {
      output.textContent = `待发送 ${input.value}%`;
      syncDynamicRange(input);
    });
    input.addEventListener("change", async () => {
      const previousValue = confirmedBrightness ?? initialValue;
      const requested = Number(input.value);
      input.dataset.uiBusy = "true";
      input.disabled = true;
      setDetailStatus("正在发送亮度…");
      try {
        const response = await api.post("/device/brightness", { brightness: requested });
        const confirmed = Number(response.brightness);
        if (response.ok === false || !Number.isFinite(confirmed) || confirmed < 1 || confirmed > 100) {
          throw new Error("小栈未接受亮度指令");
        }
        confirmedBrightness = confirmed;
        input.value = String(confirmedBrightness);
        output.textContent = `${confirmedBrightness}%`;
        setDetailStatus("小栈已接受亮度设定", "success");
      } catch (error) {
        input.value = String(previousValue);
        output.textContent = confirmedBrightness === null ? "未确认" : `${confirmedBrightness}%`;
        setDetailError(error);
      } finally {
        input.dataset.uiBusy = "false";
        syncDetailConnection();
        syncDynamicRange(input);
      }
    });
    setDetailStatus("");
  }

  function selectLighting(presetId) {
    body.querySelectorAll("[data-lighting-id]").forEach((button) => {
      const selected = Boolean(presetId) && button.dataset.lightingId === presetId;
      button.classList.toggle("is-selected", selected);
      button.setAttribute("aria-pressed", String(selected));
    });
  }

  async function renderLighting(isCurrent) {
    const device = await api.get("/device/status");
    if (!isCurrent()) return;
    body.innerHTML = `
      <section class="settings-card">
        <div class="settings-card-heading"><div><h2>灯光颜色</h2><p>选择小栈的头顶灯颜色</p></div></div>
        <div id="lightingGrid" class="lighting-grid"></div>
      </section>`;
    const grid = document.querySelector("#lightingGrid");
    LIGHTING_PRESETS.forEach((preset) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "lighting-option";
      button.dataset.lightingId = preset.id;
      button.dataset.requiresDevice = "";
      button.setAttribute("aria-pressed", "false");
      button.disabled = !device.connected;
      const swatch = document.createElement("span");
      swatch.className = "lighting-swatch";
      swatch.style.background = preset.color;
      swatch.setAttribute("aria-hidden", "true");
      const label = document.createElement("span");
      label.textContent = preset.label;
      button.append(swatch, label);
      button.addEventListener("click", async () => {
        grid.querySelectorAll("button").forEach((item) => {
          item.dataset.uiBusy = "true";
          item.disabled = true;
        });
        setDetailStatus("正在发送灯光颜色…");
        try {
          const response = await api.post("/device/led", preset.rgb);
          if (response.ok === false) throw new Error("小栈未接受灯光指令");
          confirmedLighting = preset.id;
          selectLighting(confirmedLighting);
          setDetailStatus(`小栈已接受${preset.label}灯光设定`, "success");
        } catch (error) {
          selectLighting(confirmedLighting);
          setDetailError(error);
        } finally {
          grid.querySelectorAll("button").forEach((item) => item.dataset.uiBusy = "false");
          syncDetailConnection();
        }
      });
      grid.append(button);
    });
    selectLighting(confirmedLighting);
    setDetailStatus("");
  }

  async function renderFirmware(isCurrent) {
    const deviceStatus = await api.get("/device/status");
    if (!isCurrent()) return;
    const network = deviceStatus.network || {};
    const assetsCapable = Boolean(network.assetsOtaSupported || network.assets_ota_supported);
    const [releaseResult, firmwareResult, assetsResult] = await Promise.allSettled([
      api.get("/update/status"),
      api.get("/firmware/status"),
      assetsCapable ? api.get("/assets/status") : Promise.resolve(null),
    ]);
    if (!isCurrent()) return;
    if (firmwareResult.status === "rejected") throw firmwareResult.reason;
    const release = releaseResult.status === "fulfilled" ? releaseResult.value : null;
    const firmware = firmwareResult.value;
    const assets = assetsResult.status === "fulfilled" ? assetsResult.value : null;
    const showManualUpdates = release?.configured !== true;
    const stateLabels = {
      idle: "当前没有进行中的更新",
      staged: "新版本已准备好",
      queued: "正在发送更新任务",
      accepted: "小栈已接受更新",
      downloading: "正在下载更新",
      verifying: "正在校验更新",
      rebooting: "正在重启小栈",
      completed: "最近一次更新已完成",
      failed: "最近一次更新失败",
    };
    const activeStates = new Set(["queued", "accepted", "downloading", "verifying", "rebooting"]);
    body.innerHTML = `
      <section id="releaseUpdateCard" class="settings-card update-overview">
        <div class="settings-card-heading"><div><p class="settings-eyebrow">统一更新</p><h2 id="releaseVersion"></h2><p id="releaseMessage" class="settings-note"></p></div><span id="releaseState" class="settings-state"></span></div>
        <div id="releaseComponentList" class="release-component-list"></div>
        <div class="settings-actions"><button id="releaseCheckButton" class="secondary-action" type="button">检查更新</button><button id="releasePrepareButton" class="primary-action" type="button">准备全部更新</button></div>
      </section>
      <section id="firmwareUpdateCard" class="settings-card update-component" ${showManualUpdates ? "" : "hidden"}></section>
      <section id="assetsUpdateCard" class="settings-card update-component" ${showManualUpdates ? "" : "hidden"}></section>
      <p class="settings-callout settings-callout-safe">更新期间请保持小栈供电和网络稳定，完成后会自动重启并重新连接。</p>`;

    const componentLabels = {
      computer: "电脑组件",
      mobile: "手机界面",
      firmware: "小栈软件",
      assets: "屏幕资源",
    };
    const releaseVersion = document.querySelector("#releaseVersion");
    const releaseMessage = document.querySelector("#releaseMessage");
    const releaseState = document.querySelector("#releaseState");
    const releaseComponentList = document.querySelector("#releaseComponentList");
    const releaseCheckButton = document.querySelector("#releaseCheckButton");
    const releasePrepareButton = document.querySelector("#releasePrepareButton");
    const releaseStateLabels = {
      unavailable: "暂无更新",
      idle: "可以检查",
      checking: "检查中",
      available: "有可用更新",
      downloading: "准备中",
      staged: "已准备",
      installing: "更新中",
      completed: "已完成",
      failed: "需要重试",
      rolling_back: "正在恢复",
      rolled_back: "已恢复",
    };
    releaseVersion.textContent = release?.release_version ? `StackChan ${release.release_version}` : "StackChan Companion";
    releaseMessage.textContent = release?.message || "可用更新会集中显示在这里";
    releaseState.textContent = releaseStateLabels[release?.state] || "等待检查";
    releaseState.dataset.tone = ["available", "staged", "completed"].includes(release?.state) ? "success" : "";
    Object.entries(componentLabels).forEach(([name, label]) => {
      const item = release?.components?.[name] || {};
      const row = document.createElement("div");
      row.className = "release-component-row";
      const copy = document.createElement("span");
      const title = document.createElement("strong");
      const version = document.createElement("small");
      const badge = document.createElement("span");
      title.textContent = label;
      version.textContent = item.target_version
        ? `${displayValue(item.current_version)} → ${item.target_version}`
        : displayValue(item.current_version, "等待检查");
      badge.className = "settings-state";
      badge.textContent = releaseStateLabels[item.state] || "等待检查";
      copy.append(title, version);
      row.append(copy, badge);
      releaseComponentList.append(row);
    });
    releaseCheckButton.addEventListener("click", async () => {
      releaseCheckButton.disabled = true;
      releaseCheckButton.textContent = "正在检查…";
      setDetailStatus("正在检查可用更新…");
      try {
        await api.post("/update/check", {});
        await renderActiveRoute();
      } catch (error) {
        setDetailError(error);
        releaseCheckButton.disabled = false;
        releaseCheckButton.textContent = "重新检查";
      }
    });
    let releaseArmed = false;
    const releaseAction = release?.state === "available" ? "prepare" : release?.state === "staged" ? "install" : null;
    const releaseActionLabel = releaseAction === "install" ? "安装全部更新" : "准备全部更新";
    releasePrepareButton.disabled = !releaseAction || !release?.release_id;
    releasePrepareButton.textContent = release?.state === "staged" ? "安装全部更新" : releaseActionLabel;
    releasePrepareButton.addEventListener("click", async () => {
      if (releasePrepareButton.disabled && !releaseArmed) return;
      if (!releaseArmed) {
        releaseArmed = true;
        releasePrepareButton.disabled = false;
        releasePrepareButton.textContent = "再次点击确认";
        setDetailStatus(releaseAction === "install" ? "再次点击确认安装全部更新" : "再次点击确认准备全部更新", "error");
        window.setTimeout(() => {
          releaseArmed = false;
          if (isCurrent()) {
            releasePrepareButton.textContent = releaseActionLabel;
            releasePrepareButton.disabled = false;
          }
        }, 8000);
        return;
      }
      releaseArmed = false;
      releasePrepareButton.disabled = true;
      releasePrepareButton.textContent = releaseAction === "install" ? "正在开始更新…" : "正在准备…";
      try {
        if (releaseAction === "install") {
          await api.post("/update/install", { release_id: release.release_id }, {
            headers: { "X-StackChan-Confirm": "install-release" },
            timeout: 20000,
          });
          setDetailStatus("更新已开始，请保持小栈供电和网络稳定", "success");
          startFirmwareRefresh("queued");
        } else {
          await api.post("/update/prepare", { release_id: release.release_id }, {
            headers: { "X-StackChan-Confirm": "prepare-release" },
            timeout: 120000,
          });
        }
        await renderActiveRoute();
      } catch (error) {
        setDetailError(error);
        releasePrepareButton.disabled = false;
        releasePrepareButton.textContent = releaseAction === "install" ? "重新安装" : "重新准备";
      }
    });

    function renderComponentCard(container, label, response, unavailableText) {
      const update = response?.update || {};
      const device = response?.device || {};
      const artifact = response?.artifact || null;
      const currentVersion = response ? displayValue(device.current_version, "版本未上报") : "等待小栈支持";
      const sameVersion = Boolean(artifact?.version && artifact.version === currentVersion);
      const active = activeStates.has(update.state);
      const progress = Math.max(0, Math.min(100, Number(update.progress) || 0));
      const installAvailable = Boolean(artifact?.id && device.connected && device.ota_supported !== false && !sameVersion && !active);
      container.innerHTML = `
        <div class="settings-card-heading"><div><p class="settings-eyebrow">${label}</p><h2></h2><p class="settings-note"></p></div></div>
        <div class="firmware-progress" ${active || update.state === "completed" ? "" : "hidden"}><progress max="100" value="${progress}" aria-label="${label}更新进度"></progress><span>${Math.round(progress)}%</span></div>
        <div class="update-meta"></div>
        <button class="secondary-action firmware-install" type="button"></button>`;
      container.querySelector("h2").textContent = currentVersion;
      container.querySelector(".settings-note").textContent = response
        ? stateLabels[update.state] || displayValue(update.message, "更新状态未上报")
        : unavailableText;
      if (response) {
        appendInfoList(container.querySelector(".update-meta"), artifact ? [
          ["可用版本", artifact.version],
          ["大小", artifact.size ? `${new Intl.NumberFormat("zh-CN").format(artifact.size)} 字节` : "未上报"],
        ] : [["可用版本", "暂无更新"]]);
      }
      const button = container.querySelector("button");
      button.textContent = active ? "正在更新" : sameVersion ? "已是当前版本" : artifact ? "安装更新" : "暂无可用更新";
      button.disabled = !installAvailable;
      button.hidden = !response;
      return { artifact, button, installAvailable, update };
    }

    const firmwareControl = renderComponentCard(
      document.querySelector("#firmwareUpdateCard"),
      "小栈软件",
      firmware,
      "暂时无法读取",
    );
    const assetsControl = renderComponentCard(
      document.querySelector("#assetsUpdateCard"),
      "屏幕资源",
      assets,
      "暂未启用；完成小栈软件更新后即可使用",
    );

    function bindInstall(control, install) {
      const { artifact, button, installAvailable } = control;
      let armed = false;
      let armTimer = null;
      button.addEventListener("click", async () => {
        if (!installAvailable || button.disabled && !armed) return;
        if (!armed) {
          armed = true;
          button.disabled = false;
          button.textContent = "再次点击安装";
          setDetailStatus("再次点击确认安装；更新期间请勿断电", "error");
          armTimer = window.setTimeout(() => {
            armed = false;
            button.textContent = "安装更新";
            setDetailStatus("");
          }, 8000);
          return;
        }
        armed = false;
        window.clearTimeout(armTimer);
        button.disabled = true;
        button.textContent = "正在开始更新…";
        setDetailStatus("正在开始更新…");
        try {
          const result = await install(artifact.id);
          if (result.ok !== true) throw new Error("更新任务未被接受");
          setDetailStatus("更新已开始，请保持小栈供电稳定", "success");
          startFirmwareRefresh(result.update?.state || "queued");
        } catch (error) {
          button.disabled = false;
          button.textContent = "重新安装";
          setDetailError(error);
        }
      });
    }

    bindInstall(firmwareControl, (artifactId) => api.post("/firmware/install", { artifact_id: artifactId, route: "auto" }, {
      headers: { "X-StackChan-Confirm": "install-firmware" },
      timeout: 20000,
    }));
    bindInstall(assetsControl, (artifactId) => api.post("/assets/install", { artifact_id: artifactId, route: "auto" }, {
      headers: { "X-StackChan-Confirm": "install-assets" },
      timeout: 20000,
    }));
    const failed = [firmwareControl, assetsControl].find((item) => item.update.state === "failed");
    setDetailStatus(failed ? displayValue(failed.update.error, "更新失败，请稍后重试") : "", failed ? "error" : "");
    const active = [firmwareControl, assetsControl].find((item) => activeStates.has(item.update.state));
    startFirmwareRefresh(release?.state === "installing" ? "queued" : active?.update.state || "idle");
  }

  async function renderCamera(isCurrent) {
    const [device, experience] = await Promise.all([
      api.get("/device/status"),
      api.get("/experience"),
    ]);
    if (!isCurrent()) return;
    confirmedExperience = experience;
    const camera = device.camera || {};
    const cameraEnabled = experience.privacy?.camera_enabled === true;
    body.innerHTML = `
      <section class="settings-card">
        <div class="settings-switch-row"><div><strong>允许使用摄像头</strong><small>关闭后不应声称看到画面</small></div><button id="cameraPrivacySwitch" type="button" class="settings-switch" role="switch" aria-label="允许使用摄像头"></button></div>
      </section>
      <section class="settings-card">
        <div class="settings-card-heading"><div><h2>本地实时预览</h2><p id="cameraSummary"></p></div></div>
        <div class="camera-preview"><div id="cameraPlaceholder">预览未开启</div><img id="cameraImage" alt="小栈摄像头本地实时画面" width="720" height="405" hidden></div>
        <div class="settings-actions"><button id="cameraStartButton" class="secondary-action" type="button" data-requires-device>开始预览</button><button id="cameraStopButton" class="secondary-action" type="button" data-requires-device>停止预览</button></div>
      </section>
      <p class="settings-callout settings-callout-safe">实时画面仅在当前已配对设备中查看。</p>`;
    const privacySwitch = document.querySelector("#cameraPrivacySwitch");
    const summary = document.querySelector("#cameraSummary");
    const image = document.querySelector("#cameraImage");
    const placeholder = document.querySelector("#cameraPlaceholder");
    const startButton = document.querySelector("#cameraStartButton");
    const stopButton = document.querySelector("#cameraStopButton");
    let previewActive = camera.streaming && camera.available;
    const hidePreview = () => {
      stopCameraRefresh();
      image.hidden = true;
      image.removeAttribute("src");
      placeholder.hidden = false;
    };
    const refreshFrame = () => {
      if (!isCurrent() || !previewActive || document.visibilityState !== "visible") return;
      image.src = `/mobile-api/device/camera/latest.jpg?t=${Date.now()}`;
    };
    image.addEventListener("load", () => {
      if (!previewActive) return;
      image.hidden = false;
      placeholder.hidden = true;
    });
    image.addEventListener("error", () => {
      image.hidden = true;
      placeholder.hidden = false;
      placeholder.textContent = "画面暂时不可用，正在重试";
      setDetailStatus("摄像头画面读取失败，正在自动重试", "error");
    });
    function startCameraRefresh() {
      stopCameraRefresh();
      refreshFrame();
      cameraRefreshTimer = window.setInterval(refreshFrame, 800);
    }
    setSwitch(privacySwitch, cameraEnabled);
    summary.textContent = camera.available ? (camera.streaming ? "小栈正在发送本地画面" : "摄像头可用，当前未预览") : "摄像头状态未上报";
    const canPreview = device.connected && cameraEnabled;
    startButton.disabled = !canPreview;
    stopButton.disabled = !device.connected;
    if (previewActive && cameraEnabled) {
      image.hidden = false;
      placeholder.hidden = true;
      startCameraRefresh();
    } else if (previewActive) {
      previewActive = false;
      hidePreview();
    }
    privacySwitch.addEventListener("click", async () => {
      const previousValue = privacySwitch.getAttribute("aria-checked") === "true";
      const nextValue = !previousValue;
      setSwitch(privacySwitch, nextValue);
      privacySwitch.disabled = true;
      try {
        if (!nextValue && previewActive) {
          const stopResponse = await api.post("/device/camera-preview/stop", {});
          if (stopResponse.ok === false) throw new Error("小栈未停止摄像头预览");
          previewActive = false;
          hidePreview();
        }
        const response = await api.post("/experience", { privacy: { camera_enabled: nextValue } });
        confirmedExperience = response;
        setDetailStatus("摄像头隐私设置已确认", "success");
        renderActiveRoute();
      } catch (error) {
        setSwitch(privacySwitch, previousValue);
        setDetailError(error);
      } finally {
        privacySwitch.disabled = false;
      }
    });
    startButton.addEventListener("click", async () => {
      startButton.dataset.uiBusy = "true";
      startButton.disabled = true;
      setDetailStatus("正在启动本地预览…");
      try {
        const response = await api.post("/device/camera-preview/start", { quality: 72 });
        if (response.ok === false) throw new Error("小栈未启动摄像头预览");
        previewActive = true;
        image.hidden = true;
        placeholder.hidden = false;
        placeholder.textContent = "正在读取画面…";
        startCameraRefresh();
        setDetailStatus("小栈已接受预览指令", "success");
      } catch (error) {
        setDetailError(error);
      } finally {
        startButton.dataset.uiBusy = "false";
        syncDetailConnection();
      }
    });
    stopButton.addEventListener("click", async () => {
      stopButton.dataset.uiBusy = "true";
      stopButton.disabled = true;
      setDetailStatus("正在停止预览…");
      try {
        const response = await api.post("/device/camera-preview/stop", {});
        if (response.ok === false) throw new Error("小栈未停止摄像头预览");
        previewActive = false;
        hidePreview();
        setDetailStatus("本地预览已停止", "success");
      } catch (error) {
        setDetailError(error);
      } finally {
        stopButton.dataset.uiBusy = "false";
        syncDetailConnection();
      }
    });
    setDetailStatus("");
  }

  function appendMemoryGroups(container, memory) {
    const populatedGroups = Object.entries(MEMORY_LABELS).filter(
      ([key]) => Array.isArray(memory[key]) && memory[key].length > 0,
    );
    if (!populatedGroups.length) {
      const empty = document.createElement("p");
      empty.className = "settings-empty";
      empty.textContent = "目前还没有可管理的记忆";
      container.append(empty);
      return;
    }
    populatedGroups.forEach(([key, label]) => {
      const values = memory[key];
      const section = document.createElement("details");
      section.className = "memory-disclosure";
      const heading = document.createElement("summary");
      heading.className = "memory-group-heading";
      const title = document.createElement("h3");
      title.textContent = label;
      const count = document.createElement("span");
      count.textContent = `${values.length} 条`;
      heading.append(title, count);
      section.append(heading);
      const list = document.createElement("div");
      list.className = "memory-list";
      values.forEach((value) => {
        const row = document.createElement("div");
        row.className = "memory-item";
        const copy = document.createElement("span");
        copy.textContent = value;
        const remove = document.createElement("button");
        remove.type = "button";
        remove.className = "memory-remove";
        remove.textContent = "删除";
        remove.setAttribute("aria-label", `删除${label}：${value}`);
        remove.addEventListener("click", async () => {
          remove.disabled = true;
          try {
            const response = await api.post("/memory/remove", { key, value });
            if (response.changed === false) throw new Error("这条记忆已经不存在");
            setDetailStatus("记忆已删除", "success");
            renderActiveRoute();
          } catch (error) {
            remove.disabled = false;
            setDetailError(error);
          }
        });
        row.append(copy, remove);
        list.append(row);
      });
      section.append(list);
      const clear = document.createElement("button");
      clear.type = "button";
      clear.className = "memory-clear";
      clear.textContent = `清空“${label}”`;
      let clearArmed = false;
      let clearTimer = null;
      clear.addEventListener("click", async () => {
        if (!clearArmed) {
          clearArmed = true;
          clear.textContent = "再次点击清空";
          setDetailStatus(`再次点击确认清空“${label}”`, "error");
          clearTimer = window.setTimeout(() => {
            clearArmed = false;
            clear.textContent = `清空“${label}”`;
            setDetailStatus("");
          }, 8000);
          return;
        }
        clearArmed = false;
        window.clearTimeout(clearTimer);
        clear.disabled = true;
        try {
          const response = await api.post("/memory/clear", { key }, { headers: { "X-StackChan-Confirm": "clear-memory" } });
          if (response.changed === false) throw new Error("这一类记忆已经是空的");
          setDetailStatus("这一类记忆已清空", "success");
          renderActiveRoute();
        } catch (error) {
          clear.disabled = false;
          setDetailError(error);
        }
      });
      section.append(clear);
      container.append(section);
    });
  }

  async function renderMemory(isCurrent) {
    const [experience, memory] = await Promise.all([
      api.get("/experience"),
      api.get("/memory"),
    ]);
    if (!isCurrent()) return;
    confirmedExperience = experience;
    const privacy = experience.privacy || {};
    body.innerHTML = `
      <section class="settings-card">
        <div class="settings-switch-list">
          <div class="settings-switch-row"><div><strong>记住重要的事</strong><small>允许写入新的长期记忆</small></div><button type="button" class="settings-switch" role="switch" aria-label="记忆功能" data-privacy-key="memory_enabled"></button></div>
          <div class="settings-switch-row"><div><strong>使用最近对话</strong><small>允许回答参考最近聊天上下文</small></div><button type="button" class="settings-switch" role="switch" aria-label="最近对话上下文" data-privacy-key="chat_history_enabled"></button></div>
        </div>
      </section>
      <section class="settings-card"><div class="settings-card-heading"><div><h2>记忆内容</h2><p>按分类查看和管理</p></div></div><div id="memoryGroups"></div></section>`;
    body.querySelectorAll("[data-privacy-key]").forEach((button) => {
      const key = button.dataset.privacyKey;
      setSwitch(button, privacy[key] === true);
      button.addEventListener("click", () => updateExperienceToggle(button, "privacy", key));
    });
    appendMemoryGroups(document.querySelector("#memoryGroups"), memory);
    setDetailStatus("");
  }

  function renderHelp() {
    body.innerHTML = `
      <section class="settings-card help-list">
        <details open><summary>首页怎么使用？</summary><p>首页显示小栈的连接、陪伴画面与当前状态。未获取到的内容会显示“未上报”。</p></details>
        <details><summary>遥控为什么需要小栈在线？</summary><p>3D 模型可以在手机上观察，头部摇杆、俯仰和速度只有在设备连接后才会发送。</p></details>
        <details><summary>怎么测试小栈？</summary><p>在“测试”页逐项检查动作、屏幕亮度、扬声器音量和设备内置测试音；只有收到小栈确认后才会显示成功。</p></details>
        <details><summary>没有数据线怎么更新？</summary><p>打开底部“更新”页检查签名版本，先准备更新，再次确认后安装；过程中保持小栈供电并留在同一网络。</p></details>
        <details><summary>设置没有读到数值怎么办？</summary><p>先确认小栈已经连接。仍未上报的能力会保持只读或禁用，避免写入假状态。</p></details>
      </section>
      <p class="settings-callout">手机和小栈需使用可信的同一网络；不要转发首次配对链接。</p>`;
    setDetailStatus("");
  }

  function renderAbout() {
    body.innerHTML = `
      <section class="settings-card about-card">
        <img src="./assets/settings-robot.webp?v=6" alt="小栈机器人" width="615" height="525" loading="lazy">
        <p class="settings-eyebrow">StackChan Companion</p>
        <h2>小栈</h2>
        <p>蒋磊为依婵制作的小栈陪伴应用。</p>
      </section>
      <section class="settings-card"><h2>版本说明</h2><p class="settings-note">StackChan Companion 2.0.0</p><p class="settings-note">手机界面和小栈软件均可在底部“更新”页面查看。</p></section>
      <footer class="about-signature"><strong>Made with care for Yichan by Jianglei</strong><span>© 2026 Jiang Lei</span></footer>`;
    setDetailStatus("");
  }

  const routeRenderers = {
    device: renderDevice,
    companion: renderCompanion,
    voice: renderVoice,
    "auto-response": renderAutoResponse,
    network: renderNetwork,
    display: renderDisplay,
    memory: renderMemory,
    help: renderHelp,
    about: renderAbout,
  };

  async function renderActiveRoute() {
    const route = activeRoute;
    const renderer = routeRenderers[route];
    if (!renderer) return;
    stopCameraRefresh();
    stopFirmwareRefresh();
    const generation = ++renderGeneration;
    configureSave();
    setDetailStatus(`正在读取${TITLES[route]}…`);
    body.innerHTML = `<section class="settings-placeholder" aria-busy="true"><p>正在读取${TITLES[route]}…</p></section>`;
    try {
      const isCurrent = makeCurrentCheck(route, generation);
      if (!["help", "about"].includes(route) && !(await api.isPaired())) {
        if (!isCurrent()) return;
        detailSync.dataset.state = "error";
        detailSync.textContent = "需要先完成手机配对";
        body.innerHTML = `<section class="settings-card"><h2>先完成手机配对</h2><p class="settings-note">配对后即可在这里查看和调整小栈。</p></section>`;
        setDetailStatus("");
        return;
      }
      await renderer(isCurrent);
      syncDetailConnection();
    } catch (error) {
      if (!makeCurrentCheck(route, generation)()) return;
      body.innerHTML = `<section class="settings-placeholder"><p>这部分暂时没有读取成功。</p><button id="settingsRetryButton" class="secondary-action" type="button">重新读取</button></section>`;
      document.querySelector("#settingsRetryButton").addEventListener("click", renderActiveRoute);
      setDetailError(error);
    }
  }

  function openSettingsRoute(route, anchor = null, updateHistory = true) {
    if (!TITLES[route]) return;
    settingsScroll = window.scrollY;
    returnTarget = anchor;
    activeRoute = route;
    activateSettings();
    title.textContent = TITLES[route];
    detailSync.hidden = route === "help" || route === "about";
    setDetailOpen(true);
    syncDetailConnection();
    window.scrollTo({ top: 0 });
    window.requestAnimationFrame(() => title.focus({ preventScroll: true }));
    if (updateHistory) {
      history.pushState(null, "", `#settings/${route}`);
      canPopHistory = true;
    }
    renderActiveRoute();
  }

  function closeSettingsRoute(updateHistory = true, showSettings = true) {
    if (!activeRoute) return;
    activeRoute = null;
    renderGeneration += 1;
    stopCameraRefresh();
    stopFirmwareRefresh();
    configureSave();
    setDetailOpen(false);
    if (showSettings) activateSettings();
    if (updateHistory) history.replaceState(null, "", "#settings");
    window.requestAnimationFrame(() => {
      window.scrollTo({ top: settingsScroll });
      returnTarget?.focus();
    });
    canPopHistory = false;
  }

  document.querySelectorAll("[data-settings-route]").forEach((anchor) => {
    anchor.addEventListener("click", () => openSettingsRoute(anchor.dataset.settingsRoute, anchor));
  });
  backButton.addEventListener("click", () => {
    if (canPopHistory) history.back();
    else closeSettingsRoute();
  });
  window.addEventListener("hashchange", () => {
    const match = window.location.hash.match(/^#settings\/([a-z-]+)$/);
    if (match) openSettingsRoute(match[1], null, false);
    else if (activeRoute) closeSettingsRoute(false, window.location.hash === "#settings");
  });
  window.addEventListener("stackchandevicestatus", (event) => syncDetailConnection(event.detail));

  const initialRoute = window.location.hash.match(/^#settings\/([a-z-]+)$/)?.[1];
  if (initialRoute) openSettingsRoute(initialRoute, null, false);

  return { openSettingsRoute, closeSettingsRoute };
}
