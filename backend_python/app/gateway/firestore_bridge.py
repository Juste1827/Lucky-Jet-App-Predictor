"""
Passerelle Firestore - Schéma Next-Gen pour l'architecture Transformer
Conformité stricte avec le MASTER BLUEPRINT (Aucune modification Android requise)
Version v2.1 : Chemins absolus et intégrité transactionnelle.
"""
import json
from datetime import datetime, timezone
from loguru import logger
from google.cloud import firestore
from google.cloud.firestore_v1 import SERVER_TIMESTAMP

from app.config import settings


class FirestoreBridge:
    def __init__(self):
        # 🚀 CORRECTION 1 : Utilisation du chemin absolu pour une fiabilité à 100%
        cred_path = settings.absolute_credentials_path

        if not cred_path.exists():
            raise FileNotFoundError(f"Firebase credentials not found at {cred_path}")

        with open(cred_path, 'r', encoding='utf-8') as f:
            service_account_info = json.load(f)

        self.db = firestore.Client.from_service_account_info(
            service_account_info,
            database=settings.FIREBASE_DATABASE_ID
        )
        logger.success(f"✅ Firestore connecté à : '{settings.FIREBASE_DATABASE_ID}'")

    async def push_prediction(self, round_id: int, target_score: float, confidence: float,
                              last_crash: float, regime: str, sages_summary: dict, meta_state: str, epoch: int):
        """
        Pousse la prédiction dans Firestore (Document: latest)
        Format EXACT requis par l'app Android.
        """
        try:
            ts_float = float(target_score)
        except (ValueError, TypeError):
            ts_float = 1.50

        try:
            lc_str = str(last_crash).replace('x', '').strip()
            lc_float = float(lc_str)
        except (ValueError, TypeError):
            lc_float = 1.00

        try:
            conf_int = int(float(confidence))
            conf_int = max(0, min(100, conf_int))
        except (ValueError, TypeError):
            conf_int = 50

        doc_data = {
            "round_id": int(round_id),
            "target_score": f"{ts_float:.2f}",
            "confidence": conf_int,
            "last_crash": f"{lc_float:.2f}x",
            "regime": str(regime).lower(),
            "meta_state": str(meta_state),
            "model_epoch": int(epoch),
            "sages_summary": {
                # S'assure que les chaînes formatées par main.py (ex: "3.71x (43%)") sont bien passées
                "memory": str(sages_summary.get('memory', "0.00x (0%)")),
                "drift": str(sages_summary.get('drift', "0.00x (0%)")),
                "velocity": str(sages_summary.get('velocity', "0.00x (0%)"))
            },
            "timestamp": SERVER_TIMESTAMP
        }

        try:
            self.db.collection('predictions').document('latest').set(doc_data)
            logger.info(f"📤 Firestore [latest] mis à jour: {ts_float:.2f}x @ {conf_int}% [{regime}]")
        except Exception as e:
            logger.error(f"❌ Échec push Firestore latest: {e}")

    async def log_history(self, round_id: int, predicted_threshold: float, actual_crash: float,
                          confidence: float, regime: str, was_successful: bool):
        """
        Ajoute un document dans l'historique (Collection: history)
        """
        try:
            conf_float = float(confidence)
            conf_int = int(conf_float * 100) if conf_float <= 1.0 else int(conf_float)
            conf_int = max(0, min(100, conf_int))
        except (ValueError, TypeError):
            conf_int = 50

        doc_data = {
            "round_id": int(round_id),
            "predicted_threshold": float(predicted_threshold),
            "actual_crash": float(actual_crash),
            "confidence_at_time": conf_int,
            "was_successful": bool(was_successful),
            "regime": str(regime).lower(),
            "timestamp": SERVER_TIMESTAMP
        }

        try:
            self.db.collection('history').add(doc_data)
            logger.debug(f"📚 Firestore [history] logué: round {round_id}, success={was_successful}")
        except Exception as e:
            logger.error(f"❌ Échec push Firestore history: {e}")

    async def update_last_crashes(self, crash_value: float, latency_ms: int, round_id: int):
        """
        Met à jour la liste des derniers crashs dans Firestore de manière TRANSACTIONNELLE.
        Cela empêche toute perte de donnée en cas de requêtes simultanées.
        """
        try:
            doc_ref = self.db.collection('last_crashes').document('list')

            # 🚀 CORRECTION 2 : Utilisation d'une transaction pour un Read-Modify-Write atomique
            @firestore.transactional
            def update_in_transaction(transaction):
                snapshot = doc_ref.get(transaction=transaction)
                crashes_list = []

                if snapshot.exists:
                    crashes_list = snapshot.to_dict().get('crashes', [])

                new_crash = {
                    "value": f"{float(crash_value):.2f}x",
                    "raw_value": float(crash_value),
                    "latency_ms": int(latency_ms),
                    "round_id": int(round_id),
                    "timestamp": datetime.now(timezone.utc)
                }

                # Prépend et limite à 50
                crashes_list.insert(0, new_crash)
                crashes_list = crashes_list[:50]

                transaction.set(doc_ref, {
                    "crashes": crashes_list,
                    "updated_at": SERVER_TIMESTAMP
                })

            # Exécution de la transaction
            update_in_transaction(self.db.transaction())
            logger.debug(f"🔄 Last crashes list updated (transactionnel): 50 crashs max")

        except Exception as e:
            logger.error(f"❌ Erreur mise à jour last_crashes: {e}")