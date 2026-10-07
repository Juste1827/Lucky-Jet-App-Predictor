"""
Mémoire épisodique : Fonctions utilitaires pour gérer les crashs bruts.
Enrichie avec l'Ingénierie des Features Latentes pour une analyse contextuelle.
"""
import math
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from app.memory.cloud_sql import RawCrash


async def get_last_crash(session: AsyncSession) -> Optional[RawCrash]:
    """Récupère le dernier crash enregistré."""
    result = await session.execute(
        select(RawCrash).order_by(desc(RawCrash.captured_at)).limit(1)
    )
    return result.scalar_one_or_none()


async def get_last_crashes(session: AsyncSession, limit: int = 64) -> List[Dict[str, Any]]:
    """
    Récupère les N derniers crashs pour l'analyse IA.
    CORRECTION CRITIQUE : Récupère les plus récents, puis les trie chronologiquement.
    ENRICHISSEMENT : Ajoute des features latentes de base (momentum, volatilité locale).
    """
    # 1. Récupérer les N derniers crashs (du plus récent au plus ancien)
    result = await session.execute(
        select(RawCrash)
        .order_by(desc(RawCrash.captured_at))
        .limit(limit)
    )
    crashes = result.scalars().all()

    # 2. Inverser la liste pour avoir l'ordre chronologique (du plus ancien au plus récent)
    # C'est l'ordre attendu par un Transformer (t-64 ... t-1, t)
    crashes.reverse()

    if not crashes:
        return []

    # 3. Ingénierie des Features Latentes (Calculs locaux pour enrichir l'input du modèle)
    crash_values = [c.crash_value for c in crashes]
    latencies = [c.latency_ms or 0 for c in crashes]

    # Calculs de base pour le contexte (peuvent être étendus)
    mean_crash = sum(crash_values) / len(crash_values)
    variance = sum((x - mean_crash) ** 2 for x in crash_values) / len(crash_values)
    std_crash = math.sqrt(variance) if variance > 0 else 0.0

    mean_latency = sum(latencies) / len(latencies)

    processed_crashes = []
    for i, crash in enumerate(crashes):
        # Calcul du momentum local (différence avec le crash précédent)
        momentum = (crash.crash_value - crashes[i-1].crash_value) if i > 0 else 0.0

        # Z-score de la latence (détecte les anomalies réseau, souvent corrélées aux gros crashs)
        latency_zscore = ((crash.latency_ms or 0) - mean_latency) / (std_crash + 1e-6)

        processed_crashes.append({
            'id': crash.id,
            'crash_value': float(crash.crash_value),
            'latency_ms': float(crash.latency_ms or 0),
            'delta_time_ms': float(crash.delta_time_ms or 0),
            'captured_at': crash.captured_at,
            # 🧠 Features Latentes Injectées
            'momentum': float(momentum),
            'local_volatility': float(std_crash), # Volatilité de la fenêtre actuelle
            'latency_anomaly_score': float(latency_zscore)
        })

    return processed_crashes


async def calculate_delta_time(session: AsyncSession) -> int:
    """Calcule le delta temps en ms depuis le dernier crash avec robustesse timezone."""
    last_crash = await get_last_crash(session)

    if last_crash and last_crash.captured_at:
        now = datetime.now(timezone.utc)

        # Correction robuste des datetime naïfs
        if last_crash.captured_at.tzinfo is None:
            last_crash.captured_at = last_crash.captured_at.replace(tzinfo=timezone.utc)

        delta = (now - last_crash.captured_at).total_seconds() * 1000
        return int(max(0, delta))

    return 0