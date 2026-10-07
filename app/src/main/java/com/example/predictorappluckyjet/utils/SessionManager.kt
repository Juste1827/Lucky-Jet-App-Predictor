package com.example.predictorappluckyjet.utils

import android.content.Context

object SessionManager {
    private const val PREFS_NAME = "LuckyJetPrefs"
    private const val KEY_IS_LOGGED_IN = "is_logged_in"
    private const val KEY_PLAYER_ID = "player_id"

    // Sauvegarder la session
    fun saveSession(context: Context, playerId: String) {
        val sharedPreferences = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        sharedPreferences.edit().apply {
            putBoolean(KEY_IS_LOGGED_IN, true)
            putString(KEY_PLAYER_ID, playerId)
            apply()
        }
    }

    // Vérifier si l'utilisateur est déjà connecté
    fun isLoggedIn(context: Context): Boolean {
        val sharedPreferences = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        return sharedPreferences.getBoolean(KEY_IS_LOGGED_IN, false)
    }

    // Récupérer l'ID du joueur (utile pour le backend)
    fun getPlayerId(context: Context): String? {
        val sharedPreferences = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        return sharedPreferences.getString(KEY_PLAYER_ID, null)
    }

    // Déconnexion propre (à utiliser uniquement si l'utilisateur le demande explicitement)
    fun clearSession(context: Context) {
        val sharedPreferences = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        sharedPreferences.edit().clear().apply()
    }
}