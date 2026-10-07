import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
import math
from loguru import logger

class AgentMemory(nn.Module):
    """
    Sage Memory : Analyse les patterns historiques via réseau neuronal profond.
    CORRECTION v2.2 : Initialisation avec biais positif pour éviter le figement à 1.0x
    """
    def __init__(self):
        super().__init__()
        # Réseau pour analyser les patterns et produire une prédiction absolue
        self.pattern_net = nn.Sequential(
            nn.Linear(16, 64),  # 16 derniers crashs log-transformés
            nn.GELU(),
            nn.LayerNorm(64),
            nn.Dropout(0.1),
            nn.Linear(64, 32),
            nn.GELU(),
            nn.Linear(32, 1)  # Prédiction log du prochain crash
        )

        # Réseau pour calculer la confiance
        self.confidence_net = nn.Sequential(
            nn.Linear(18, 32),  # 16 crashs + entropie + stabilité
            nn.GELU(),
            nn.Linear(32, 1),
            nn.Sigmoid()
        )

        # 🚀 CORRECTION : Initialisation Xavier pour de meilleurs gradients
        self._init_weights()

        # 🚀 CORRECTION CRITIQUE : Biais positif pour forcer des prédictions > 1.0x
        # exp(log(2.0)) = 2.0, donc le Sage démarre avec une prédiction de ~2.0x
        with torch.no_grad():
            self.pattern_net[-1].bias.fill_(math.log(2.0))  # ~0.693
            self.pattern_net[-1].weight.normal_(0, 0.05)  # Petits poids pour la sortie

        logger.info("🧠 Agent Memory (v2.2) - Pattern Recognition avec biais positif")

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

        # 1. Extraction des 16 derniers crashs log-transformés
        recent_log_crashes = sequence[:, -16:, 0]  # [batch, 16]
        recent_crashes = torch.exp(recent_log_crashes) - 1.0

        # 2. Entropie de Shannon (Stabilisée)
        scaled_logs = recent_log_crashes * 0.1
        probs = F.softmax(scaled_logs, dim=1)
        entropy = -torch.sum(probs * torch.log(probs + 1e-8), dim=1, keepdim=True)
        max_entropy = np.log(16)
        normalized_entropy = torch.clamp(entropy / max_entropy, 0.0, 1.0)

        # 3. Stabilité latente
        latent_norm = torch.norm(global_state, p=2, dim=1, keepdim=True)
        latent_stability = torch.clamp(latent_norm / 10.0, 0.0, 1.0)

        # 4. Prédiction absolue via réseau neuronal
        memory_prediction_log = self.pattern_net(recent_log_crashes)  # [batch, 1]

        # 5. Confiance via réseau neuronal
        confidence_input = torch.cat([
            recent_log_crashes,  # [batch, 16]
            normalized_entropy,  # [batch, 1]
            latent_stability     # [batch, 1]
        ], dim=1)  # [batch, 18]

        memory_confidence = self.confidence_net(confidence_input)  # [batch, 1]

        # 6. Transformation : exp pour avoir valeur absolue, min=1.0x
        memory_prediction = torch.clamp(torch.exp(memory_prediction_log), min=1.0)

        return {
            'memory_confidence': memory_confidence,
            'memory_prediction': memory_prediction,
            'normalized_entropy': normalized_entropy,
            'latent_stability': latent_stability
        }

    def analyze(self, sequence: torch.Tensor, global_state: torch.Tensor) -> dict:
        return self.forward(sequence, global_state)