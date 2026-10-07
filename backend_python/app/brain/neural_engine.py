"""
Cerveau Neuronal - Architecture Transformer + Agents de Raisonnement Tabula Rasa + Méta-Décideur Conscient
Conformément au Master Blueprint (Approche Tabula Rasa Stricte)
CORRECTION : Libération de l'espace de prédiction + Bruit d'exploration
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import math
from loguru import logger

# Import des nouveaux Agents de Raisonnement Tabula Rasa
from app.reasoning.agent_memory import AgentMemory
from app.reasoning.agent_drift import AgentDrift
from app.reasoning.agent_velocity import AgentVelocity
from app.reasoning.meta_decider import MetaDeciderConscient


class PositionalEncoding(nn.Module):
    """Encodage positionnel temporel pour les séquences de crashs."""
    def __init__(self, d_model: int, max_len: int = 100):
        super().__init__()
        position = torch.arange(max_len).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2) * (-math.log(10000.0) / d_model))
        pe = torch.zeros(max_len, 1, d_model)
        pe[:, 0, 0::2] = torch.sin(position * div_term)
        pe[:, 0, 1::2] = torch.cos(position * div_term)
        self.register_buffer('pe', pe)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x + self.pe[:x.size(0), :, :]


class TransformerEncoder(nn.Module):
    """Cerveau Central - Transformer Encoder"""
    def __init__(self, input_dim: int = 3, d_model: int = 128, nhead: int = 8,
                 num_layers: int = 4, dim_feedforward: int = 512, dropout: float = 0.1):
        super().__init__()
        self.input_projection = nn.Linear(input_dim, d_model)
        self.pos_encoder = PositionalEncoding(d_model)

        encoder_layers = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=nhead, dim_feedforward=dim_feedforward,
            dropout=dropout, batch_first=True
        )
        self.transformer_encoder = nn.TransformerEncoder(encoder_layers, num_layers=num_layers)
        self.layer_norm = nn.LayerNorm(d_model)
        self.d_model = d_model
        logger.info(f"✅ Transformer Encoder initialisé: d_model={d_model}, heads={nhead}, layers={num_layers}")

    def forward(self, src: torch.Tensor) -> torch.Tensor:
        batch_size, seq_len, _ = src.shape
        device = src.device

        src = self.input_projection(src)
        src_t = src.transpose(0, 1)
        src_t = self.pos_encoder(src_t)
        src = src_t.transpose(0, 1)

        causal_mask = torch.triu(torch.full((seq_len, seq_len), float('-inf'), device=device), diagonal=1)
        encoded = self.transformer_encoder(src, mask=causal_mask)

        # Pooling sur le dernier pas de temps
        global_state = encoded[:, -1, :]
        return self.layer_norm(global_state)


class RegimeClassifier(nn.Module):
    """Classificateur de Régime Hybride (Algorithme CUSUM Statistique)"""
    def __init__(self):
        super().__init__()
        self.regime_names = ["normal", "high-rtp", "low-rtp", "volatile"]
        logger.info("✅ Regime Classifier (CUSUM Dynamique) initialisé")

    def forward(self, sequence: torch.Tensor) -> tuple:
        batch_size, seq_len, _ = sequence.shape
        # Reconstruction inverse du log-transform : exp(x) - 1
        crash_values = torch.exp(sequence[:, :, 0]) - 1.0

        regimes = []
        confidences = []

        for b in range(batch_size):
            crashes = crash_values[b].detach().cpu().numpy()

            if len(crashes) < 50:
                regimes.append("normal")
                confidences.append(0.5)
                continue

            mean_50 = float(crashes[-50:].mean())
            std_50 = float(crashes[-50:].std()) + 1e-6

            cusum_pos = 0.0
            cusum_neg = 0.0
            threshold = 0.5

            start_idx = max(0, len(crashes) - 100)
            recent_crashes = crashes[start_idx:]

            for crash in recent_crashes:
                z_score = (crash - mean_50) / std_50
                cusum_pos = max(0.0, cusum_pos + z_score - threshold)
                cusum_neg = max(0.0, cusum_neg - z_score - threshold)

            if cusum_pos > 5.0:
                regime, conf = "high-rtp", min(cusum_pos / 10.0, 1.0)
            elif cusum_neg > 5.0:
                regime, conf = "low-rtp", min(cusum_neg / 10.0, 1.0)
            elif std_50 > 10.0:
                regime, conf = "volatile", 0.85
            else:
                regime, conf = "normal", 0.90

            regimes.append(regime)
            confidences.append(conf)

        return regimes[-1], confidences[-1]


class LuckyJetPredictor(nn.Module):
    """
    Modèle complet assemblant le Transformer, les Agents et le Méta-Décideur.
    CORRECTION : Ajout d'une tête de prédiction libre + Bruit d'exploration
    """
    def __init__(self):
        super().__init__()
        self.transformer = TransformerEncoder(input_dim=3, d_model=128, nhead=8, num_layers=4, dim_feedforward=512)
        self.agent_memory = AgentMemory()
        self.agent_drift = AgentDrift()
        self.agent_velocity = AgentVelocity()
        self.meta_decider = MetaDeciderConscient()
        self.regime_classifier = RegimeClassifier()

        # 🚀 Tête de prédiction brute pour exploration libre
        self.raw_prediction_head = nn.Sequential(
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 1)
        )

        # 🚀 Initialisation améliorée pour éviter le figement à 1.0x
        # On initialise la dernière couche pour produire des valeurs autour de 0.5 (softplus(0.5) + 1 ≈ 1.97x)
        nn.init.normal_(self.raw_prediction_head[-1].weight, mean=0.0, std=0.1)
        nn.init.constant_(self.raw_prediction_head[-1].bias, 0.5)

        # Poids apprenable pour combiner meta_decider et prédiction brute
        self.combination_weight = nn.Parameter(torch.tensor(0.0))

        # Température pour contrôler l'agressivité des prédictions
        self.temperature = 1.0

        # 🚀 NOUVEAU : Bruit d'exploration pour casser la routine
        self.exploration_noise_std = 0.15  # 15% de bruit relatif

        logger.success("🧠 Modèle LuckyJetPredictor avec EXPLORATION LIBRE initialisé!")
        logger.info("   → Espace de prédiction: 1.00x → ∞ (aucun plafond artificiel)")
        logger.info("   → Tête brute: 128 → 64 → 32 → 1 (softplus + 1.0)")
        logger.info(f"   → Bruit d'exploration: {self.exploration_noise_std*100}% (actif en inférence)")

    def forward(self, sequence: torch.Tensor):
        # 1. Cerveau central
        global_state = self.transformer(sequence) # [batch, 128]

        # 2. Agents de Raisonnement
        memory_data = self.agent_memory.analyze(sequence, global_state)
        drift_data = self.agent_drift.analyze(sequence, global_state)
        velocity_data = self.agent_velocity.analyze(sequence, global_state)

        agents_data = {
            'memory': memory_data,
            'drift': drift_data,
            'velocity': velocity_data
        }

        # 3. Méta-Décideur Conscient (raisonnement structuré)
        decision = self.meta_decider(global_state, agents_data)
        meta_score = decision['target_score']

        # 4. 🚀 Prédiction brute (exploration libre de l'espace)
        raw_score = self.raw_prediction_head(global_state)  # [batch, 1]

        # 5. 🚀 Combinaison dynamique des deux approches
        weight = torch.sigmoid(self.combination_weight)
        combined_score = weight * meta_score + (1 - weight) * raw_score

        # 6. 🚀 Transformation pour garantir min=1.0x sans plafond
        final_score = F.softplus(combined_score / self.temperature) + 1.0

        # 7. 🚀 NOUVEAU : Bruit d'exploration (uniquement en mode inférence)
        # Cela force l'IA à varier ses prédictions même si les entrées sont similaires
        if not self.training:
            # Bruit gaussien multiplicatif : final_score * (1 + noise)
            noise = torch.randn_like(final_score) * self.exploration_noise_std
            final_score = final_score * (1.0 + noise)
            # Re-clamp pour garantir le minimum de 1.0x
            final_score = torch.clamp(final_score, min=1.0)

        # 8. Classificateur de régime
        regime, regime_conf = self.regime_classifier(sequence)

        # Extraction de la divergence
        divergence = decision.get('divergence', torch.tensor(0.5, device=sequence.device))

        return {
            'target_score': final_score,
            'confidence': decision['confidence'],
            'regime': regime,
            'regime_confidence': regime_conf,
            'global_state': global_state,
            'divergence': divergence,
            # Logs de diagnostic pour monitorer l'équilibre
            'meta_score': meta_score,
            'raw_score': raw_score,
            'combination_weight': weight.item(),
            'sages': {
                'memory': memory_data['memory_prediction'],
                'drift': drift_data['drift_prediction'],
                'velocity': velocity_data['velocity_prediction']
            }
        }