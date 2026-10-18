const form = document.getElementById("login-form");
const msgEl = document.getElementById("msg");
const flagBox = document.getElementById("flag-box");

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  msgEl.textContent = "";
  msgEl.className = "msg";
  flagBox.style.display = "none";

  const username = document.getElementById("username").value;
  const password = document.getElementById("password").value;

  const turnstileToken = new FormData(form).get("cf-turnstile-response") || "";

  const submitBtn = form.querySelector("button[type=submit]");
  submitBtn.disabled = true;

  try {
    const res = await fetch("/admin/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password, turnstile_token: turnstileToken }),
    });

    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      msgEl.textContent = data.detail || "No se pudo iniciar sesión. Inténtalo de nuevo.";
      msgEl.className = "msg error";
      return;
    }

    if (data.success) {
      msgEl.textContent = "¡Acceso correcto!";
      msgEl.className = "msg success";
      flagBox.textContent = data.flag;
      flagBox.style.display = "block";
    } else {
      msgEl.textContent = "Usuario o contraseña incorrectos.";
      msgEl.className = "msg error";
    }
  } catch (err) {
    msgEl.textContent = "No se pudo contactar con el servidor. Inténtalo de nuevo.";
    msgEl.className = "msg error";
  } finally {
    submitBtn.disabled = false;
    if (window.turnstile) turnstile.reset();
  }
});
