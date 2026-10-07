"""
Apprentissage en ligne (Online Learning)
Partie 4 du Master Blueprint: Cycle d'auto-apprentissage et Backpropagation
Version v2.1 : Ajout de logs de diagnostic pour monitorer la nouvelle architecture
"""

import torch
import torch.nn as nn
from loguru import logger
from typing import List, Tuple, Dict, Any
import numpy as np

from app.brain.neural_engine import LuckyJetPredictor


class OnlineLearner:
    """
    Moteur d'apprentissage continu avec mini-batch.
    Utilise la Huber Loss pour la robustesse aux outliers et la rétropropagation
    pour l'ajustement des poids en temps réel.
    """

    def __init__(self, model: LuckyJetPredictor, optimizer: torch.optim.Optimizer, learning_rate: float = 1e-3):
        self.model = model
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model.to(self.device)

        # 🛑 CORRECTION CRITIQUE N°1 : Utiliser l'optimiseur fourni par ModelCheckpoint
        # Cela préserve le momentum (état Adam) lors du chargement d'un checkpoint.
        self.optimizer = optimizer

        # S'assurer que l'optimiseur est bien sur le bon device
        for state in self.optimizer.state.values():
            for k, v in state.items():
                if isinstance(v, torch.Tensor):
                    state[k] = v.to(self.device)

        self.criterion = nn.HuberLoss(delta=1.0) # Robuste aux jackpots

        self.batch_size = 32
        self.context_window = 64
        self.total_rounds_trained = 0

        logger.info(f"🧠 Online Learner initialisé sur {self.device} | lr={learning_rate} | batch={self.batch_size} (Optimiseur lié)")

    def prepare_inference_sequence(self, crash_history: List[Dict[str, Any]]) -> torch.Tensor:
        """
        Prépare une SEULE séquence pour la prédiction en temps réel (Inference).
        """
        if len(crash_history) < self.context_window:
            padding_size = self.context_window - len(crash_history)

            # 🛑 CORRECTION CRITIQUE N°2 : Ne JAMAIS pad avec crash_history[0].
            # Utiliser des valeurs neutres pour ne pas créer de faux patterns (ex: trente 10.0x d'affilée).
            neutral_crash = {'crash_value': 1.0, 'latency_ms': 0.0, 'delta_time_ms': 0.0}
            padding = [neutral_crash] * padding_size
            crash_history = padding + crash_history

        recent = crash_history[-self.context_window:]
        features = []
        for crash in recent:
            # Log-transform pour stabiliser la variance
            log_crash = np.log(float(crash['crash_value']) + 1.0)
            latency_norm = min(float(crash.get('latency_ms', 0)) / 1000.0, 5.0)
            delta_norm = min(float(crash.get('delta_time_ms', 0)) / 60000.0, 1.0)
            features.append([log_crash, latency_norm, delta_norm])

        # [1, 64, 3] et déplacement sur le bon device
        sequence = torch.tensor(features, dtype=torch.float32, device=self.device).unsqueeze(0)
        return sequence

    def prepare_training_batch(self, crash_history: List[Dict[str, Any]]) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Prépare des séquences d'entraînement (X) et leurs cibles (y) à partir de l'historique.
        Crée des fenêtres glissantes pour maximiser les données d'apprentissage.
        """
        min_required = self.context_window + 1
        if len(crash_history) < min_required:
            return torch.empty(0, device=self.device), torch.empty(0, device=self.device)

        X_list = []
        y_list = []

        # Fenêtre glissante : génère (N - 64) exemples d'entraînement
        for i in range(len(crash_history) - self.context_window):
            window = crash_history[i : i + self.context_window]
            target_crash = float(crash_history[i + self.context_window]['crash_value'])

            features = []
            for crash in window:
                log_crash = np.log(float(crash['crash_value']) + 1.0)
                latency_norm = min(float(crash.get('latency_ms', 0)) / 1000.0, 5.0)
                delta_norm = min(float(crash.get('delta_time_ms', 0)) / 60000.0, 1.0)
                features.append([log_crash, latency_norm, delta_norm])

            X_list.append(features)
            y_list.append([target_crash])

        X_batch = torch.tensor(X_list, dtype=torch.float32, device=self.device)
        y_batch = torch.tensor(y_list, dtype=torch.float32, device=self.device)

        return X_batch, y_batch

    async def train_step(self, X_batch: torch.Tensor, y_batch: torch.Tensor) -> float:
        """
        Exécute une étape complète de rétropropagation (Backpropagation).
        """
        if X_batch.numel() == 0:
            return 0.0

        self.model.train()
        self.optimizer.zero_grad()

        # 1. Forward pass
        outputs = self.model(X_batch)
        predictions = outputs['target_score']

        # 2. Calcul de la Loss (Huber)
        loss = self.criterion(predictions, y_batch)

        # 3. Backward pass (Rétropropagation)
        loss.backward()

        # 4. Gradient clipping pour éviter l'explosion des gradients (crucial en online learning)
        torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)

        # 5. Mise à jour des poids
        self.optimizer.step()

        # 6. Mise à jour du compteur global
        self.total_rounds_trained += len(X_batch)

        # 🚀 NOUVEAU : Logs de diagnostic pour monitorer la nouvelle architecture
        # Afficher les métriques internes tous les 100 batches pour comprendre l'équilibre
        if self.total_rounds_trained % (100 * self.batch_size) < self.batch_size:
            with torch.no_grad():
                # Logs pour comprendre comment l'IA utilise sa liberté
                sample_idx = 0  # Premier échantillon du batch
                meta_score = outputs['meta_score'][sample_idx].item()
                raw_score = outputs['raw_score'][sample_idx].item()
                combination_weight = outputs['combination_weight']

                logger.info(
                    f"📊 Diagnostic Online Learning | "
                    f"Meta Score: {meta_score:.2f}x | "
                    f"Raw Score: {raw_score:.2f}x | "
                    f"Combination Weight: {combination_weight:.2f} | "
                    f"Final Prediction: {predictions[sample_idx].item():.2f}x | "
                    f"Target: {y_batch[sample_idx].item():.2f}x"
                )

        return loss.item()

    async def evaluate_prediction(self, predicted: float, actual: float) -> Dict[str, Any]:
        """Évalue la qualité d'une prédiction après le crash réel."""
        error = abs(predicted - actual)
        relative_error = error / (actual + 1e-6)
        # Objectif rentabilité : la prédiction est <= au crash réel, OU l'erreur relative est très faible
        was_accurate = (predicted <= actual) or (relative_error < 0.2)

        return {
            'error': round(error, 4),
            'relative_error': round(relative_error, 4),
            'was_accurate': was_accurate
        }