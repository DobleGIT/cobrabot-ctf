// Registro / login. Al autenticarse, el servidor pone el JWT en una cookie.
let mode = "login";

function setMode(m) {
  mode = m;
  document.getElementById("tab-login").classList.toggle("active", m === "login");
  document.getElementById("tab-register").classList.toggle("active", m === "register");
  document.getElementById("email-field").style.display = m === "register" ? "block" : "none";
  document.getElementById("submit-btn").textContent = m === "register" ? "Crear cuenta" : "Entrar";
}

document.getElementById("tab-login").addEventListener("click", () => setMode("login"));
document.getElementById("tab-register").addEventListener("click", () => setMode("register"));

document.getElementById("auth-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const msg = document.getElementById("msg");
  msg.textContent = "";
  msg.className = "msg";
  const usuario = document.getElementById("usuario").value;
  const password = document.getElementById("password").value;
  const email = document.getElementById("email").value;
  const path = mode === "register" ? "/profile/api/register" : "/profile/api/login";
  const body = mode === "register" ? { usuario, email, password } : { usuario, password };
  try {
    const res = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      msg.textContent = data.detail || "No se pudo completar la operación.";
      msg.className = "msg error";
      return;
    }
    window.location.href = "/profile/cuenta";
  } catch (err) {
    msg.textContent = "No se pudo contactar con el servidor.";
    msg.className = "msg error";
  }
});

setMode("login");
