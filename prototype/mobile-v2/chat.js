// mobile-v2 聊天模块：底部抽屉 + 输入 + 思考/错误态 + 快捷提问。
import { api } from "./api.js";

function cleanReply(payload) {
  const reply = typeof payload?.say === "string" ? payload.say.trim() : "";
  if (!reply) throw new Error("小栈这次没有返回内容，请再试一次。");
  return reply;
}

export function createChatController({ onThinkingChanged }) {
  const fab = document.querySelector("#chatFab");
  const backdrop = document.querySelector("#chatBackdrop");
  const sheet = document.querySelector("#chatSheet");
  const form = document.querySelector("#chatComposer");
  const input = document.querySelector("#chatMessageInput");
  const sendButton = document.querySelector("#chatSendButton");
  const log = document.querySelector("#chatLog");
  const empty = document.querySelector("#chatEmpty");
  const feedback = document.querySelector("#chatFeedback");
  const modelState = document.querySelector("#chatModelState");

  let pending = false;

  function open() {
    sheet.classList.add("is-open");
    sheet.setAttribute("aria-hidden", "false");
    fab.classList.add("is-open");
    fab.setAttribute("aria-expanded", "true");
    backdrop.hidden = false;
    input.focus({ preventScroll: true });
  }
  function close() {
    sheet.classList.remove("is-open");
    sheet.setAttribute("aria-hidden", "true");
    fab.classList.remove("is-open");
    fab.setAttribute("aria-expanded", "false");
    backdrop.hidden = true;
  }
  function scrollToLatest() {
    log.scrollTo({ top: log.scrollHeight, behavior: "smooth" });
  }
  function appendMessage(role, message) {
    if (empty) empty.style.display = "none";
    const bubble = document.createElement("article");
    bubble.className = `chat-bubble ${role}`;
    const body = document.createElement("p");
    body.textContent = message;
    bubble.append(body);
    log.append(bubble);
    scrollToLatest();
    return bubble;
  }
  function setPending(next) {
    pending = next;
    form.setAttribute("aria-busy", String(next));
    input.disabled = next;
    sendButton.disabled = next;
    modelState.textContent = next ? "认真想想…" : "智能模式";
    onThinkingChanged?.(next);
  }
  async function sendMessage(raw) {
    const content = typeof raw === "string" ? raw.trim() : "";
    if (!content || pending) return;
    appendMessage("user", content);
    input.value = "";
    feedback.textContent = "";
    setPending(true);
    const thinking = appendMessage("assistant pending", "正在认真想…");
    try {
      const payload = await api.post("/chat", { message: content }, { timeout: 45000 });
      thinking.remove();
      appendMessage("assistant", cleanReply(payload));
      modelState.textContent = payload.model ? "已认真回答" : "智能模式";
    } catch (error) {
      thinking.remove();
      feedback.textContent = error?.message || "暂时没能联系到小栈，请稍后再试。";
      appendMessage("assistant error", "刚才的连接没有成功，消息还在这里，你可以再试一次。");
    } finally {
      setPending(false);
      input.focus({ preventScroll: true });
    }
  }

  fab.addEventListener("click", () => (sheet.getAttribute("aria-hidden") === "true" ? open() : close()));
  backdrop.addEventListener("click", close);
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    sendMessage(input.value);
  });
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      form.requestSubmit();
    }
  });
  document.querySelectorAll("[data-chat-prompt]").forEach((button) => {
    button.addEventListener("click", () => sendMessage(button.dataset.chatPrompt || ""));
  });

  return { open, close, sendMessage };
}