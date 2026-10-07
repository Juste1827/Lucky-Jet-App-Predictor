"""
Script d'initialisation de la base de données Cloud SQL PostgreSQL.
Crée les 5 tables essentielles pour la mémoire du cerveau neuronal.

Usage :
    python scripts/init_db.py
"""

import asyncio
import sys
from pathlib import Path

# Ajouter le dossier parent au path pour importer app.config
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import Column, BigInteger, Double, Integer, String, Boolean, LargeBinary, DateTime, ForeignKey, Index, text
from sqlalchemy.sql import func
from sqlalchemy.orm import declarative_base
from app.config import settings

# Base ORM
Base = declarative_base()


# ============================================================
# DÉFINITION DES 5 TABLES (Mémoire du Cerveau)
# ============================================================

class RawCrash(Base):
    __tablename__ = "raw_crashes"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    crash_value = Column(Double, nullable=False, comment="Valeur de crash brute (ex: 4.21)")
    latency_ms = Column(Integer, nullable=False, comment="Latence réseau en millisecondes")
    delta_time_ms = Column(Integer, nullable=False, comment="Temps écoulé depuis le tour précédent (ms)")
    captured_at = Column(DateTime(timezone=True), server_default=func.now(), comment="Timestamp de capture")
    __table_args__ = (Index("idx_crashes_time", captured_at.desc()),)

    def __repr__(self):
        return f"<RawCrash(id={self.id}, crash={self.crash_value}x, latency={self.latency_ms}ms)>"


class PredictionLog(Base):
    __tablename__ = "predictions_log"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    round_id = Column(BigInteger, ForeignKey("raw_crashes.id"), nullable=True, comment="ID du tour prédit")
    predicted_score = Column(Double, nullable=False, comment="Score prédit par le Méta-Décideur")
    confidence = Column(Integer, nullable=False, comment="Confiance en pourcentage (0-100)")
    regime = Column(String(20), nullable=False, comment="Régime détecté: normal/high-rtp/low-rtp/volatile")
    sage_memory_score = Column(Double, nullable=True, comment="Sortie du Sage Memory")
    sage_drift_score = Column(Double, nullable=True, comment="Sortie du Sage Drift")
    sage_velocity_score = Column(Double, nullable=True, comment="Sortie du Sage Velocity")
    latent_vector = Column(LargeBinary, nullable=True, comment="Vecteur latent 128D sérialisé (état du cerveau)")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (Index("idx_predictions_round", round_id),)

    def __repr__(self):
        return f"<PredictionLog(id={self.id}, predicted={self.predicted_score}, conf={self.confidence}%)>"


class FeedbackLoop(Base):
    __tablename__ = "feedback_loop"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    prediction_id = Column(BigInteger, ForeignKey("predictions_log.id"), nullable=False)
    actual_crash = Column(Double, nullable=False, comment="Valeur de crash réelle observée")
    error_score = Column(Double, nullable=False, comment="Huber Loss calculée")
    was_accurate = Column(Boolean, nullable=False, comment="La prédiction était-elle correcte ?")
    confidence_calibration = Column(Double, nullable=True, comment="Brier Score pour calibrer la confiance")
    learned_at = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (Index("idx_feedback_accuracy", was_accurate),)

    def __repr__(self):
        return f"<FeedbackLoop(pred={self.prediction_id}, accurate={self.was_accurate}, error={self.error_score})>"


class ModelCheckpoint(Base):
    __tablename__ = "model_checkpoints"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    version = Column(String(50), nullable=False, comment="Version du modèle (ex: v1.2.3)")
    epoch = Column(Integer, nullable=False, comment="Nombre d'époques d'entraînement")
    total_rounds_trained = Column(Integer, nullable=False, comment="Nombre total de tours vus")
    accuracy_score = Column(Double, nullable=True, comment="Accuracy sur les 1000 derniers tours")
    loss_value = Column(Double, nullable=True, comment="Dernière loss enregistrée")
    model_weights = Column(LargeBinary, nullable=False, comment="State dict PyTorch sérialisé (pickle)")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<ModelCheckpoint(version={self.version}, rounds={self.total_rounds_trained})>"


class RegimeHistory(Base):
    __tablename__ = "regime_history"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    regime = Column(String(20), nullable=False)
    confidence = Column(Double, nullable=False)
    latent_cluster_id = Column(Integer, nullable=True, comment="Cluster découvert dynamiquement")
    started_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<RegimeHistory(regime={self.regime}, conf={self.confidence})>"


# ============================================================
# FONCTION D'INITIALISATION
# ============================================================

async def init_database():
    print("=" * 60)
    print("🚀 Initialisation de la base de données Lucky Jet AI")
    print("=" * 60)
    print(f"📡 URL de connexion : {settings.DATABASE_URL[:40]}...")

    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=1800,
        connect_args={"timeout": 30, "command_timeout": 60}
    )

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        print("✅ Tables créées avec succès :")
        for table_name in Base.metadata.tables.keys():
            print(f"    {table_name}")

        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT version();"))
            pg_version = result.scalar()
            print(f"\n🐘 PostgreSQL version : {pg_version}")

        await engine.dispose()
        print("\n✨ Base de données prête ! Le cerveau peut commencer à apprendre.")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Erreur lors de l'initialisation : {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(init_database())