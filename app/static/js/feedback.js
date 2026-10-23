// Feedback page: send a message, show the reply. The thread is kept for this tab only.
(function () {
  const form = document.getElementById("feedback-form");
  const text = document.getElementById("feedback-text");
  const send = document.getElementById("send");
  const counter = document.getElementById("counter");
  const errorBox = document.getElementById("form-error");
  const thread = document.getElementById("thread");
  const KEY = "cirrus.feedbackThread";
  const TAG_NAMES = { query: "Question", suggestion: "Suggestion", bug: "Bug report", junk: "Unclear" };

  function load() {
    try {
      return JSON.parse(sessionStorage.getItem(KEY)) || [];
    } catch (e) {
      return [];
    }
  }

  function save(items) {
    try {
      sessionStorage.setItem(KEY, JSON.stringify(items));
    } catch (e) { /* ignore */ }
  }

  function bubble(item) {
    const user = document.createElement("li");
    user.className = "bubble user";
    user.textContent = item.text;

    const bot = document.createElement("li");
    bot.className = "bubble bot";
    const tag = document.createElement("span");
    tag.className = `tag ${item.label || "none"}`;
    tag.textContent = TAG_NAMES[item.label] || "Received";
    const body = document.createElement("div");
    body.textContent = item.reply;
    bot.append(tag, body);
    thread.prepend(user, bot);
  }

  const items = load();
  items.forEach(bubble);

  text.addEventListener("input", () => {
    counter.textContent = `${text.value.length} / 2000`;
    errorBox.textContent = "";
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const value = text.value.trim();
    if (!value) return;
    send.disabled = true;
    errorBox.textContent = "";
    try {
      const resp = await fetch("/api/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: value }),
      });
      const data = await resp.json();
      if (!resp.ok) {
        errorBox.textContent = data.error || "Something went wrong, please try again.";
        return;
      }
      const item = { text: value, reply: data.reply, label: data.label };
      items.push(item);
      save(items);
      bubble(item);
      text.value = "";
      counter.textContent = "0 / 2000";
    } catch (err) {
      errorBox.textContent = "Couldn't reach the server. Check your connection and try again.";
    } finally {
      send.disabled = false;
    }
  });
})();
