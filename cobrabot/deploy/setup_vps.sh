#!/usr/bin/env bash
# Prepara un Droplet Ubuntu 24.04 limpio y levanta CobraBot.
# Uso (como root, en el VPS):  bash setup_vps.sh
set -euo pipefail

APP_DIR=/opt/cobrabot

echo "[1/5] Actualizando sistema e instalando Docker..."
apt-get update -y
apt-get install -y ca-certificates curl ufw
if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sh
fi

echo "[2/5] Swap de 1 GB (por si el droplet es pequeno)..."
if ! swapon --show | grep -q /swapfile; then
  fallocate -l 1G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

echo "[3/5] Firewall: solo SSH, HTTP y HTTPS..."
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 443/udp
ufw --force enable

echo "[4/5] Desplegando la app en $APP_DIR..."
mkdir -p "$APP_DIR"
tar -xzf ~/cobrabot.tar.gz -C "$APP_DIR"
[ -f ~/.env ] && cp ~/.env "$APP_DIR/.env"
cd "$APP_DIR"
if [ ! -f .env ]; then echo "ERROR: falta .env (subelo con scp)"; exit 1; fi
grep -q '^DOMAIN=example.com' .env && { echo "ERROR: cambia DOMAIN en .env"; exit 1; }
mkdir -p logs data

echo "[5/5] Arrancando contenedores..."
docker compose up -d --build
sleep 5
docker compose ps
echo
echo "Comprobacion local:"
curl -s -o /dev/null -w "app -> HTTP %{http_code}\n" http://127.0.0.1:8000/
echo "Listo. Abre https://$(grep '^DOMAIN=' .env | cut -d= -f2)"
