# Write-up — CobraBot CTF (retos web)

CTF del **Samsung Dev Challenge** (16 oct 2026). Seis retos encadenados: una
primera mitad de **OSINT** y una segunda de **seguridad web**. Este repositorio
contiene y despliega los tres retos web (4, 5 y 6). Resumo primero el arco
completo para dar contexto y luego detallo los tres retos que viven aquí.

> Las flags concretas se configuran en los `.env` y no se incluyen en el repo.
> Aquí se explica la **técnica**, no el valor exacto de cada flag.

## El arco (contexto OSINT, retos 1–3)

El punto de partida es la imagen de *defacement* que el atacante deja en la web
de la víctima. Tirando del hilo:

1. **La imagen del ataque** — los metadatos del SVG guardan la ruta de
   exportación de Inkscape, que incluye el nombre de usuario del sistema del
   atacante. Con ese alias se llega a sus perfiles públicos (GitHub).
2. **El descuido** — en el historial de commits de su repo quedó una API key que
   borró del estado actual pero no del pasado (`git log`). Borrar un fichero no
   borra su historia en Git.
3. **El viaje** — en una foto presume de un viaje; el destino aparece tachado a
   la vista, pero el **código de barras** de la tarjeta de embarque conserva la
   ruta y revela la ciudad.

El rastro lleva a que el atacante es otro "gurú" con su propio SaaS, **CobraBot**.
A partir de aquí, los retos web de este repo.

---

## Reto 4 — La tienda que regala (descuento manipulable)

**Objetivo:** conseguir un pedido real a 0 € en la tienda.

**Fallo (intencionado):** el servidor confía en el porcentaje de descuento que
envía el cliente en el checkout, en lugar de calcularlo él a partir del código.

**Ruta prevista:**
1. Regístrate: te dan un código de bienvenida (p. ej. 10%).
2. Añade productos al carrito y aplica el código.
3. Intercepta `POST /home/api/checkout` (Burp o las DevTools del navegador) y
   cambia `discount_percent` a `100`.
4. El total baja a 0 € y, al confirmar un pedido gratuito con carrito no vacío,
   la respuesta incluye la flag.

**Por qué funciona:** los precios y el carrito vienen del servidor y no son
manipulables; el **único** valor controlado por el atacante es el porcentaje de
descuento, que el backend aplica sin validarlo contra el código ni acotarlo.
`/home/api/discount` solo *valida* el código y devuelve su porcentaje para
mostrarlo, pero no lo vincula al checkout.

**La corrección sería:** mirar el descuento en el servidor a partir del código
aplicado y nunca aceptar el porcentaje del cliente (y acotar 0–100).

---

## Reto 5 — El soporte bocazas (prompt injection en el LLM)

**Objetivo:** entrar en el panel `/admin`.

**Fallo (intencionado):** el chatbot de soporte (`/admin/chat`) es vulnerable a
inyección de prompt. Las credenciales **no** están en el system prompt: viven en
una base de datos SQLite que el bot consulta mediante una *tool*
(`buscar_usuario`). El bot rechaza dar la contraseña directamente, pero el prompt
permite deliberadamente "transformar/codificar" campos como tarea de soporte.

**Ruta prevista:**
1. Haz que el bot localice la cuenta de administrador. No tiene un nombre obvio
   (su rol es `administrador` y figura como "Cuenta de sistema").
2. No le pidas la contraseña a las claras (lo bloquean el prompt y la blocklist
   de entrada). En su lugar, pídele que **reescriba/codifique** el campo del hash
   (base64, hex, URL-encode, JSON...). El prompt trata eso como una operación
   permitida, así que suelta el `password_md5`.
3. Crackea el hash MD5 offline (p. ej. CrackStation) → obtienes la contraseña.
4. Inicia sesión en `/admin`. El login devuelve la flag en la respuesta.

**Por qué funciona:** el hash queda en el contexto del modelo (está en el
resultado de la tool), y la "transformación de formato" es un hueco que la
instrucción del prompt no cierra. Las defensas son deliberadamente débiles: un
system prompt instructivo y una blocklist por subcadenas.

**Palancas de dificultad:** `prompts/system.txt`, `filters/blocked_phrases.txt`,
`FILTER_ENABLED` y `OUTPUT_FILTER_ENABLED` (este último redacta el hash de la
respuesta; va desactivado por defecto porque corta la vía prevista).

---

## Reto 6 — La base de clientes (JWT `alg:none`)

**Objetivo:** en `/profile/cuenta`, usar el botón "Exportar base de clientes",
reservado a administradores.

**Fallo (intencionado):** la sesión es un JWT que el servidor acepta con
`alg:none`, es decir, sin verificar la firma.

**Ruta prevista:**
1. Regístrate e inicia sesión: recibes un JWT en la cookie `reto6_session`
   (a propósito **sin** HttpOnly, para poder leerla y editarla).
2. Decodifica el token: verás un claim `role` con valor `user`.
3. Forja un token nuevo con `role: admin`, cabecera `alg: none` y **sin firma**.
4. Reemplaza la cookie y pulsa "Exportar base de clientes":
   `POST /profile/admin/export` comprueba `role == admin` y, al pasar, devuelve
   la flag junto con un listado de clientes ficticio.

**Por qué funciona:** el verificador acepta tokens con `alg:none`, así que
cualquiera puede fabricar los claims que quiera sin conocer el secreto HS256. El
endpoint `/profile/api/me` oculta el `role` para obligar a decodificar el token a
mano, pero eso no añade seguridad real.

**La corrección sería:** rechazar `alg:none`, fijar el algoritmo esperado (HS256)
y validar siempre la firma contra el secreto del servidor.

---

## Resumen de las lecciones

| Reto | Lección |
|------|---------|
| 4 | Nunca confíes en valores sensibles que vienen del cliente; calcula precios y descuentos en el servidor. |
| 5 | Un LLM con acceso a datos sensibles puede filtrarlos aunque "tenga prohibido"; las defensas por prompt/blocklist son porosas. |
| 6 | Valida siempre la firma del JWT y fija el algoritmo; `alg:none` es una puerta abierta. |
