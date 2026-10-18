// ZumoShop — frontend de la tienda. Sin framework ni build, fetch a /home/api/*.

const euro = (n) => `${Number(n).toFixed(2).replace(".", ",")} €`;

const state = {
  user: null,
  discountPercent: 0, // porcentaje "legítimo" aplicado tras validar un código
  discountCode: "",
};

// --- helpers de red ---
async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || "Error en la petición.");
  }
  return data;
}

// --- auth ---
async function refreshMe() {
  const data = await api("/home/api/me");
  state.user = data.user;
  const text = document.getElementById("auth-text");
  const authBtn = document.getElementById("auth-btn");
  const logoutBtn = document.getElementById("logout-btn");
  if (state.user) {
    text.innerHTML = `Hola, <strong>${state.user.usuario}</strong>`;
    authBtn.style.display = "none";
    logoutBtn.style.display = "inline-block";
  } else {
    text.textContent = "No has iniciado sesión";
    authBtn.style.display = "inline-block";
    logoutBtn.style.display = "none";
    gate(); // sin sesión, obliga a registrarse / iniciar sesión
  }
  updateCheckoutButton();
}

// Mientras no haya sesión, el modal de registro es obligatorio: se abre y no se
// puede cerrar hasta que el usuario entre.
function gate() {
  setAuthMode("register");
  document.getElementById("auth-close-row").style.display = "none";
  openModal();
}

// --- catálogo ---
async function loadProducts() {
  const { products } = await api("/home/api/products");
  const grid = document.getElementById("product-grid");
  grid.innerHTML = "";
  products.forEach((p, i) => {
    const el = document.createElement("article");
    el.className = "product";
    el.dataset.cat = p.categoria;
    el.innerHTML = `
      <div class="top">
        <span class="ref">#${String(i + 1).padStart(2, "0")}</span>
        <span class="cat">${p.categoria}</span>
        <span class="emoji">${p.emoji}</span>
      </div>
      <div class="info">
        <h3 class="nombre">${p.nombre}</h3>
        <p class="desc">${p.descripcion}</p>
      </div>
      <div class="bottom">
        <span class="precio">${euro(p.precio)}</span>
        <button type="button" data-id="${p.id}">Añadir</button>
      </div>`;
    const btn = el.querySelector("button");
    btn.addEventListener("click", async () => {
      await addToCart(p.id);
      btn.classList.add("added");
      btn.textContent = "¡Añadido!";
      setTimeout(() => {
        btn.classList.remove("added");
        btn.textContent = "Añadir";
      }, 1200);
    });
    grid.appendChild(el);
  });
  renderFilters(products);
}

// Filtro por categoría (solo visual, en cliente)
function renderFilters(products) {
  const box = document.getElementById("filters");
  const cats = ["Todos", ...new Set(products.map((p) => p.categoria))];
  box.innerHTML = "";
  for (const cat of cats) {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = cat;
    if (cat === "Todos") b.classList.add("active");
    b.addEventListener("click", () => {
      box.querySelectorAll("button").forEach((x) => x.classList.toggle("active", x === b));
      document.querySelectorAll("#product-grid .product").forEach((el) => {
        el.hidden = cat !== "Todos" && el.dataset.cat !== cat;
      });
    });
    box.appendChild(b);
  }
}

// --- carrito ---
let lastCart = { items: [], subtotal: 0 };

async function loadCart() {
  lastCart = await api("/home/api/cart");
  renderCart();
}

async function addToCart(productId) {
  lastCart = await api("/home/api/cart/add", {
    method: "POST",
    body: JSON.stringify({ product_id: productId, qty: 1 }),
  });
  renderCart();
}

async function setQty(productId, qty) {
  lastCart = await api("/home/api/cart/set", {
    method: "POST",
    body: JSON.stringify({ product_id: productId, qty }),
  });
  renderCart();
}

function renderCart() {
  const box = document.getElementById("cart-items");
  box.innerHTML = "";
  document.getElementById("cart-count").textContent = lastCart.items.reduce((n, it) => n + it.qty, 0);
  if (!lastCart.items.length) {
    box.innerHTML = '<div class="cart-empty">El carrito está vacío.</div>';
  } else {
    for (const it of lastCart.items) {
      const line = document.createElement("div");
      line.className = "cart-line";
      line.innerHTML = `
        <span class="ci-name">${it.emoji} ${it.nombre}</span>
        <span class="qty-ctrl">
          <button type="button" data-act="dec">−</button>
          <span>${it.qty}</span>
          <button type="button" data-act="inc">+</button>
        </span>
        <span class="ci-line">${euro(it.linea)}</span>`;
      line.querySelector('[data-act="dec"]').addEventListener("click", () =>
        setQty(it.product_id, it.qty - 1)
      );
      line.querySelector('[data-act="inc"]').addEventListener("click", () =>
        setQty(it.product_id, it.qty + 1)
      );
      box.appendChild(line);
    }
  }
  renderTotals();
  updateCheckoutButton();
}

function renderTotals() {
  const subtotal = lastCart.subtotal || 0;
  const pct = state.discountPercent || 0;
  const disc = subtotal * (pct / 100);
  const total = Math.max(0, subtotal - disc);
  document.getElementById("t-subtotal").textContent = euro(subtotal);
  document.getElementById("t-pct").textContent = pct;
  document.getElementById("t-disc").textContent = `-${euro(disc)}`;
  document.getElementById("t-total").textContent = euro(total);
}

function updateCheckoutButton() {
  const btn = document.getElementById("checkout-btn");
  const hasItems = lastCart.items && lastCart.items.length > 0;
  btn.disabled = !hasItems;
  btn.textContent = state.user ? "Contratar servicios" : "Inicia sesión para contratar";
}

// --- descuento ---
async function applyDiscount() {
  const code = document.getElementById("discount-code").value.trim();
  const note = document.getElementById("discount-note");
  if (!code) {
    state.discountPercent = 0;
    state.discountCode = "";
    note.textContent = "";
    note.className = "discount-note";
    renderTotals();
    return;
  }
  const data = await api("/home/api/discount", {
    method: "POST",
    body: JSON.stringify({ code }),
  });
  if (data.valid) {
    state.discountPercent = data.percent;
    state.discountCode = data.code;
    note.textContent = `Código aplicado: -${data.percent}%`;
    note.className = "discount-note ok";
  } else {
    state.discountPercent = 0;
    state.discountCode = "";
    note.textContent = "Código no válido.";
    note.className = "discount-note bad";
  }
  renderTotals();
}

// --- checkout ---
async function checkout() {
  const resultBox = document.getElementById("order-result");
  resultBox.style.display = "none";
  const itemsBefore = lastCart.items.slice();
  try {
    const data = await api("/home/api/checkout", {
      method: "POST",
      body: JSON.stringify({
        discount_code: state.discountCode,
        // El frontend envía el porcentaje legítimo validado por el servidor.
        discount_percent: state.discountPercent,
      }),
    });
    resultBox.style.display = "block";
    if (data.free) {
      resultBox.className = "order-result free";
      resultBox.innerHTML = `
        <div>${data.message}</div>
        <div>Pedido #${data.order_id} · Total pagado: <strong>${euro(data.total)}</strong></div>
        <div class="flag">🏁 ${data.flag}</div>`;
      showWin({ ...data, items: itemsBefore });
    } else {
      resultBox.className = "order-result normal";
      resultBox.innerHTML = `
        <div>${data.message}</div>
        <div>Pedido #${data.order_id} · Subtotal ${euro(data.subtotal)} · Descuento ${data.discount_percent}% · Total <strong>${euro(data.total)}</strong></div>`;
    }
    state.discountPercent = 0;
    state.discountCode = "";
    document.getElementById("discount-code").value = "";
    document.getElementById("discount-note").textContent = "";
    await loadCart();
  } catch (err) {
    resultBox.style.display = "block";
    resultBox.className = "order-result normal";
    resultBox.textContent = err.message;
  }
}

// --- pedido gratis: celebración ---
// Se muestra tras un checkout a 0 € desde la web, y también si el checkout se
// hizo desde Burp/curl: al volver a la pestaña se consulta el último pedido gratis.
const winKey = (orderId) => `cb_win_${state.user ? state.user.usuario : ""}_${orderId}`;

function winSeen(orderId) {
  try {
    return localStorage.getItem(winKey(orderId)) === "1";
  } catch (e) {
    return false;
  }
}

function markWinSeen(orderId) {
  try {
    localStorage.setItem(winKey(orderId), "1");
  } catch (e) {}
}

function showWin(order) {
  markWinSeen(order.order_id);
  document.getElementById("win-order").textContent = `#${String(order.order_id).padStart(4, "0")}`;
  const lines = document.getElementById("win-lines");
  lines.innerHTML = "";
  for (const it of order.items || []) {
    const row = document.createElement("div");
    row.className = "r-line";
    const name = document.createElement("span");
    name.textContent = `${it.qty}× ${it.nombre}`;
    const price = document.createElement("span");
    price.textContent = euro(it.linea);
    row.append(name, price);
    lines.appendChild(row);
  }
  document.getElementById("win-subtotal").textContent = euro(order.subtotal);
  document.getElementById("win-disc").textContent = `-${order.discount_percent}%`;
  document.getElementById("win-total").textContent = euro(order.total);
  document.getElementById("win-flag").textContent = order.flag;
  document.getElementById("win-copy").textContent = "Copiar";
  document.getElementById("win-modal").classList.add("open");
  launchConfetti();
}

async function checkFreeOrder() {
  if (!state.user) return;
  try {
    const { order } = await api("/home/api/orders/free");
    if (order && !winSeen(order.order_id)) {
      showWin(order);
      await loadCart();
    }
  } catch (e) {}
}

function launchConfetti() {
  const box = document.getElementById("confetti");
  box.innerHTML = "";
  const colors = ["#ff5b3a", "#ffd23f", "#3ccf98", "#b8a4ff", "#7cc6ff", "#ff9ccf"];
  for (let i = 0; i < 90; i++) {
    const p = document.createElement("i");
    p.style.left = `${Math.random() * 100}%`;
    p.style.background = colors[i % colors.length];
    p.style.animationDelay = `${Math.random() * 0.8}s`;
    p.style.animationDuration = `${2.2 + Math.random() * 1.8}s`;
    p.style.setProperty("--drift", `${(Math.random() - 0.5) * 220}px`);
    p.style.setProperty("--spin", `${Math.random() * 900 - 450}deg`);
    if (i % 3 === 0) p.style.borderRadius = "50%";
    box.appendChild(p);
  }
  setTimeout(() => (box.innerHTML = ""), 4800);
}

// --- modal de auth ---
let authMode = "login";

function openModal() {
  document.getElementById("auth-modal").classList.add("open");
}
function closeModal() {
  document.getElementById("auth-modal").classList.remove("open");
  document.getElementById("auth-msg").textContent = "";
}
function setAuthMode(mode) {
  authMode = mode;
  document.getElementById("tab-login").classList.toggle("active", mode === "login");
  document.getElementById("tab-register").classList.toggle("active", mode === "register");
  document.getElementById("email-field").style.display = mode === "register" ? "block" : "none";
  document.getElementById("auth-submit").textContent = mode === "register" ? "Crear cuenta" : "Entrar";
  document.getElementById("modal-intro").textContent =
    mode === "register"
      ? "Crea tu cuenta para entrar en CobraBot."
      : "Inicia sesión para entrar en CobraBot.";
}

function showWelcome(code, percent) {
  document.getElementById("welcome-code").textContent = code;
  document.getElementById("welcome-pct").textContent = `-${percent}% en tu primera compra`;
  document.getElementById("welcome-modal").classList.add("open");
}

async function submitAuth(event) {
  event.preventDefault();
  const msg = document.getElementById("auth-msg");
  msg.textContent = "";
  const usuario = document.getElementById("m-user").value;
  const password = document.getElementById("m-pass").value;
  const email = document.getElementById("m-email").value;
  try {
    let welcome = null;
    if (authMode === "register") {
      const data = await api("/home/api/register", {
        method: "POST",
        body: JSON.stringify({ usuario, email, password }),
      });
      welcome = data;
    } else {
      await api("/home/api/login", {
        method: "POST",
        body: JSON.stringify({ usuario, password }),
      });
    }
    closeModal();
    await refreshMe();
    await loadCart();
    if (welcome && welcome.welcome_code) {
      showWelcome(welcome.welcome_code, welcome.welcome_percent);
    } else {
      await checkFreeOrder();
    }
  } catch (err) {
    msg.textContent = err.message;
  }
}

// --- init ---
function wire() {
  document.getElementById("auth-btn").addEventListener("click", openModal);
  document.getElementById("auth-close").addEventListener("click", closeModal);
  document.getElementById("tab-login").addEventListener("click", () => setAuthMode("login"));
  document.getElementById("tab-register").addEventListener("click", () => setAuthMode("register"));
  document.getElementById("auth-form").addEventListener("submit", submitAuth);
  document.getElementById("welcome-start").addEventListener("click", () => {
    document.getElementById("welcome-modal").classList.remove("open");
  });
  document.getElementById("apply-discount").addEventListener("click", applyDiscount);
  document.getElementById("checkout-btn").addEventListener("click", () => {
    if (!state.user) {
      openModal();
      return;
    }
    checkout();
  });
  document.getElementById("logout-btn").addEventListener("click", async () => {
    await api("/home/api/logout", { method: "POST" });
    await refreshMe();
  });
  document.getElementById("win-close").addEventListener("click", () => {
    document.getElementById("win-modal").classList.remove("open");
  });
  document.getElementById("win-copy").addEventListener("click", async (e) => {
    const flag = document.getElementById("win-flag").textContent;
    try {
      await navigator.clipboard.writeText(flag);
      e.target.textContent = "¡Copiada!";
    } catch (err) {
      const range = document.createRange();
      range.selectNodeContents(document.getElementById("win-flag"));
      const sel = window.getSelection();
      sel.removeAllRanges();
      sel.addRange(range);
      e.target.textContent = "Selecciónala y copia";
    }
  });
  // Si el jugador hace el checkout desde Burp/curl, al volver a la pestaña lo detectamos
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") checkFreeOrder();
  });
  window.addEventListener("focus", checkFreeOrder);
}

(async function init() {
  wire();
  setAuthMode("register");
  await loadProducts();
  await refreshMe();
  await loadCart();
  await checkFreeOrder();
})();
