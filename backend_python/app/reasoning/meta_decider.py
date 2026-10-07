import torch
import torch.nn as nn
import torch.nn.functional as F
from loguru import logger

class MetaDeciderConscient(nn.Module):
    """
    Méta-Décideur Conscient : Agrège les signaux des 3 Sages et prend décision finale.
    NOUVEAU : Calcul de divergence amélioré + réseau plus expressif.
    CORRECTION : Suppression des skip connections incompatibles (dimensions 32 vs 128).
    """
    def __init__(self, global_dim: int = 128, agent_features_dim: int = 13):
        super().__init__()
        input_dim = global_dim + agent_features_dim + 3  # +3 pour divergence, max_pred, min_pred

        # Réseau profond (sans skip connections pour éviter les conflits de dimension)
        self.layer1 = nn.Linear(input_dim, 128)
        self.norm1 = nn.LayerNorm(128)
        self.layer2 = nn.Linear(128, 64)
        self.norm2 = nn.LayerNorm(64)
        self.layer3 = nn.Linear(64, 32)
        self.norm3 = nn.LayerNorm(32)
        self.output_layer = nn.Linear(32, 2)  # target_score_log, confidence_raw

        self.dropout = nn.Dropout(0.15)
        self.activation = nn.GELU()

        logger.info(f"✅ Méta-Décideur Conscient (v2.1) - Input: {input_dim}D, Architecture profonde")

    def forward(self, global_state: torch.Tensor, agents_data: dict) -> dict:
        batch_size = global_state.shape[0]
        device = global_state.device

        # 1. Extraction
        mem_pred = agents_data['memory']['memory_prediction']
        mem_conf = agents_data['memory']['memory_confidence']
        drift_pred = agents_data['drift']['drift_prediction']
        drift_conf = agents_data['drift']['drift_confidence']
        vel_pred = agents_data['velocity']['velocity_prediction']
        vel_conf = agents_data['velocity']['velocity_confidence']

        # 2. Calcul de divergence multi-métrique
        predictions_stack = torch.cat([mem_pred, drift_pred, vel_pred], dim=1)  # [batch, 3]
        max_pred = torch.max(predictions_stack, dim=1, keepdim=True)[0]
        min_pred = torch.min(predictions_stack, dim=1, keepdim=True)[0]
        mean_pred = torch.mean(predictions_stack, dim=1, keepdim=True)

        # Divergence absolue
        divergence_range = max_pred - min_pred

        # Divergence relative (coefficient de variation)
        pred_std = torch.std(predictions_stack, dim=1, keepdim=True)
        divergence_cv = pred_std / (mean_pred + 1e-6)

        # Divergence normalisée combinée
        normalized_divergence = torch.clamp(
            (divergence_range / 10.0) * 0.5 + divergence_cv * 0.5,
            0.0, 1.0
        )

        # 3. Vecteur de features
        agent_features = torch.cat([
            mem_conf, mem_pred, agents_data['memory']['normalized_entropy'], agents_data['memory']['latent_stability'],
            drift_conf, drift_pred, agents_data['drift']['momentum_score'], agents_data['drift']['velocity'], agents_data['drift']['acceleration'],
            vel_conf, vel_pred, agents_data['velocity']['anomaly_score'], agents_data['velocity']['correlation_score']
        ], dim=1)

        # Ajout de max_pred et min_pred comme features explicites
        combined_input = torch.cat([
            global_state,
            agent_features,
            normalized_divergence,
            max_pred,
            min_pred
        ], dim=1)

        # 4. 🚀 CORRECTION : Forward pass simple et robuste (sans skip connections)
        x = self.activation(self.norm1(self.layer1(combined_input))) # [batch, 128]
        x = self.activation(self.norm2(self.layer2(x)))              # [batch, 64]
        x = self.activation(self.norm3(self.layer3(x)))              # [batch, 32]
        x = self.dropout(x)

        outputs = self.output_layer(x)
        target_score_log = outputs[:, 0:1]
        confidence_raw = outputs[:, 1:2]

        # 5. Transformations finales (LIBERTÉ TOTALE)
        temperature = 1.0
        target_score = torch.clamp(torch.exp(target_score_log / temperature), min=1.0)

        base_confidence = torch.sigmoid(confidence_raw)

        # Pénalité de confiance plus nuancée
        divergence_penalty = normalized_divergence * 0.4

        # Bonus si divergence élevée ET prédictions élevées (signal de gros crash)
        high_prediction_bonus = ((mean_pred > 5.0).float() * normalized_divergence * 0.2)

        final_confidence = torch.clamp(
            base_confidence * (1.0 - divergence_penalty) + high_prediction_bonus,
            0.0, 1.0
        )

        return {
            'target_score': target_score,
            'confidence': final_confidence,
            'divergence': normalized_divergence,
            'base_confidence': base_confidence
        }