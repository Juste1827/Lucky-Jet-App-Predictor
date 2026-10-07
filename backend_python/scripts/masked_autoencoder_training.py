"""
Phase de Rêve (Masked Autoencoding + Adversarial Training)
Version v3.1 - Quantile Loss Asymétrique + Warm-up + Bruit Progressif

Fonctionnement :
- Charge 3000 tours historiques depuis PostgreSQL
- Masque 20% des séquences
- Injecte du bruit adversarial progressif (10% → 30%)
- Quantile Loss asymétrique : pénalise 2.3x plus les prédictions TROP HAUTES
- Warm-up 5 époques + Cosine Decay
- Validation chronologique 80/20
- Early stopping patience 20
- Exécution automatique toutes les heures
"""

import torch
import torch.nn as nn
import asyncio
import numpy as np
import random
import copy
import time
import math
from loguru import logger
from typing import List, Dict, Any
from sqlalchemy import select, desc

from app.memory.cloud_sql import get_session, RawCrash
from app.brain.model_manager import ModelCheckpoint


# ==========================
# CONFIGURATION GLOBALE
# ==========================
RUN_CONTINUOUS = True
INTERVAL_SECONDS = 3600  # 1 heure

DREAM_EPOCHS = 150
DATA_LIMIT = 3000
LEARNING_RATE = 5e-4       # 🚀 Augmenté de 1e-4 à 5e-4
MIN_LR = 1e-6
WARMUP_EPOCHS = 5

MASK_RATIO = 0.20
NOISE_MIN = 0.10           # 🚀 Bruit progressif : commence à 10%
NOISE_MAX = 0.30           # 🚀 Bruit progressif : monte à 30%
VALIDATION_SPLIT = 0.20

EARLY_STOPPING_PATIENCE = 20  # 🚀 Augmenté de 15 à 20
EARLY_STOPPING_MIN_DELTA = 1e-4

BATCH_SIZE = 32
CONTEXT_WINDOW = 64
MASK_VALUE = 0.0

# 🚀 NOUVEAU : Quantile pour la loss asymétrique
# 0.30 signifie : sur-prédiction pénalisée 2.3x plus que sous-prédiction
# Ajuster entre 0.20 (très conservateur) et 0.40 (plus agressif)
QUANTILE = 0.30


class AdversarialNoiseGenerator:
    """
    Génère du bruit adversarial pour forcer l'IA à distinguer
    les vrais signaux des faux.
    """

    @staticmethod
    def inject_fake_jackpot(features: np.ndarray) -> np.ndarray:
        """Insère un crash 50x-100x suivi de 10 crashs 1.0x-1.5x."""
        seq = features.copy()
        if len(seq) > 15:
            idx = random.randint(0, len(seq) - 12)
            seq[idx, 0] = np.log(random.uniform(50.0, 100.0) + 1.0)
            for i in range(1, 11):
                if idx + i < len(seq):
                    seq[idx + i, 0] = np.log(random.uniform(1.0, 1.5) + 1.0)
        return seq

    @staticmethod
    def inject_fake_purge(features: np.ndarray) -> np.ndarray:
        """Insère 15 crashs 1.0x-1.2x suivis d'un crash 20x+."""
        seq = features.copy()
        if len(seq) > 16:
            idx = random.randint(0, len(seq) - 17)
            for i in range(15):
                seq[idx + i, 0] = np.log(random.uniform(1.0, 1.2) + 1.0)
            seq[idx + 15, 0] = np.log(random.uniform(20.0, 50.0) + 1.0)
        return seq

    @staticmethod
    def inject_random_rng(features: np.ndarray) -> np.ndarray:
        """Remplace 30% des crashs par des valeurs aléatoires."""
        seq = features.copy()
        for i in range(len(seq)):
            if random.random() < 0.30:
                if random.random() < 0.80:
                    seq[i, 0] = np.log(random.uniform(1.0, 3.0) + 1.0)
                else:
                    seq[i, 0] = np.log(random.uniform(3.0, 50.0) + 1.0)
        return seq

    @staticmethod
    def inject_abnormal_latency(features: np.ndarray) -> np.ndarray:
        """Injecte des latences anormales 500ms-2000ms."""
        seq = features.copy()
        for i in range(len(seq)):
            if random.random() < 0.20:
                seq[i, 1] = random.uniform(0.5, 2.0)
        return seq

    @classmethod
    def apply_noise(cls, features: np.ndarray, injection_rate: float = 0.30) -> np.ndarray:
        """Applique un type de bruit aléatoire à une séquence."""
        if random.random() > injection_rate:
            return features

        noise_type = random.choice(["jackpot", "purge", "rng", "latency"])

        if noise_type == "jackpot":
            return cls.inject_fake_jackpot(features)
        elif noise_type == "purge":
            return cls.inject_fake_purge(features)
        elif noise_type == "rng":
            return cls.inject_random_rng(features)
        elif noise_type == "latency":
            return cls.inject_abnormal_latency(features)

        return features


class DreamPhaseTrainer:
    """
    Entraîneur de la Phase de Rêve v3.1 :
    - Quantile Loss asymétrique
    - Warm-up + Cosine Decay
    - Bruit adversarial progressif
    - Validation chronologique 80/20
    - Early stopping
    """

    def __init__(self, model_manager: ModelCheckpoint, learning_rate: float = LEARNING_RATE):
        self.model_manager = model_manager
        self.model = model_manager.get_model()
        self.optimizer = model_manager.get_optimizer()

        # 🚀 Learning rate de base (sera modulé par warm-up + cosine)
        self.base_lr = learning_rate
        for param_group in self.optimizer.param_groups:
            param_group["lr"] = learning_rate

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)

        # Déplacer les états de l'optimiseur sur le bon device
        for state in self.optimizer.state.values():
            for k, v in state.items():
                if isinstance(v, torch.Tensor):
                    state[k] = v.to(self.device)

        self.context_window = CONTEXT_WINDOW
        self.mask_ratio = MASK_RATIO
        self.mask_value = MASK_VALUE
        self.batch_size = BATCH_SIZE
        self.validation_split = VALIDATION_SPLIT
        self.patience = EARLY_STOPPING_PATIENCE
        self.min_delta = EARLY_STOPPING_MIN_DELTA
        self.quantile = QUANTILE

        self.noise_generator = AdversarialNoiseGenerator()

        logger.info(
            f"🌙 Dream Phase Trainer v3.1 initialisé sur {self.device} | "
            f"Mask: {self.mask_ratio * 100:.0f}% | "
            f"LR: {learning_rate} | "
            f"Quantile: {self.quantile} | "
            f"Batch: {self.batch_size}"
        )

    def _get_lr(self, epoch: int, total_epochs: int) -> float:
        """
        🚀 NOUVEAU : Schedule de learning rate manuel.
        - Warm-up linéaire pendant WARMUP_EPOCHS
        - Cosine decay ensuite
        """
        if epoch <= WARMUP_EPOCHS:
            # Warm-up linéaire : de 10% du LR à 100%
            return self.base_lr * max(0.1, epoch / WARMUP_EPOCHS)
        else:
            # Cosine decay
            progress = (epoch - WARMUP_EPOCHS) / max(1, total_epochs - WARMUP_EPOCHS)
            return MIN_LR + 0.5 * (self.base_lr - MIN_LR) * (1 + math.cos(math.pi * progress))

    def _loss(self, predictions: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        """
        🚀 NOUVEAU : Quantile Loss asymétrique en espace log.

        Objectif : la prédiction doit être INFÉRIEURE au crash réel.
        - pred < target (on gagne) : petite pénalité
        - pred > target (on perd)  : FORTE pénalité (2.3x avec quantile=0.30)

        En espace log1p pour gérer les gros crashs (100x, 500x).
        """
        log_preds = torch.log1p(predictions)
        log_targets = torch.log1p(targets)

        error = log_targets - log_preds

        loss = torch.where(
            error >= 0,
            # pred < target : on gagne, petite pénalité pour encourager à prédire plus haut
            self.quantile * error,
            # pred > target : on perd, FORTE pénalité
            (self.quantile - 1.0) * error
        )

        return loss.mean()

    async def load_dream_data(self, limit: int = DATA_LIMIT) -> List[Dict[str, Any]]:
        """Charge les N derniers tours depuis Cloud SQL."""
        logger.info(f"💾 Chargement de {limit} tours pour la phase de rêve...")

        try:
            async with get_session() as session:
                stmt = select(RawCrash).order_by(desc(RawCrash.id)).limit(limit)
                result = await session.execute(stmt)
                crashes = result.scalars().all()

                # Ordre chronologique ancien -> récent
                crashes.reverse()

                data = [
                    {
                        "crash_value": float(c.crash_value),
                        "latency_ms": float(c.latency_ms or 0),
                        "delta_time_ms": float(c.delta_time_ms or 0),
                    }
                    for c in crashes
                ]

                logger.success(f"✅ {len(data)} tours chargés avec succès.")
                return data

        except Exception as e:
            logger.error(f"❌ Erreur lors du chargement des données de rêve : {e}")
            return []

    def create_sequences(self, data: List[Dict[str, Any]]):
        """Crée les séquences propres X et y."""
        if len(data) < self.context_window + 1:
            logger.warning("⚠️ Pas assez de données pour créer des séquences de rêve.")
            return torch.empty(0), torch.empty(0)

        X_list = []
        y_list = []

        for i in range(len(data) - self.context_window):
            window = data[i : i + self.context_window]
            target_crash = float(data[i + self.context_window]["crash_value"])

            features = []
            for crash in window:
                log_crash = np.log(float(crash["crash_value"]) + 1.0)
                latency_norm = min(float(crash.get("latency_ms", 0)) / 1000.0, 5.0)
                delta_norm = min(float(crash.get("delta_time_ms", 0)) / 60000.0, 1.0)
                features.append([log_crash, latency_norm, delta_norm])

            X_list.append(features)
            y_list.append([target_crash])

        # Conversion via np.asarray pour éviter le warning PyTorch
        X = torch.tensor(np.asarray(X_list, dtype=np.float32), device=self.device)
        y = torch.tensor(np.asarray(y_list, dtype=np.float32), device=self.device)

        logger.info(f"🧩 Séquences créées : {X.shape[0]} fenêtres de {self.context_window} tours")
        return X, y

    def _chronological_split(self, X: torch.Tensor, y: torch.Tensor):
        """Split chronologique 80/20 sans fuite temporelle."""
        n = X.shape[0]
        if n == 0:
            return X, y, X, y

        split_idx = int(n * (1.0 - self.validation_split))
        split_idx = max(1, min(n - 1, split_idx))

        X_train = X[:split_idx]
        y_train = y[:split_idx]
        X_val = X[split_idx:]
        y_val = y[split_idx:]

        logger.info(
            f"📊 Split chronologique : Train={X_train.shape[0]} | Validation={X_val.shape[0]}"
        )

        return X_train, y_train, X_val, y_val

    def _make_batches(self, X: torch.Tensor, y: torch.Tensor, shuffle: bool = True):
        """Crée des mini-batches."""
        n = X.shape[0]
        if n == 0:
            return []

        if shuffle:
            indices = torch.randperm(n, device=self.device)
        else:
            indices = torch.arange(n, device=self.device)

        batches = []
        for start in range(0, n, self.batch_size):
            batch_idx = indices[start : start + self.batch_size]
            batches.append((X[batch_idx], y[batch_idx]))

        return batches

    def _augment_batch(self, X_batch: torch.Tensor, epoch: int, total_epochs: int) -> torch.Tensor:
        """
        Applique bruit adversarial PROGRESSIF + masquage 20%.
        Le bruit commence à 10% et monte à 30% au fil des époques.
        """
        # 🚀 Bruit progressif
        noise_rate = NOISE_MIN + (NOISE_MAX - NOISE_MIN) * (epoch / max(1, total_epochs))

        X_np = X_batch.detach().cpu().numpy()
        augmented = np.empty_like(X_np)

        for i, seq in enumerate(X_np):
            augmented[i] = self.noise_generator.apply_noise(seq, injection_rate=noise_rate)

        X_aug = torch.tensor(augmented, dtype=torch.float32, device=self.device)

        # Masquage de 20% des pas de temps
        mask = torch.rand(X_aug.shape[0], self.context_window, device=self.device) < self.mask_ratio
        mask_3d = mask.unsqueeze(-1).expand_as(X_aug)

        X_masked = torch.where(
            mask_3d,
            torch.full_like(X_aug, self.mask_value),
            X_aug
        )

        return X_masked

    def _evaluate(self, X_val: torch.Tensor, y_val: torch.Tensor):
        """
        Évaluation sur données propres, sans bruit ni exploration noise.
        Retourne : (loss, accuracy, stats_dict)
        """
        if X_val.numel() == 0:
            return 0.0, 0.0, {}

        self.model.eval()

        # Désactiver le bruit d'exploration pendant validation
        old_noise = getattr(self.model, "exploration_noise_std", 0.0)
        if hasattr(self.model, "exploration_noise_std"):
            self.model.exploration_noise_std = 0.0

        total_loss = 0.0
        total_samples = 0
        successful = 0
        all_preds = []
        all_targets = []

        batches = self._make_batches(X_val, y_val, shuffle=False)

        with torch.no_grad():
            for X_batch, y_batch in batches:
                outputs = self.model(X_batch)
                preds = outputs["target_score"]

                loss = self._loss(preds, y_batch)

                total_loss += loss.item() * X_batch.shape[0]
                total_samples += X_batch.shape[0]
                successful += (preds <= y_batch).sum().item()

                all_preds.append(preds.cpu())
                all_targets.append(y_batch.cpu())

        # Restaurer le bruit d'exploration
        if hasattr(self.model, "exploration_noise_std"):
            self.model.exploration_noise_std = old_noise

        self.model.train()

        if total_samples == 0:
            return 0.0, 0.0, {}

        avg_loss = total_loss / total_samples
        accuracy = (successful / total_samples) * 100.0

        # 🚀 NOUVEAU : Statistiques sur la distribution des prédictions
        all_preds = torch.cat(all_preds, dim=0)
        all_targets = torch.cat(all_targets, dim=0)

        stats = {
            "pred_mean": all_preds.mean().item(),
            "pred_std": all_preds.std().item(),
            "pred_min": all_preds.min().item(),
            "pred_max": all_preds.max().item(),
            "target_mean": all_targets.mean().item(),
            "target_max": all_targets.max().item(),
        }

        return avg_loss, accuracy, stats

    async def run(self, epochs: int = DREAM_EPOCHS, data_limit: int = DATA_LIMIT):
        """Orchestre la phase de rêve complète."""
        logger.info("🌌 DÉBUT DE LA PHASE DE RÊVE v3.1 (Quantile + Warm-up + Progressive Noise)...")

        data = await self.load_dream_data(limit=data_limit)
        if not data:
            logger.warning("⚠️ Aucune donnée pour la phase de rêve.")
            return

        X, y = self.create_sequences(data)
        if X.numel() == 0:
            logger.warning("⚠️ Séquences vides. Arrêt de la phase de rêve.")
            return

        X_train, y_train, X_val, y_val = self._chronological_split(X, y)

        best_val_loss = float("inf")
        patience_counter = 0
        best_state = copy.deepcopy(self.model.state_dict())
        best_epoch = 0

        for epoch in range(1, epochs + 1):
            # 🚀 NOUVEAU : Warm-up + Cosine Decay manuel
            current_lr = self._get_lr(epoch, epochs)
            for param_group in self.optimizer.param_groups:
                param_group["lr"] = current_lr

            self.model.train()
            total_train_loss = 0.0
            total_train_samples = 0

            train_batches = self._make_batches(X_train, y_train, shuffle=True)

            for X_batch, y_batch in train_batches:
                # 🚀 Bruit progressif selon l'époque
                X_aug = self._augment_batch(X_batch, epoch=epoch, total_epochs=epochs)

                self.optimizer.zero_grad()
                outputs = self.model(X_aug)
                preds = outputs["target_score"]

                loss = self._loss(preds, y_batch)

                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
                self.optimizer.step()

                total_train_loss += loss.item() * X_batch.shape[0]
                total_train_samples += X_batch.shape[0]

            train_loss = total_train_loss / max(1, total_train_samples)
            val_loss, val_accuracy, val_stats = self._evaluate(X_val, y_val)

            # Log avec distribution des prédictions
            pred_info = ""
            if val_stats:
                pred_info = (
                    f" | Pred: μ={val_stats['pred_mean']:.2f} "
                    f"σ={val_stats['pred_std']:.2f} "
                    f"[{val_stats['pred_min']:.2f}-{val_stats['pred_max']:.2f}] "
                    f"Target: μ={val_stats['target_mean']:.2f} "
                    f"max={val_stats['target_max']:.2f}"
                )

            logger.info(
                f"🌙 Rêve Epoch {epoch}/{epochs} | "
                f"LR: {current_lr:.2e} | "
                f"Train Loss: {train_loss:.4f} | "
                f"Val Loss: {val_loss:.4f} | "
                f"Val Accuracy: {val_accuracy:.2f}%"
                f"{pred_info}"
            )

            # Early stopping
            if val_loss < best_val_loss - self.min_delta:
                best_val_loss = val_loss
                patience_counter = 0
                best_state = copy.deepcopy(self.model.state_dict())
                best_epoch = epoch
                logger.success(
                    f"✅ Nouveau meilleur modèle | Val Loss: {val_loss:.4f} | "
                    f"Accuracy: {val_accuracy:.2f}%"
                )
            else:
                patience_counter += 1
                logger.info(f"⏳ Pas d'amélioration ({patience_counter}/{self.patience})")

                if patience_counter >= self.patience:
                    logger.warning(f"🛑 Early stopping déclenché après {epoch} époques.")
                    break

        # Restaurer le meilleur modèle
        self.model.load_state_dict(best_state)
        final_val_loss, final_val_accuracy, final_stats = self._evaluate(X_val, y_val)

        logger.success(
            f"🏁 Phase de rêve terminée | "
            f"Best Epoch: {best_epoch} | "
            f"Best Val Loss: {best_val_loss:.4f} | "
            f"Final Val Accuracy: {final_val_accuracy:.2f}%"
        )

        if final_stats:
            logger.info(
                f"📊 Distribution finale des prédictions : "
                f"μ={final_stats['pred_mean']:.2f} "
                f"σ={final_stats['pred_std']:.2f} "
                f"[{final_stats['pred_min']:.2f} - {final_stats['pred_max']:.2f}]"
            )

        # Mise à jour du compteur de tours entraînés
        self.model_manager.total_rounds_trained += data_limit

        logger.info("💾 Sauvegarde du meilleur modèle de rêve...")

        try:
            await self.model_manager.save_checkpoint(
                accuracy=final_val_accuracy,
                loss=final_val_loss,
                is_dream_checkpoint=True
            )
            logger.success("✅ Checkpoint DREAM sauvegardé avec succès.")
        except Exception as e:
            logger.error(f"❌ Erreur lors de la sauvegarde du checkpoint DREAM : {e}")


async def run_dream_cycle():
    """Exécute un cycle complet de Phase de Rêve."""
    logger.info("🚀 Lancement d'un cycle de Phase de Rêve v3.1...")

    manager = ModelCheckpoint()
    await manager.load_latest_checkpoint()

    trainer = DreamPhaseTrainer(
        model_manager=manager,
        learning_rate=LEARNING_RATE
    )

    await trainer.run(
        epochs=DREAM_EPOCHS,
        data_limit=DATA_LIMIT
    )

    logger.info("🛑 Fin du cycle de Phase de Rêve.")


async def main():
    """
    Point d'entrée.
    Si RUN_CONTINUOUS=True, lance une phase de rêve toutes les heures.
    """
    logger.info("🌙 Script Phase de Rêve v3.1 démarré.")

    if not RUN_CONTINUOUS:
        await run_dream_cycle()
        return

    while True:
        start_time = time.time()

        try:
            await run_dream_cycle()
        except Exception as e:
            logger.error(f"❌ Erreur critique pendant la Phase de Rêve : {e}", exc_info=True)

        elapsed = time.time() - start_time
        sleep_time = max(0.0, float(INTERVAL_SECONDS - elapsed))

        logger.info(
            f"⏱️ Cycle terminé en {elapsed:.0f}s. "
            f"Prochaine phase de rêve dans {sleep_time / 3600:.2f}h."
        )

        await asyncio.sleep(sleep_time)


if __name__ == "__main__":
    asyncio.run(main())