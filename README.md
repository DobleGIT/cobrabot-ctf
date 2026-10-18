# CobraBot CTF

CTF que monté para el **Samsung Dev Challenge (16 oct 2026)**. Es una cadena de
**seis retos** con hilo narrativo: una primera mitad de **OSINT** y una segunda de
**seguridad web**. Este repositorio contiene y despliega los **tres retos web**
(retos 4, 5 y 6), que son los que tienen código y servicios propios.

Todo arranca con un solo comando (Docker Compose).

> **Aviso:** los fallos de seguridad son **intencionados**. Esto es un entorno de
> entrenamiento, no software de producción. Personajes, empresas, datos y flags
> son ficticios y satíricos.

---

## La historia

Todo empieza con una web corporativa víctima de un *defacement*: el atacante ha
dejado su firma. A partir de esa imagen, el jugador va tirando del hilo (OSINT)
hasta descubrir quién hay detrás: un supuesto "gurú" de la tecnología que, lejos
de ser un genio, comete descuido tras descuido. El rastro desemboca en su propio
producto SaaS, **CobraBot**: un software (ficticio) de cobro automatizado de
deudas, tan agresivo en su marketing como flojo en su seguridad.

En la segunda mitad, el jugador ya no investiga al personaje: ataca directamente
su producto y demuestra lo mal construido que está, rompiéndolo de tres maneras
distintas.

### Mapa de los seis retos

| # | Reto | Fase | Qué se practica |
|---|------|------|-----------------|
| 1 | La imagen del ataque | OSINT | Metadatos de un SVG (ruta de exportación de Inkscape -> alias del atacante) |
| 2 | El descuido | OSINT | Secreto filtrado en el historial de Git (borrado del HEAD, no del `git log`) |
| 3 | El viaje | OSINT | Código de barras de una tarjeta de embarque que revela un destino "tachado" |
| 4 | La tienda que regala | Web | Lógica de negocio: descuento manipulable desde el cliente |
| 5 | El soporte bocazas | Web | Prompt injection en un chatbot LLM con acceso a datos |
| 6 | La base de clientes | Web | JWT con `alg:none` (firma no verificada) |

Los retos 1-3 (OSINT) se montaban con material externo (imágenes, un repo de
ejemplo, etc.) y no forman parte de este código. **Aquí viven los retos 4, 5 y 6.**

---

## Los retos web de este repo

Cada reto es una pieza del SaaS CobraBot y se resuelve en el navegador.

### Reto 4 — La tienda que regala
La tienda online de CobraBot. El objetivo es conseguir un pedido real **a 0 €**.
El fallo está en la **lógica de negocio**: el servidor se fía de un dato de
descuento que controla el cliente en el checkout. Se practica el análisis de
tráfico y la manipulación de peticiones (DevTools / Burp).
**URL:** `/home`

### Reto 5 — El soporte bocazas
El chatbot de soporte de CobraBot, conectado a un LLM y con acceso a la base de
datos de usuarios mediante *tools*. El objetivo es entrar en el panel `/admin`.
El bot tiene instrucciones de no soltar credenciales, pero es vulnerable a
**prompt injection**: se practica cómo esas defensas (system prompt + blocklist)
son porosas y cómo un modelo con acceso a datos sensibles puede acabar
filtrándolos. Luego hay una fase offline de cracking de hash.
**URL:** `/admin` (chatbot en `/admin/chat`)

### Reto 6 — La base de clientes
El panel de cliente de CobraBot. El objetivo es usar una acción reservada a
administradores ("Exportar base de clientes"). La sesión es un **JWT** y el
servidor lo acepta con **`alg:none`**, es decir, sin verificar la firma. Se
practica la decodificación y forja de tokens JWT.
**URL:** `/profile/cuenta`

> La **solución paso a paso** de cada reto está en [`WRITEUP.md`](WRITEUP.md).

---

## Requisitos

- [Docker](https://docs.docker.com/get-docker/) y Docker Compose v2.
- Una **API key de OpenRouter** (o cualquier API compatible con OpenAI) para el
  chatbot del reto 5. El resto de retos funciona sin ella.

## Cómo ejecutarlo

```bash
# 1. Copia la plantilla de configuración
cp .env.example .env          # en Windows:  copy .env.example .env

# 2. Edita .env y pon tu LLM_API_KEY (lo único imprescindible para el reto 5)

# 3. Levanta los tres servicios
docker compose up --build
```

Cuando terminen de arrancar, abre **http://localhost:8080/home**.

Los tres retos quedan servidos en la misma URL:

| Reto | Entrada |
|------|---------|
| 4 — La tienda que regala | http://localhost:8080/home |
| 5 — El soporte bocazas | http://localhost:8080/admin (chatbot en `/admin/chat`) |
| 6 — La base de clientes | http://localhost:8080/profile/cuenta |

Para parar: `Ctrl+C`, o `docker compose down` para eliminar los contenedores.

Por dentro, un **Caddy** hace de proxy inverso y reparte las rutas: `/profile*`
va al servicio del reto 6 y el resto a CobraBot. Es el mismo ruteo que en
producción, pero en HTTP y sin dominio.

## Configuración

Todo vive en un único `.env` en la raíz (copiado de `.env.example`). Lo relevante:

- **Flags:** `SHOP_FLAG` (reto 4), `FLAG` (reto 5), `RETO6_FLAG` (reto 6).
- **Chatbot (reto 5):** `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`.
- **Credenciales del reto 5:** `ADMIN_USER` / `ADMIN_PASSWORD` / `ADMIN_HASH_MD5`
  (el hash debe corresponder a la contraseña; recalcúlalo con
  `python -c "import hashlib;print(hashlib.md5(b'nueva').hexdigest())"`).
- **Dificultad del reto 5:** se ajusta con `prompts/system.txt`,
  `filters/blocked_phrases.txt`, `FILTER_ENABLED` y `OUTPUT_FILTER_ENABLED`.
  Tras tocar `prompts/` o `filters/`: `docker compose restart app`.

El `.env` real (con tu API key y tus flags) está en `.gitignore` y **nunca se
sube**; en el repositorio solo viaja `.env.example`.

## Estructura

```
cobrabot-ctf/
├── docker-compose.yml        # levanta los 3 servicios
├── .env.example              # plantilla de configuración (cópiala a .env)
├── deploy/Caddyfile.local    # proxy inverso para la demo local (:8080)
├── cobrabot/                 # retos 4 y 5 (FastAPI)
│   ├── app/                  # backend
│   ├── static/               # frontend (HTML/JS/CSS, sin build)
│   ├── prompts/system.txt    # system prompt del bot
│   ├── filters/              # blocklist de entrada
│   └── deploy/               # Caddyfile + script para VPS (HTTPS real)
└── reto6-jwt/                # reto 6 (FastAPI)
    ├── app/
    └── static/
```

## Despliegue en un VPS (producción con HTTPS)

En `cobrabot/deploy/` están el `Caddyfile` (TLS + Cloudflare) y `setup_vps.sh`
para un servidor real con dominio. Ahí se activa el captcha Turnstile
(`TURNSTILE_ENABLED=true` con tus claves) y se fija `DOMAIN`.
