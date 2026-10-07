"""
Configuration centrale du backend Lucky Jet Predictor AI.
Lit les variables d'environnement et expose des settings typés et sécurisés.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    """
    Settings chargés depuis les variables d'environnement (.env).
    Pydantic assure la validation et le typage automatique.
    """

    # --- Google Cloud SQL (PostgreSQL) ---
    # Le pilote asyncpg est impératif pour l'asynchrone SQLAlchemy
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/luckyjet"

    # --- Firebase (Firestore) ---
    # Ce champ sera résolu en chemin absolu dans le modèle validator ci-dessous
    FIREBASE_CREDENTIALS_PATH: str = "credentials/serviceAccountKey.json"
    FIREBASE_DATABASE_ID: str = "app-predictor-lucky-jet"

    # --- Jeu Lucky Jet ---
    TARGET_URL: str = "https://1win.com/fr-CI/casino/play/v_1wingames:luckyjet"

    # --- Configuration IA ---
    CONTEXT_WINDOW_SIZE: int = 64
    MIN_CONFIDENCE_THRESHOLD: int = 60
    WARMUP_ROUNDS: int = 100
    CHECKPOINT_INTERVAL: int = 1000  # Sauvegarde majeure (la sauvegarde online se fait tous les 32 tours)

    # --- Dimensions du réseau neuronal (Tabula Rasa) ---
    LATENT_DIM: int = 128
    NUM_TRANSFORMER_LAYERS: int = 4
    NUM_ATTENTION_HEADS: int = 8
    FEEDFORWARD_DIM: int = 512
    DROPOUT_RATE: float = 0.1
    MASKED_RATIO: float = 0.2

    # --- Apprentissage ---
    LEARNING_RATE: float = 0.001
    BATCH_SIZE: int = 32
    HUBER_DELTA: float = 1.0

    # Configuration Pydantic V2
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    @property
    def absolute_credentials_path(self) -> Path:
        """Retourne le chemin absolu vers les credentials Firebase, résolu dynamiquement."""
        return BASE_DIR / self.FIREBASE_CREDENTIALS_PATH


# Instance globale accessible partout dans l'application
settings = Settings()

# Chemins absolus utiles pour le projet
# Si config.py est dans app/, parent.parent est la racine du projet (backend_python/)
BASE_DIR = Path(__file__).resolve().parent.parent
CREDENTIALS_DIR = BASE_DIR / "credentials"