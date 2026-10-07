"""
Point d'entrée FastAPI du backend Lucky Jet Predictor AI.
Orchestre le cerveau neuronal complet avec Online Learning, Multi-Agents Tabula Rasa,
et Dashboard de Performance. (Version v3.2 - Apprentissage Rapide)
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from loguru import logger
import uvicorn
from datetime import datetime
import torch
import sys
from sqlalchemy import select

from app.config import settings
from app.memory.cloud_sql import get_session, init_db, RawCrash, PredictionLog, FeedbackLoop
from app.memory.episodic_memory import calculate_delta_time, get_last_crashes
from app.brain.model_manager import ModelCheckpoint
from app.learning.online_learner import OnlineLearner
from app.gateway.firestore_bridge import FirestoreBridge

# Variables globales pour l'état du système
model_manager: ModelCheckpoint = None
online_learner: OnlineLearner = None
firestore_bridge: FirestoreBridge = None
last_prediction: dict = None
rounds_since_last_train: int = 0

# 🚀 NOUVEAU : Seuil d'apprentissage réduit pour une adaptation plus rapide
ONLINE_LEARNING_THRESHOLD = 10  # Apprentissage tous les 10 tours (au lieu de 32)
CHECKPOINT_SAVE_THRESHOLD = 10    # Sauvegarde tous les 10 tours

@asynccontextmanager
async def lifespan(app: FastAPI):
    global model_manager, online_learner, firestore_bridge

    logger.info("🚀 Initialisation du moteur neuronal...")
    try:
        await init_db()
        logger.success("✅ Connexion à la base de données établie avec succès.")
    except Exception as db_error:
        logger.error(f"❌ ÉCHEC CRITIQUE de connexion à la base de données : {db_error}")
        sys.exit(1)

    try:
        model_manager = ModelCheckpoint()
        # Le chargement utilise maintenant la méthode Dual-Storage (Fichier local + SQL)
        success = await model_manager.load_latest_checkpoint()
        if success:
            logger.success("✅ Cerveau IA restauré avec succès (Poids conservés).")
        else:
            logger.warning("⚠️ Démarrage à zéro (Tabula Rasa). Aucun checkpoint valide trouvé.")
    except Exception as model_error:
        logger.error(f"❌ Échec chargement modèle : {model_error}")

    online_learner = OnlineLearner(
        model=model_manager.get_model(),
        optimizer=model_manager.get_optimizer() # <-- AJOUT CRUCIAL
    )
    firestore_bridge = FirestoreBridge()

    logger.success(f"✅ Moteur neuronal prêt et opérationnel sur le port 8000 !")
    logger.info(f"   → Online Learning tous les {ONLINE_LEARNING_THRESHOLD} tours")
    logger.info(f"   → Sauvegarde checkpoint tous les {CHECKPOINT_SAVE_THRESHOLD} tours")

    yield

    logger.info("🛑 Arrêt du moteur neuronal et sauvegarde finale...")
    if model_manager:
        await model_manager.save_checkpoint(is_dream_checkpoint=False)

app = FastAPI(
    title="Lucky Jet Predictor AI - Neural Engine",
    description="Backend Python avec cerveau neuronal Transformer, Multi-Agents Tabula Rasa et Online Learning",
    version="3.2.0",
    lifespan=lifespan
)

class CrashData(BaseModel):
    crash_value: float
    latency_ms: int
    timestamp: str


async def trigger_online_training():
    """
    Cœur de l'Online Learning : Récupère l'historique, prépare le batch,
    effectue la backpropagation et sauvegarde si nécessaire.
    🚀 AMÉLIORÉ : Apprentissage plus fréquent (tous les 10 tours)
    """
    global model_manager, online_learner

    logger.info("🧠 Début de la séquence d'apprentissage en ligne (Backpropagation)...")
    try:
        model = model_manager.get_model()
        model.train() # 🚀 Passage en mode entraînement

        async with get_session() as session:
            recent_tours = await get_last_crashes(session, limit=100)

        if len(recent_tours) < 65:
            logger.warning(f"⚠️ Pas assez de données pour l'entraînement ({len(recent_tours)}/65 requis).")
            model.eval()
            return

        X_batch, y_batch = online_learner.prepare_training_batch(recent_tours)

        if X_batch.numel() == 0:
            logger.warning("⚠️ Batch d'entraînement vide.")
            model.eval()
            return

        # 1. Backpropagation
        loss_value = await online_learner.train_step(X_batch, y_batch)

        # 🚀 CORRECTION CRITIQUE : Synchroniser le compteur !
        # On met à jour le compteur du ModelManager avec la vraie valeur de l'OnlineLearner
        model_manager.total_rounds_trained = online_learner.total_rounds_trained

        logger.success(f"✅ Backpropagation réussie ! Loss: {loss_value:.4f} | Tours entraînés (total): {model_manager.total_rounds_trained}")

        # 2. Sauvegarde périodique (tous les CHECKPOINT_SAVE_THRESHOLD tours d'entraînement)
        if model_manager.total_rounds_trained > 0 and (model_manager.total_rounds_trained % CHECKPOINT_SAVE_THRESHOLD == 0):
            logger.info(f"💾 Seuil de sauvegarde atteint ({CHECKPOINT_SAVE_THRESHOLD} tours). Sauvegarde du checkpoint (Dual-Storage)...")
            await model_manager.save_checkpoint(loss=loss_value)
            logger.success("✅ Checkpoint sauvegardé sur disque et indexé en SQL.")

        model.eval() # 🚀 Retour en mode inférence

    except Exception as e:
        logger.error(f"❌ Erreur critique durant l'entraînement en ligne : {e}", exc_info=True)
        if model_manager:
            model_manager.get_model().eval()


@app.post("/api/crash")
async def receive_crash(data: CrashData):
    global rounds_since_last_train, last_prediction
    logger.info(f"📥 Reçu de Node.js : Crash {data.crash_value}x | Latence {data.latency_ms}ms")

    try:
        async with get_session() as session:
            delta_time = await calculate_delta_time(session)
            new_crash = RawCrash(
                crash_value=data.crash_value,
                latency_ms=data.latency_ms,
                delta_time_ms=delta_time
            )
            session.add(new_crash)
            await session.commit()
            await session.refresh(new_crash)
            crash_id = new_crash.id

        logger.success(f"💾 Sauvegardé en base: ID {crash_id}, Crash {data.crash_value}x")

        await firestore_bridge.update_last_crashes(
            crash_value=data.crash_value,
            latency_ms=data.latency_ms,
            round_id=crash_id
        )

        # 1. Évaluer la prédiction précédente AVANT d'en générer une nouvelle
        if last_prediction is not None:
            await evaluate_and_learn(crash_id, data.crash_value)

        # 2. Générer la nouvelle prédiction
        await generate_prediction(crash_id)

        return {"status": "ok", "message": "Données reçues, prédiction générée", "id": crash_id}

    except Exception as e:
        logger.error(f"❌ Erreur dans la pipeline: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur interne du serveur")


async def generate_prediction(crash_id: int):
    """Génère une prédiction pour le prochain tour avec des données 100% DYNAMIQUES"""
    global last_prediction
    try:
        async with get_session() as session:
            crash_history = await get_last_crashes(session, limit=64)

        if len(crash_history) < 10:
            logger.warning(f"⚠️ Pas assez de données pour prédire ({len(crash_history)}/10 requis)")
            return

        # 🛑 SONDE DE DIAGNOSTIC : Affiche les 3 derniers crashs donnés au modèle
        debug_last_3 = [c['crash_value'] for c in crash_history[-3:]]
        logger.debug(f"🧠 Séquence d'inférence (3 derniers): {debug_last_3}")

        sequence = online_learner.prepare_inference_sequence(crash_history)
        model = model_manager.get_model()
        model.eval() # Mode évaluation (désactive Dropout, etc.)

        with torch.no_grad():
            outputs = model(sequence)

        target_score_raw = max(1.00, float(outputs['target_score'].item()))
        confidence_raw = max(0.0, min(1.0, float(outputs['confidence'].item())))
        regime = str(outputs.get('regime', 'normal'))
        last_crash_float = crash_history[-1].get('crash_value', 1.0)

        # --- EXTRACTION DES SAGES (Avec Fallback Dynamique) ---
        try:
            divergence = float(outputs.get('divergence', 0.5).item()) if 'divergence' in outputs else 0.5

            if 'sages' in outputs:
                sage_mem_val = float(outputs['sages']['memory'].item())
                sage_drift_val = float(outputs['sages']['drift'].item())
                sage_vel_val = float(outputs['sages']['velocity'].item())
            else:
                # Fallback : Si les sages ne sont pas dans le output, on les calcule statistiquement ici
                vals = [c['crash_value'] for c in crash_history[-10:]]
                sage_mem_val = sum(vals)/len(vals)
                sage_drift_val = vals[-1] - vals[-2] if len(vals)>1 else 0.0
                sage_vel_val = 1.0
                divergence = 0.5

            logger.info(f"🧠 Sages Dynamiques - Memory: {sage_mem_val:.2f}, Drift: {sage_drift_val:.2f}, Velocity: {sage_vel_val:.2f} | Divergence: {divergence:.2f}")

            sage_confidence_pct = int(max(0, min(100, 100 - (divergence * 100))))

            sages_summary = {
                'memory': f"{sage_mem_val:.2f}x ({sage_confidence_pct}%)",
                'drift': f"{sage_drift_val:.2f}x ({sage_confidence_pct}%)",
                'velocity': f"{sage_vel_val:.2f}x ({sage_confidence_pct}%)"
            }

            divergence_pct = int(divergence * 100)
            if divergence < 0.20:
                meta_state = f"Méta-IA: État stable, divergence faible ({divergence_pct}%)."
            elif divergence < 0.50:
                meta_state = f"Méta-IA: État modéré, divergence acceptable ({divergence_pct}%)."
            else:
                meta_state = f"Méta-IA: État instable, divergence élevée ({divergence_pct}%). Prudence."

        except Exception as e:
            logger.error(f"❌ ERREUR extraction sages: {e}. Activation du mode calcul statistique pur.")
            vals = [c['crash_value'] for c in crash_history[-5:]]
            sages_summary = {
                'memory': f"{(sum(vals)/len(vals)):.2f}x",
                'drift': f"{(vals[-1] - vals[0]):.2f}x",
                'velocity': f"1.00x"
            }
            meta_state = "Méta-IA: Mode dégradé statistique."

        # Push vers Firestore
        await firestore_bridge.push_prediction(
            round_id=int(crash_id),
            target_score=float(target_score_raw),
            confidence=int(confidence_raw * 100),
            last_crash=float(last_crash_float),
            regime=str(regime),
            sages_summary=sages_summary,
            meta_state=meta_state,
            epoch=int(model_manager.current_epoch)
        )

        # Sauvegarde Locale SQL pour le Dashboard
        async with get_session() as session:
            new_pred = PredictionLog(
                round_id=crash_id,
                predicted_score=target_score_raw,
                confidence=int(confidence_raw * 100),
                regime=regime,
                sage_memory_score=float(sages_summary['memory'].split('x')[0]),
                sage_drift_score=float(sages_summary['drift'].split('x')[0]),
                sage_velocity_score=float(sages_summary['velocity'].split('x')[0])
            )
            session.add(new_pred)
            await session.commit()
            await session.refresh(new_pred)

        last_prediction = {
            'db_id': new_pred.id,
            'target_score': float(target_score_raw),
            'confidence': int(confidence_raw * 100),
            'regime': str(regime),
            'timestamp': datetime.utcnow()
        }
        logger.info(f"🔮 Prédiction générée: {target_score_raw:.2f}x @ {int(confidence_raw * 100)}% [{regime}]")

    except Exception as e:
        logger.error(f"❌ Erreur génération prédiction: {e}", exc_info=True)


async def evaluate_and_learn(crash_id: int, actual_crash: float):
    """Évalue la prédiction précédente, sauvegarde le feedback et déclenche l'apprentissage."""
    global last_prediction, rounds_since_last_train

    if last_prediction is None:
        return

    try:
        # Logique de réussite : Le crash réel est >= à notre prédiction conservative
        was_successful = actual_crash >= last_prediction['target_score']
        error_score = abs(actual_crash - last_prediction['target_score'])

        logger.info(f"📊 Évaluation Tour {crash_id}: Prédit={last_prediction['target_score']:.2f}x | Réel={actual_crash:.2f}x | ✅ Succès={was_successful}")

        await firestore_bridge.log_history(
            round_id=crash_id,
            predicted_threshold=last_prediction['target_score'],
            actual_crash=actual_crash,
            confidence=last_prediction['confidence'],
            regime=last_prediction['regime'],
            was_successful=was_successful
        )

        async with get_session() as session:
            feedback = FeedbackLoop(
                prediction_id=last_prediction['db_id'],
                actual_crash=actual_crash,
                error_score=error_score,
                was_accurate=was_successful,
                confidence_calibration=last_prediction['confidence'] / 100.0
            )
            session.add(feedback)
            await session.commit()

        # 🚀 MODIFICATION : Déclenchement de l'entraînement plus fréquent (tous les 10 tours)
        rounds_since_last_train += 1
        if rounds_since_last_train >= ONLINE_LEARNING_THRESHOLD:
            logger.info(f"🎯 Seuil de {rounds_since_last_train} tours atteint. Déclenchement de l'Online Learning...")
            await trigger_online_training()
            rounds_since_last_train = 0

    except Exception as e:
        logger.error(f"❌ Erreur evaluate_and_learn: {e}", exc_info=True)
    finally:
        last_prediction = None # Reset pour le prochain tour


@app.get("/api/stats")
async def get_performance_stats():
    """Dashboard de Performance : Calcule les métriques de l'IA sur les 100 derniers tours."""
    try:
        async with get_session() as session:
            stmt = (
                select(FeedbackLoop, PredictionLog)
                .join(PredictionLog, FeedbackLoop.prediction_id == PredictionLog.id)
                .order_by(FeedbackLoop.learned_at.desc())
                .limit(100)
            )
            result = await session.execute(stmt)
            rows = result.all()

            if not rows:
                return {"status": "no_data", "message": "Pas encore assez de données (attendre 100 évaluations)."}

            total_evals = len(rows)
            successful_preds = sum(1 for fb, pl in rows if fb.was_accurate)
            accuracy = (successful_preds / total_evals) * 100 if total_evals > 0 else 0.0
            avg_error = sum(fb.error_score for fb, pl in rows) / total_evals if total_evals > 0 else 0.0

            regime_stats = {}
            for fb, pl in rows:
                regime = pl.regime
                if regime not in regime_stats:
                    regime_stats[regime] = {'total': 0, 'success': 0}
                regime_stats[regime]['total'] += 1
                if fb.was_accurate:
                    regime_stats[regime]['success'] += 1

            for regime, stats in regime_stats.items():
                stats['accuracy'] = round((stats['success'] / stats['total']) * 100, 2) if stats['total'] > 0 else 0.0

            evolution = 0.0
            if total_evals >= 100:
                recent_50_success = sum(1 for fb, pl in rows[:50] if fb.was_accurate)
                previous_50_success = sum(1 for fb, pl in rows[50:100] if fb.was_accurate)
                evolution = round(((recent_50_success / 50) - (previous_50_success / 50)) * 100, 2)

            return {
                "status": "success",
                "total_evaluations": total_evals,
                "global_accuracy": round(accuracy, 2),
                "average_error": round(avg_error, 4),
                "evolution_trend": evolution,
                "regime_breakdown": regime_stats,
                "model_info": {
                    "current_epoch": model_manager.current_epoch if model_manager else 0,
                    "total_rounds_trained": model_manager.total_rounds_trained if model_manager else 0
                }
            }

    except Exception as e:
        logger.error(f"❌ Erreur lors du calcul des statistiques : {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur interne lors du calcul des stats")


@app.get("/health")
async def healthcheck():
    return {
        "status": "healthy",
        "service": "Lucky Jet Neural Engine v3.2",
        "model_loaded": model_manager is not None,
        "total_rounds_trained": online_learner.total_rounds_trained if online_learner else 0,
        "current_epoch": model_manager.current_epoch if model_manager else 0
    }

if __name__ == "__main__":
    logger.info("🚀 Démarrage du moteur neuronal Python sur le port 8000...")
    uvicorn.run(app, host="0.0.0.0", port=8000)