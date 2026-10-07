"""Test de connexion simple à Cloud SQL"""
import psycopg2
from app.config import settings

try:
    # Décoder l'URL pour psycopg2
    print("📡 Tentative de connexion...")
    print(f"URL : {settings.DATABASE_URL}")

    # Connexion directe
    conn = psycopg2.connect(
        host="34.141.72.29",
        port=5432,
        database="luckyjet",
        user="postgres",
        password="LuckyJet2024!"  # Mot de passe brut (non encodé)
    )

    cur = conn.cursor()
    cur.execute("SELECT version();")
    version = cur.fetchone()[0]

    print("✅ CONNEXION RÉUSSIE !")
    print(f"🐘 PostgreSQL : {version}")

    cur.close()
    conn.close()

except Exception as e:
    print(f"❌ ÉCHEC DE CONNEXION : {e}")
    print("\n💡 Vérifie que :")
    print("   1. Ton IP est autorisée dans Cloud SQL (0.0.0.0/0)")
    print("   2. Le mot de passe est correct")
    print("   3. Le port 5432 n'est pas bloqué par ton pare-feu")