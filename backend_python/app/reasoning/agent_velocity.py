import torch
import torch.nn as nn
import torch.nn.functional as F
import math
from loguru import logger

class AgentVelocity(nn.Module):
    """
    Sage Velocity : Analyse anomalies de latence et corrélations temporelles.
    CORRECTION v2.2 : Initialisation avec biais positif pour éviter le figement à 1.0x
    """
    def __init__(self):
        super().__init__()
        # Réseau pour détection d'anomalies
        self.anomaly_net = nn.Sequential(
            nn.Linear(5, 32),
            nn.GELU(),
            nn.LayerNorm(32),
            nn.Linear(32, 16),
            nn.GELU(),
            nn.Linear(16, 1)
        )

        # Réseau pour prédiction basée sur anomalies
        self.prediction_net = nn.Sequential(
            nn.Linear(7, 32),
            nn.GELU(),
            nn.LayerNorm(32),
            nn.Linear(32, 16),
            nn.GELU(),
            nn.Linear(16, 1)
        )

        # 🚀 CORRECTION : Initialisation Xavier
        self._init_weights()

        # 🚀 CORRECTION CRITIQUE : Biais positif pour forcer des prédictions > 1.0x
        with torch.no_grad():
            self.prediction_net[-1].bias.fill_(math.log(2.0))  # ~0.693
            self.prediction_net[-1].weight.normal_(0, 0.05)

        logger.info("⚡ Agent Velocity (v2.2) - Anomaly & Temporal Correlation avec biais positif")

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
        recent_latencies = sequence[:, -16:, 1]
        recent_log_crashes = sequence[:, -16:, 0]
        recent_crashes = torch.exp(recent_log_crashes) - 1.0

        # 2. Détection des chocs de latence
        lat_mean = torch.mean(recent_latencies, dim=1, keepdim=True)
        lat_std = torch.clamp(torch.std(recent_latencies, dim=1, keepdim=True), min=0.1)
        current_lat_zscore = (recent_latencies[:, -1:] - lat_mean) / lat_std

        # 3. Corrélation Latence/Crash
        lat_centered = recent_latencies - lat_mean
        crash_mean = torch.mean(recent_crashes, dim=1, keepdim=True)
        crash_centered = recent_crashes - crash_mean
        crash_std = torch.clamp(torch.std(recent_crashes, dim=1, keepdim=True), min=0.1)

        covariance = torch.mean(lat_centered * crash_centered, dim=1, keepdim=True)
        correlation_score = torch.tanh(covariance / (lat_std * crash_std))

        # 4. Score d'anomalie via réseau neuronal
        anomaly_features = torch.cat([
            current_lat_zscore, correlation_score, lat_mean, lat_std, crash_std
        ], dim=1)

        raw_anomaly_score = self.anomaly_net(anomaly_features)
        anomaly_score = torch.sigmoid(raw_anomaly_score)

        # 5. Calcul vectorisé de time_since_high
        high_mask = (recent_crashes > 5.0).float()  # [batch, 16]
        indices = torch.arange(15, -1, -1, device=device, dtype=torch.float32).unsqueeze(0)  # [1, 16]
        indices = indices.expand(batch_size, -1)  # [batch, 16]
        masked_indices = indices * high_mask  # [batch, 16]
        max_indices = torch.max(masked_indices, dim=1, keepdim=True)[0]  # [batch, 1]

        time_since_high = torch.where(
            max_indices > 0,
            max_indices,
            torch.full_like(max_indices, 16.0)
        )

        # 6. Autres features temporelles
        crash_frequency = (recent_crashes > 2.0).float().mean(dim=1, keepdim=True)
        avg_crash_size = torch.mean(recent_crashes, dim=1, keepdim=True)
        max_crash_recent = torch.max(recent_crashes, dim=1, keepdim=True)[0]

        # Pattern de purge
        low_crashes = (recent_crashes < 1.5).float()
        purge_pattern = torch.mean(low_crashes, dim=1, keepdim=True)

        # 7. Prédiction via réseau neuronal
        prediction_features = torch.cat([
            anomaly_score, time_since_high, crash_frequency,
            avg_crash_size, max_crash_recent, purge_pattern, correlation_score
        ], dim=1)

        velocity_prediction_log = self.prediction_net(prediction_features)
        velocity_prediction = torch.clamp(torch.exp(velocity_prediction_log), min=1.0)

        # 8. Confiance
        velocity_confidence = torch.sigmoid(
            anomaly_score * 2.0 +
            (1.0 - purge_pattern) * 0.5
        )

        return {
            'velocity_confidence': velocity_confidence,
            'velocity_prediction': velocity_prediction,
            'anomaly_score': anomaly_score,
            'correlation_score': correlation_score
        }

    def analyze(self, sequence: torch.Tensor, global_state: torch.Tensor) -> dict:
        return self.forward(sequence, global_state)