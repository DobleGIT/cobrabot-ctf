"""
Prueba de carga simple: simula N "equipos" hablando con el chat a la vez,
cada uno manda varios mensajes seguidos, y mide latencias y errores.

Uso:
    python tests/load_test.py --url http://localhost:8000 --teams 20 --turns 4
"""

import argparse
import asyncio
import statistics
import time

import httpx

MESSAGES = [
    "Hola, tengo una duda sobre mi factura de este mes.",
    "¿Por qué se me ha cobrado dos veces el mismo recibo?",
    "¿Cómo puedo cambiar mi método de pago?",
    "Gracias, eso es todo.",
]


async def run_conversation(client: httpx.AsyncClient, team_id: int, turns: int, results: list):
    cookies = {}
    for i in range(turns):
        message = MESSAGES[i % len(MESSAGES)]
        start = time.perf_counter()
        try:
            resp = await client.post("/api/chat", json={"message": message}, cookies=cookies, timeout=30)
            elapsed = time.perf_counter() - start
            cookies.update(resp.cookies)
            ok = resp.status_code == 200
            results.append({"team": team_id, "turn": i, "status": resp.status_code, "latency": elapsed, "ok": ok})
        except Exception as exc:
            elapsed = time.perf_counter() - start
            results.append({"team": team_id, "turn": i, "status": None, "latency": elapsed, "ok": False, "error": str(exc)})


async def main(base_url: str, teams: int, turns: int):
    results: list = []
    async with httpx.AsyncClient(base_url=base_url) as client:
        start = time.perf_counter()
        await asyncio.gather(*[run_conversation(client, t, turns, results) for t in range(teams)])
        total_time = time.perf_counter() - start

    latencies = [r["latency"] for r in results]
    errors = [r for r in results if not r["ok"]]

    print(f"\nEquipos simulados: {teams} | Turnos por equipo: {turns} | Peticiones totales: {len(results)}")
    print(f"Tiempo total: {total_time:.2f}s")
    print(f"Errores: {len(errors)} ({len(errors) / len(results) * 100:.1f}%)")
    if latencies:
        print(f"Latencia media: {statistics.mean(latencies):.2f}s")
        print(f"Latencia mediana: {statistics.median(latencies):.2f}s")
        sorted_lat = sorted(latencies)
        p95_idx = max(0, int(len(sorted_lat) * 0.95) - 1)
        print(f"Latencia p95: {sorted_lat[p95_idx]:.2f}s")
        print(f"Latencia máx: {max(latencies):.2f}s")

    if errors:
        print("\nEjemplos de errores:")
        for e in errors[:5]:
            print(f"  equipo={e['team']} turno={e['turn']} status={e['status']} error={e.get('error')}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000", help="URL base de la app")
    parser.add_argument("--teams", type=int, default=20, help="Conversaciones concurrentes a simular")
    parser.add_argument("--turns", type=int, default=4, help="Mensajes por conversación")
    args = parser.parse_args()

    asyncio.run(main(args.url, args.teams, args.turns))
