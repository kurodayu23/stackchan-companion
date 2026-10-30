// 只接受非空说话文本；HTTP 成功但没有内容时仍按无效回复处理。
function cleanReply(payload) {
  const reply = typeof payload?.say === "string" ? payload.say.trim() : "";
  if (!reply) throw new Error("小栈这次没有返回内容，请再试一次。");
  return reply;
}

// 把聊天界面事件与 API 连接起来，内部闭包保存本页面的发送状态。
export function createChatController({ api }) {
  const form = document.querySelector("#chatComposer");
  const input = document.querySelector("#chatMessageInput");
  const sendButton = document.querySelector("#chatSendButton");
  const log = document.querySelector("#chatLog");
  const feedback = document.querySelector("#chatFeedback");
  const modelState = document.querySelector("#chatModelState");
  if (!form || !input || !sendButton || !log || !feedback || !modelState) return;

  let pending = false;

  function scrollToLatest() {
    const reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    log.scrollTo({ top: log.scrollHeight, behavior: reducedMotion ? "auto" : "smooth" });
  }

  // 通过 textContent 写入消息正文，用户或模型内容不会被解释为 HTML 标签。
  function appendMessage(role, message) {
    const bubble = document.createElement("article");
    bubble.className = `chat-bubble ${role}`;
    const label = document.createElement("span");
    label.textContent = role === "user" ? "你" : "小栈";
    const body = document.createElement("p");
    body.textContent = message;
    bubble.append(label, body);
    log.append(bubble);
    scrollToLatest();
    return bubble;
  }

  // 请求期间禁用输入和发送，防止重复提交，并同步无障碍忙碌状态。
  function setPending(next) {
    pending = next;
    form.setAttribute("aria-busy", String(next));
    input.disabled = next;
    sendButton.disabled = next;
    modelState.textContent = next ? "认真想想…" : "智能模式";
    // 小栈在思考时眯起眼睛，界面和状态是同一件事。
    document.querySelector(".chat-screen")?.classList.toggle("is-thinking", next);
  }

  // 显示用户消息与等待提示，收到结果后替换提示；finally 保证失败后也能继续输入。
  async function sendMessage(message) {
    const content = message.trim();
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

  form.addEventListener("submit", event => {
    event.preventDefault();
    sendMessage(input.value);
  });
  input.addEventListener("keydown", event => {
    // 输入法组词期间的回车不应发送消息，isComposing 用于避免误提交中文输入。
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      form.requestSubmit();
    }
  });
  document.querySelectorAll("[data-chat-prompt]").forEach(button => {
    button.addEventListener("click", () => sendMessage(button.dataset.chatPrompt || ""));
  });
}
