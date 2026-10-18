const chatWindow = document.getElementById("chat-window");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const chatMsg = document.getElementById("chat-msg");
const resetBtn = document.getElementById("reset-btn");

function addBubble(text, role) {
  const bubble = document.createElement("div");
  bubble.className = `bubble ${role}`;
  bubble.textContent = text;
  chatWindow.appendChild(bubble);
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = chatInput.value.trim();
  if (!message) return;

  chatMsg.textContent = "";
  addBubble(message, "user");
  chatInput.value = "";

  const sendBtn = chatForm.querySelector("button[type=submit]");
  sendBtn.disabled = true;

  try {
    const res = await fetch("/admin/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });

    const data = await res.json().catch(() => null);

    if (!data || !data.reply) {
      chatMsg.textContent = "No se pudo contactar con el servidor. Inténtalo de nuevo.";
      return;
    }

    addBubble(data.reply, "bot");
  } catch (err) {
    chatMsg.textContent = "No se pudo contactar con el servidor. Inténtalo de nuevo.";
  } finally {
    sendBtn.disabled = false;
  }
});

resetBtn.addEventListener("click", async () => {
  await fetch("/admin/api/chat/reset", { method: "POST" }).catch(() => {});
  chatWindow.innerHTML = "";
  addBubble("Conversación reiniciada. ¿En qué puedo ayudarte?", "bot");
});

chatInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    chatForm.requestSubmit();
  }
});
