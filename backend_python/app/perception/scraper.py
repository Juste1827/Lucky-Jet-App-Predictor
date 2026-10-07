"""
Capteur Playwright Async pour Lucky Jet (Version Python optimisée).
Logique alignée à 100% sur le moteur Node.js fonctionnel (stopCoefficient + finalValue + latence paquet).
"""

import asyncio
import time
import re
import signal
from pathlib import Path
from playwright.async_api import async_playwright, BrowserContext, Page, WebSocket
from playwright_stealth import stealth_async
from loguru import logger

from app.config import settings
from app.memory.cloud_sql import get_session
from app.memory.episodic_memory import RawCrash


class LuckyJetScraper:
    def __init__(self, user_data_dir: str = "./browser_session"):
        self.game_state = "IDLE"  # IDLE, FLYING, COOLDOWN
        self.last_packet_time = int(time.time() * 1000)
        self.user_data_dir = Path(user_data_dir).resolve()
        self.session_file = self.user_data_dir / "storage_state.json"
        self._stop_event = asyncio.Event()

        # Création du dossier de session s'il n'existe pas
        self.user_data_dir.mkdir(parents=True, exist_ok=True)

    async def run(self):
        """Boucle principale du scraper avec gestion robuste des ressources."""
        logger.info("🚀 Lancement du Capteur Python (Logique Node.js portée)...")

        try:
            # Le bloc "async with" garantit la fermeture automatique et propre du navigateur
            async with async_playwright() as p:
                # 1. Lancement avec contexte persistant (gère automatiquement les cookies/session)
                context: BrowserContext = await p.chromium.launch_persistent_context(
                    user_data_dir=str(self.user_data_dir),
                    headless=False,
                    args=[
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-blink-features=AutomationControlled',
                        '--disable-web-security'
                    ],
                    ignore_default_args=['--enable-automation'],
                    viewport={"width": 1280, "height": 800},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
                )

                page = await context.new_page()

                # 2. Application du furtif (Stealth) sur la page
                await stealth_async(page)

                page.on("websocket", self._handle_websocket)

                logger.info(f"🌐 Navigation vers : {settings.TARGET_URL}")
                await page.goto(settings.TARGET_URL, wait_until="domcontentloaded", timeout=60000)

                logger.info("⏳ Connecte-toi manuellement si nécessaire. Le scraper est en écoute...")
                await asyncio.sleep(10)  # Temps pour se connecter manuellement la première fois

                # Sauvegarde explicite de l'état (utile pour la portabilité)
                await context.storage_state(path=str(self.session_file))
                logger.info("✅ Session sauvegardée pour les prochains lancements (plus de CAPTCHA !)")

                # 3. Boucle d'écoute infinie (se débloque quand _stop_event est défini)
                await self._stop_event.wait()

        except asyncio.CancelledError:
            logger.info("🛑 Annulation de la tâche principale.")
        except Exception as e:
            logger.exception("❌ Erreur critique dans la boucle principale")
        finally:
            # Playwright ferme automatiquement le contexte ici.
            # Pas besoin de await context.close() qui causerait un TargetClosedError.
            logger.info("✅ Arrêt du capteur terminé (nettoyage automatique géré par Playwright).")

    def _handle_websocket(self, ws: WebSocket):
        """Gère les messages entrants des WebSockets (Logique Node.js)."""
        # Filtrage exact et insensible à la casse
        url_lower = ws.url.lower()
        if 'gamedev-tech.cc' not in url_lower and 'luckyjet' not in url_lower:
            return

        logger.info(f"✅ FLUX WEBSOCKET CONNECTÉ : {ws.url[:60]}...")
        ws.on("framereceived", self._process_payload)

    def _process_payload(self, payload: str):
        """Analyse les payloads avec la logique exacte de index.js."""
        if self.game_state == "COOLDOWN":
            return

        if not payload or not isinstance(payload, str):
            return

        # 1. Calcul de la latence entre les paquets
        current_time_ms = int(time.time() * 1000)
        packet_latency = current_time_ms - self.last_packet_time
        self.last_packet_time = current_time_ms

        # 2. Détection de l'état FLYING
        if '"eventType": "changeState"' in payload and '"state": "flying"' in payload:
            if self.game_state == "IDLE":
                self.game_state = "FLYING"
                logger.debug("🚀 État du jeu: FLYING")
            return

        # 3. Détection du CRASH via stopCoefficient
        if '"eventType": "stopCoefficient"' in payload:
            if self.game_state == "FLYING":
                match = re.search(r'"finalValue":\s*(\d+\.?\d*)', payload)
                if match:
                    crash_value = float(match.group(1))
                    logger.info(f"💥 CRASH DÉTECTÉ : {crash_value}x | Latence paquet: {packet_latency}ms")

                    self.game_state = "COOLDOWN"  # Empêche les doubles déclenchements

                    # Sauvegarde asynchrone immédiate dans Cloud SQL
                    asyncio.create_task(self._save_to_db(crash_value, packet_latency))

                    # Reset de l'état après 6 secondes
                    asyncio.create_task(self._reset_state_after_delay(6))
            return

        # 4. Reset de l'état quand le jeu est en attente du prochain tour
        if '"eventType": "changeState"' in payload and '"state": "waiting"' in payload:
            self.game_state = "IDLE"
            return

    async def _reset_state_after_delay(self, seconds: int):
        """Réinitialise l'état du jeu après un délai."""
        await asyncio.sleep(seconds)
        self.game_state = "IDLE"

    async def _save_to_db(self, crash_value: float, latency_ms: int):
        """Insère les données brutes dans la table raw_crashes."""
        try:
            async with get_session() as session:
                new_crash = RawCrash(
                    crash_value=crash_value,
                    latency_ms=latency_ms,
                    delta_time_ms=0
                )
                session.add(new_crash)
                await session.commit()  # Garantit l'écriture en base
            logger.success(f"💾 Sauvegardé en base : {crash_value}x")
        except Exception as e:
            logger.error(f"❌ Échec de la sauvegarde en base : {e}")

    def stop(self):
        """Méthode publique pour déclencher l'arrêt propre depuis l'extérieur."""
        logger.info("🛑 Signal d'arrêt reçu...")
        self._stop_event.set()


if __name__ == "__main__":
    scraper = LuckyJetScraper()

    # Gestion propre des signaux système (Ctrl+C)
    def signal_handler(sig, frame):
        scraper.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        asyncio.run(scraper.run())
    except KeyboardInterrupt:
        logger.info("⌨️ Interruption clavier détectée.")
    finally:
        logger.info("👋 Programme terminé.")