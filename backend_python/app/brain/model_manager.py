"""
Gestionnaire de modèle: Chargement, sauvegarde, et persistance des checkpoints.
Architecture Dual-Storage (Fichier Local + Métadonnées SQL) pour éliminer toute corruption.
Version v2.3 : Chargement robuste avec gestion des checkpoints anciens (strict=False)
"""
import torch
import os
from datetime import datetime
from pathlib import Path
from sqlalchemy import select, desc
from loguru import logger

from app.memory.cloud_sql import get_session, ModelCheckpointTable
from app.brain.neural_engine import LuckyJetPredictor


class ModelCheckpoint:
    """Gestionnaire des poids du modèle et de l'état de l'optimiseur."""

    def __init__(self, checkpoint_dir: str = "./checkpoints"):
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

        self.model = LuckyJetPredictor()

        # Optimiseur aligné avec l'OnlineLearner
        self.optimizer = torch.optim.AdamW(
            self.model.parameters(),
            lr=1e-4,
            weight_decay=1e-5
        )

        self.total_rounds_trained = 0
        self.current_epoch = 0
        self._checkpoint_file_path = None

        logger.info("📦 ModelCheckpoint Manager initialisé (Dual-Storage: Local + SQL)")

    async def save_checkpoint(self, accuracy: float = 0.0, loss: float = 0.0, is_dream_checkpoint: bool = False):
        """
        Sauvegarde hybride : Fichier .pt local (fiable) + Métadonnées dans Cloud SQL.
        """
        try:
            self.current_epoch += 1
            version_tag = f"v{self.current_epoch}.0{'_DREAM' if is_dream_checkpoint else ''}"
            filename = f"checkpoint_{version_tag}.pt"
            file_path = self.checkpoint_dir / filename

            # 1. Sauvegarde locale des poids (100% fiable, pas de corruption binaire SQL)
            checkpoint_data = {
                'epoch': self.current_epoch,
                'model_state_dict': self.model.state_dict(),
                'optimizer_state_dict': self.optimizer.state_dict(),
                'total_rounds_trained': self.total_rounds_trained,
                'is_dream': is_dream_checkpoint
            }
            torch.save(checkpoint_data, file_path)
            logger.debug(f"💾 Poids sauvegardés localement : {file_path}")

            # 2. Sauvegarde des métadonnées dans Cloud SQL
            async with get_session() as session:
                checkpoint = ModelCheckpointTable(
                    version=version_tag,
                    epoch=self.current_epoch,
                    total_rounds_trained=self.total_rounds_trained,
                    accuracy_score=float(accuracy) if accuracy is not None else 0.0,
                    loss_value=float(loss) if loss is not None else 0.0,
                    checkpoint_path=filename
                )
                session.add(checkpoint)
                await session.commit()

            dream_msg = " (Phase de Rêve)" if is_dream_checkpoint else ""
            logger.success(f"✅ Checkpoint HYBRIDE sauvé : {version_tag} | Epoch {self.current_epoch} | Rounds: {self.total_rounds_trained}{dream_msg}")
            self._checkpoint_file_path = file_path

            # Nettoyage des anciens checkpoints locaux (garde les 3 derniers)
            self._cleanup_old_local_checkpoints()

        except Exception as e:
            logger.error(f"❌ ÉCHEC CRITIQUE sauvegarde checkpoint : {e}", exc_info=True)

    async def load_latest_checkpoint(self) -> bool:
        """
        Charge le dernier checkpoint via métadonnées SQL, puis récupère les poids du fichier local.
        🚀 NOUVEAU : Chargement robuste avec strict=False pour gérer les anciens checkpoints.
        """
        try:
            async with get_session() as session:
                stmt = select(ModelCheckpointTable).order_by(
                    desc(ModelCheckpointTable.created_at)
                ).limit(1)

                result = await session.execute(stmt)
                latest = result.scalar_one_or_none()

                if latest and latest.checkpoint_path:
                    filename = latest.checkpoint_path
                    file_path = self.checkpoint_dir / filename

                    if file_path.exists():
                        # Chargement PyTorch robuste
                        checkpoint_data = torch.load(file_path, map_location=torch.device('cpu'), weights_only=False)

                        # 🚀 NOUVEAU : Chargement avec strict=False pour gérer les anciens checkpoints
                        # Cela permet de charger un checkpoint qui n'a pas les nouveaux modules
                        # (raw_prediction_head, combination_weight, etc.)
                        try:
                            # Essai 1 : Chargement strict (normal)
                            self.model.load_state_dict(checkpoint_data['model_state_dict'], strict=True)
                            logger.debug("✅ Chargement strict réussi (checkpoint compatible)")
                        except (RuntimeError, KeyError) as e:
                            # Essai 2 : Chargement non-strict (anciens checkpoints)
                            logger.warning(f"⚠️ Checkpoint ancien détecté, chargement partiel : {e}")

                            # Charger uniquement les paramètres qui correspondent
                            missing_keys, unexpected_keys = self.model.load_state_dict(
                                checkpoint_data['model_state_dict'],
                                strict=False
                            )

                            if missing_keys:
                                logger.info(f"🆕 Nouveaux modules initialisés aléatoirement : {len(missing_keys)} clés")
                                logger.debug(f"   Clés manquantes : {missing_keys[:5]}...")  # Afficher les 5 premières

                            if unexpected_keys:
                                logger.warning(f"⚠️ Clés obsolètes ignorées : {len(unexpected_keys)} clés")
                                logger.debug(f"   Clés inattendues : {unexpected_keys[:5]}...")

                        # Charger l'optimiseur (peut aussi échouer si structure différente)
                        try:
                            self.optimizer.load_state_dict(checkpoint_data['optimizer_state_dict'])
                            logger.debug("✅ Optimiseur restauré")
                        except (RuntimeError, KeyError, ValueError) as e:
                            logger.warning(f"⚠️ Optimiseur non restauré (structure différente) : {e}")
                            logger.info("🔄 Optimiseur réinitialisé avec paramètres actuels")

                        self.current_epoch = checkpoint_data['epoch']
                        self.total_rounds_trained = checkpoint_data.get('total_rounds_trained', 0)

                        dream_msg = " (Phase de Rêve)" if checkpoint_data.get('is_dream', False) else ""
                        logger.success(f"🧠 Cerveau restauré depuis disque : {latest.version} (Epoch {latest.epoch}){dream_msg} | Rounds: {self.total_rounds_trained}")
                        self._checkpoint_file_path = file_path
                        return True
                    else:
                        logger.warning(f"⚠️ Fichier local {filename} introuvable. Fallback Tabula Rasa.")
                        return False
                else:
                    logger.warning("⚠️ Aucun checkpoint trouvé. Initialisation Tabula Rasa.")
                    return False

        except Exception as e:
            logger.error(f"❌ ÉCHEC CRITIQUE chargement checkpoint : {e}", exc_info=True)
            logger.warning("⚠️ Fallback : Modèle initialisé à zéro.")
            return False

    def _cleanup_old_local_checkpoints(self, keep_last: int = 3):
        """Nettoie les anciens fichiers .pt pour ne pas saturer le disque."""
        try:
            files = sorted(self.checkpoint_dir.glob("checkpoint_*.pt"), key=os.path.getmtime)
            if len(files) > keep_last:
                for old_file in files[:-keep_last]:
                    old_file.unlink()
                    logger.debug(f"🗑️ Nettoyé ancien checkpoint : {old_file.name}")
        except Exception as e:
            logger.warning(f"⚠️ Échec du nettoyage des checkpoints : {e}")

    def get_model(self) -> LuckyJetPredictor:
        return self.model

    def get_optimizer(self) -> torch.optim.Optimizer:
        return self.optimizer