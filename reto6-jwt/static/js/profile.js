// Carga los datos de la cuenta y gestiona edición + la acción admin.
// Nota: el 'role' NO llega aquí; si lo quieres saber, decodifica el JWT de la cookie.

async function loadMe() {
  try {
    const res = await fetch("/profile/api/me");
    if (res.status === 401) {
      window.location.href = "/profile/";
      return;
    }
    const data = await res.json();
    document.getElementById("v-usuario").textContent = data.usuario || "—";
    document.getElementById("avatar").textContent = (data.usuario || "?").charAt(0);
    document.getElementById("v-email").textContent = data.email || "(sin email)";
    document.getElementById("email").value = data.email || "";
  } catch (e) {
    window.location.href = "/profile/";
  }
}

document.getElementById("edit-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const msg = document.getElementById("edit-msg");
  msg.textContent = "";
  msg.className = "msg";
  const email = document.getElementById("email").value;
  const password = document.getElementById("password").value;
  try {
    const res = await fetch("/profile/api/profile", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password: password || null }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      msg.textContent = data.detail || "No se pudo guardar.";
      msg.className = "msg error";
      return;
    }
    msg.textContent = "Datos actualizados.";
    msg.className = "msg success";
    document.getElementById("password").value = "";
    loadMe();
  } catch (err) {
    msg.textContent = "No se pudo contactar con el servidor.";
    msg.className = "msg error";
  }
});

// La acción admin: interceptamos el submit para mostrar la respuesta inline
// (incluido el 403 explícito o, si el token es admin, la flag).
document.getElementById("admin-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const box = document.getElementById("admin-result");
  box.textContent = "";
  box.className = "";
  try {
    const res = await fetch("/profile/admin/export", { method: "POST" });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      box.textContent = JSON.stringify(data, null, 2);
      box.className = "result bad";
      return;
    }
    box.textContent = JSON.stringify(data, null, 2);
    box.className = "result ok";
  } catch (err) {
    box.textContent = "No se pudo contactar con el servidor.";
    box.className = "result bad";
  }
});

document.getElementById("logout-btn").addEventListener("click", async () => {
  await fetch("/profile/api/logout", { method: "POST" }).catch(() => {});
  window.location.href = "/profile/";
});

loadMe();
