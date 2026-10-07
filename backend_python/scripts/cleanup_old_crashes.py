"""
Buffer Circulaire - Nettoyage automatique des anciens crashs
Maintient un maximum de tours défini dans raw_crashes de manière optimisée.
"""

import asyncio
from sqlalchemy import select, func, delete
from loguru import logger

from app.memory.cloud_sql import get_session, RawCrash


async def cleanup_old_crashes(max_records: int = 300000):
    """
    Supprime les anciens crashs si le nombre total dépasse max_records.
    Utilise une approche par seuil temporel (Cutoff Time) pour une performance O(log N)
    au lieu de charger des milliers d'IDs en mémoire.
    """
    try:
        async with get_session() as session:
            # 1. Compter le nombre total de crashs (Rapide si indexé)
            count_stmt = select(func.count(RawCrash.id))
            result = await session.execute(count_stmt)
            total_crashes = result.scalar() or 0

            logger.info(f"📊 Nombre total de crashs en base : {total_crashes} / {max_records}")

            if total_crashes > max_records:
                records_to_delete = total_crashes - max_records
                logger.warning(f"⚠️ Limite dépassée. {records_to_delete} enregistrements doivent être supprimés.")

                # 2. Trouver la date/heure de coupure (Cutoff Time)
                # On récupère la date du (max_records)-ième crash le plus récent.
                # Tout ce qui est PLUS VIEUX que cette date sera supprimé.
                cutoff_query = (
                    select(RawCrash.captured_at)
                    .order_by(RawCrash.captured_at.desc())
                    .offset(max_records)
                    .limit(1)
                )
                cutoff_result = await session.execute(cutoff_query)
                cutoff_time = cutoff_result.scalar()

                if cutoff_time:
                    logger.info(f"🎯 Seuil de coupure identifié : {cutoff_time}")

                    # 3. Suppression en masse optimisée par le moteur SQL
                    # Cette méthode est bien plus rapide et sûre que WHERE id IN (...)
                    delete_stmt = delete(RawCrash).where(RawCrash.captured_at < cutoff_time)

                    result_delete = await session.execute(delete_stmt)
                    await session.commit()

                    deleted_count = result_delete.rowcount
                    logger.success(f"🗑️ {deleted_count} anciens crashs supprimés avec succès (Buffer circulaire)")

                    # Vérification finale
                    new_count_stmt = select(func.count(RawCrash.id))
                    new_total = (await session.execute(new_count_stmt)).scalar() or 0
                    logger.info(f"✅ Nombre de crashs restants : {new_total}")
                else:
                    logger.warning("⚠️ Impossible de déterminer le seuil de coupure. Annulation du nettoyage.")
            else:
                remaining = max_records - total_crashes
                logger.debug(f"✅ Base de données dans les limites ({remaining} crashs avant la limite)")

    except Exception as e:
        logger.error(f"❌ Erreur critique lors du nettoyage du buffer : {e}", exc_info=True)
        # On ne propage pas l'erreur pour ne pas casser le pipeline principal si ce script est appelé en tâche de fond


async def main():
    """Point d'entrée pour exécution manuelle ou via Cron"""
    logger.info("🧹 Démarrage du nettoyage du buffer circulaire...")
    await cleanup_old_crashes(max_records=300000)
    logger.info("✅ Nettoyage terminé")


if __name__ == "__main__":
    asyncio.run(main())