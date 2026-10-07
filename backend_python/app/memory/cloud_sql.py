"""
Configuration et modèles SQLAlchemy pour Cloud SQL PostgreSQL.
Contient les définitions des tables du Master Blueprint, optimisées pour la haute fréquence
et l'architecture Dual-Storage (Fichier Local + Métadonnées SQL).
"""
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import Column, BigInteger, Double, Integer, DateTime, String, Boolean, func, Index
from loguru import logger
from app.config import settings

Base = declarative_base()

# ==========================================
# 1. raw_crashes (Mémoire Épisodique Brute)
# ==========================================
class RawCrash(Base):
    __tablename__ = "raw_crashes"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    crash_value = Column(Double, nullable=False)
    latency_ms = Column(Integer, nullable=False)
    delta_time_ms = Column(Integer, nullable=True)
    captured_at = Column(DateTime(timezone=True), server_default=func.now(), index=True) # 🚀 INDEX AJOUTÉ

    # Index composé pour accélérer les requêtes "derniers crashs"
    __table_args__ = (
        Index('ix_raw_crashes_captured_at_desc', captured_at.desc()),
    )

# ==========================================
# 2. predictions_log (Mémoire des Décisions)
# ==========================================
class PredictionLog(Base):
    __tablename__ = "predictions_log"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    round_id = Column(BigInteger, nullable=True, index=True) # 🚀 INDEX AJOUTÉ pour les jointures
    predicted_score = Column(Double, nullable=False)
    confidence = Column(Integer, nullable=False)
    regime = Column(String(20), nullable=False)
    sage_memory_score = Column(Double, nullable=True)
    sage_drift_score = Column(Double, nullable=True)
    sage_velocity_score = Column(Double, nullable=True)
    # 🚀 SUPPRIMÉ : latent_vector (LargeBinary) était inutile et lourd pour les stats
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

# ==========================================
# 3. feedback_loop (Mémoire d'Apprentissage)
# ==========================================
class FeedbackLoop(Base):
    __tablename__ = "feedback_loop"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    prediction_id = Column(BigInteger, nullable=True, index=True) # 🚀 INDEX AJOUTÉ pour le JOIN dans /api/stats
    actual_crash = Column(Double, nullable=False)
    error_score = Column(Double, nullable=False)
    was_accurate = Column(Boolean, nullable=False)
    confidence_calibration = Column(Double, nullable=True)
    learned_at = Column(DateTime(timezone=True), server_default=func.now(), index=True) # 🚀 INDEX AJOUTÉ pour le ORDER BY

# ==========================================
# 4. model_checkpoints (Métadonnées des Poids)
# ==========================================
class ModelCheckpointTable(Base):
    __tablename__ = "model_checkpoints"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    version = Column(String(50), nullable=False)
    epoch = Column(Integer, nullable=False)
    total_rounds_trained = Column(Integer, nullable=False)
    accuracy_score = Column(Double, nullable=True)
    loss_value = Column(Double, nullable=True)

    # 🚀 CORRECTION CRITIQUE : Remplacement de LargeBinary par String
    # Stocke le chemin du fichier local (ex: "checkpoints/checkpoint_v1.0.pt")
    # Cela élimine définitivement l'erreur "Invalid magic number; corrupt file?"
    checkpoint_path = Column(String(255), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

# ==========================================
# 5. regime_history (Historique des Contextes)
# ==========================================
class RegimeHistory(Base):
    __tablename__ = "regime_history"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    regime = Column(String(20), nullable=False)
    confidence = Column(Double, nullable=False)
    latent_cluster_id = Column(Integer, nullable=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


# --- Gestion de la connexion ---
# pool_pre_ping=True est EXCELLENT : il vérifie que la connexion est vivante avant de l'utiliser
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False, # Mettre à True temporairement si tu veux voir les requêtes SQL brutes pour le debug
    pool_pre_ping=True,
    pool_size=10,       # 🚀 Optimisation : nombre de connexions maintenues ouvertes
    max_overflow=20     # 🚀 Optimisation : connexions supplémentaires en cas de pic
)

AsyncSessionLocal = sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)

@asynccontextmanager
async def get_session():
    """Fournit une session de base de données asynchrone (Context Manager)."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            logger.error(f"❌ Erreur de session SQL, rollback effectué : {e}")
            raise
        finally:
            await session.close()

async def init_db():
    """Crée les tables et les index si elles n'existent pas."""
    async with engine.begin() as conn:
        # create_all est intelligent : il ne crée que ce qui manque
        await conn.run_sync(Base.metadata.create_all)
    logger.success("✅ Tables et Index Cloud SQL vérifiés/créés avec succès.")