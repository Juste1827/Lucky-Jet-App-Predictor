import torch
import torch.nn as nn
import torch.nn.functional as F
import math
from loguru import logger

class AgentDrift(nn.Module):
    """
    Sage Drift : Analyse momentum et tendances via statistiques différentielles.
    CORRECTION v2.2 : Initialisation avec biais positif pour éviter le figement à 1.0x
    """
    def __init__(self):
        super().__init__()
        # Paramètres apprenables pour pondérer différents indicateurs
        self.velocity_weight = nn.Parameter(torch.tensor(1.0))
        self.acceleration_weight = nn.Parameter(torch.tensor(0.5))
        self.trend_weight = nn.Parameter(torch.tensor(0.3))

        # Réseau pour prédiction basée sur momentum
        self.momentum_net = nn.Sequential(
            nn.Linear(6, 32),  # velocity, acceleration, trend + 3 stats
            nn.GELU(),
            nn.LayerNorm(32),
            nn.Linear(32, 16),
            nn.GELU(),
            nn.Linear(16, 1)  # Prédiction log
        )

        # 🚀 CORRECTION : Initialisation Xavier
        self._init_weights()

        # 🚀 CORRECTION CRITIQUE : Biais positif pour forcer des prédictions > 1.0x
        with torch.no_grad():
            self.momentum_net[-1].bias.fill_(math.log(2.0))  # ~0.693
            self.momentum_net[-1].weight.normal_(0, 0.05)

        logger.info("📈 Agent Drift (v2.2) - Momentum & Trend avec biais positif")

    def _init_weights(self):
        """Initialisation Xavier pour tous les réseaux"""
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.xavier_uniform_(m.weight)
                if m.bias is not None:
                    nn.init.zeros_(m.bias)

    def forward(self, sequence: torch.Tensor, global_state: torch.Tensor) -> dict:
        batch_size = sequence.shape[0]
        device = sequence.device

        # 1. Extraction
        recent_log_crashes = sequence[:, -16:, 0]
        recent_crashes = torch.exp(recent_log_crashes) - 1.0

        # 2. Calcul du Drift (Vitesse) - pente de régression linéaire
        t = torch.arange(16, device=device, dtype=torch.float32).unsqueeze(0).expand(batch_size, -1)
        t_mean = t.mean(dim=1, keepdim=True)
        crash_mean = recent_crashes.mean(dim=1, keepdim=True)

        covariance = torch.mean((t - t_mean) * (recent_crashes - crash_mean), dim=1, keepdim=True)
        t_variance = torch.var(t, dim=1, keepdim=True) + 1e-6
        velocity = covariance / t_variance

        # 3. Calcul de l'Accélération (dérivée seconde)
        diffs = torch.diff(recent_crashes, dim=1)
        accels = torch.diff(diffs, dim=1)
        if accels.shape[1] > 0:
            acceleration = torch.mean(accels, dim=1, keepdim=True)
        else:
            acceleration = torch.zeros_like(velocity)

        # 4. Détection de tendance longue
        if sequence.shape[1] >= 32:
            long_crashes = torch.exp(sequence[:, -32:, 0]) - 1.0
            long_mean = long_crashes.mean(dim=1, keepdim=True)
            trend = (recent_crashes.mean(dim=1, keepdim=True) - long_mean) / (long_mean + 1e-6)
        else:
            trend = torch.zeros_like(velocity)

        # 5. Statistiques supplémentaires
        volatility = torch.std(recent_crashes, dim=1, keepdim=True)
        max_recent = torch.max(recent_crashes, dim=1, keepdim=True)[0]
        min_recent = torch.min(recent_crashes, dim=1, keepdim=True)[0]
        range_recent = max_recent - min_recent

        # 6. Momentum score combiné
        momentum_score = torch.tanh(
            velocity * self.velocity_weight +
            acceleration * self.acceleration_weight +
            trend * self.trend_weight
        )

        # 7. Prédiction via réseau neuronal
        momentum_features = torch.cat([
            velocity, acceleration, trend, volatility, max_recent, range_recent
        ], dim=1)  # [batch, 6]

        drift_prediction_log = self.momentum_net(momentum_features)
        drift_prediction = torch.clamp(torch.exp(drift_prediction_log), min=1.0)

        # 8. Confiance basée sur la cohérence des signaux
        stacked_signals = torch.cat([velocity, acceleration, trend], dim=1)
        signal_agreement = 1.0 - torch.std(stacked_signals, dim=1, keepdim=True)
        drift_confidence = torch.sigmoid(signal_agreement)

        return {
            'drift_confidence': drift_confidence,
            'drift_prediction': drift_prediction,
            'momentum_score': momentum_score,
            'velocity': velocity,
            'acceleration': acceleration
        }

    def analyze(self, sequence: torch.Tensor, global_state: torch.Tensor) -> dict:
        return self.forward(sequence, global_state)