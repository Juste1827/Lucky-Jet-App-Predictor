package com.example.predictorappluckyjet.viewmodel

import android.util.Log
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.google.firebase.FirebaseApp
import com.google.firebase.firestore.FirebaseFirestore
import com.google.firebase.firestore.ListenerRegistration
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

data class SageSummary(val memory: String = "0.00x (0%)", val drift: String = "0.00x (0%)", val velocity: String = "0.00x (0%)")
data class CrashItem(val value: String = "0.00x", val raw_value: Double = 0.0, val latency_ms: Int = 0, val round_id: Long = 0, val timestamp: String? = null)

data class PredictionData(
    val round_id: Long = 0,
    val target_score: String = "1.50",
    val confidence: Int = 0,
    val last_crash: String = "0.00x",
    val regime: String = "normal",
    val meta_state: String = "En attente...",
    val sages_summary: SageSummary? = null,
    val model_epoch: Int = 0,
    val timestamp: String? = null,
    val is_training: Boolean = true
)

// 🆕 AJOUT du champ 'message' pour gérer les états "no_data"
data class PerformanceStats(
    val status: String = "",
    val message: String = "", // Nouveau champ
    val global_accuracy: Double = 0.0,
    val average_error: Double = 0.0,
    val evolution_trend: Double = 0.0,
    val total_evaluations: Int = 0,
    val regime_breakdown: Map<String, RegimeStat> = emptyMap(),
    val model_info: ModelInfo? = null
)

data class RegimeStat(val total: Int = 0, val success: Int = 0, val accuracy: Double = 0.0)
data class ModelInfo(val current_epoch: Int = 0, val total_rounds_trained: Int = 0)

class DashboardViewModel : ViewModel() {
    private val firebaseApp = FirebaseApp.getInstance()
    private val db = FirebaseFirestore.getInstance(firebaseApp, "app-predictor-lucky-jet")

    private val _prediction = MutableStateFlow<PredictionData?>(null)
    val prediction: StateFlow<PredictionData?> = _prediction.asStateFlow()

    private val _lastCrashes = MutableStateFlow<List<CrashItem>>(emptyList())
    val lastCrashes: StateFlow<List<CrashItem>> = _lastCrashes.asStateFlow()

    private val _isConnected = MutableStateFlow(false)
    val isConnected: StateFlow<Boolean> = _isConnected.asStateFlow()

    private val _isUserStopped = MutableStateFlow(false)
    val isUserStopped: StateFlow<Boolean> = _isUserStopped.asStateFlow()

    private val _performanceStats = MutableStateFlow<PerformanceStats?>(null)
    val performanceStats: StateFlow<PerformanceStats?> = _performanceStats.asStateFlow()

    private var listenerRegistration: ListenerRegistration? = null
    private var lastCrashesListenerRegistration: ListenerRegistration? = null

    // ⚠️ ASSURE-TOI QUE C'EST BIEN L'IP DE TON PC (ex: 192.168.1.XX), PAS 10.0.2.2
    private val backendBaseUrl = "http://192.168.100.9:8000" // <-- REMPLACE ICI

    init {
        Log.d("FIRESTORE_DEBUG", "🚀 Initialisation du ViewModel avec la base: app-predictor-lucky-jet")
        startListening()
        startListeningLastCrashes()
        fetchPerformanceStats()
    }

    // ... (Garde tes fonctions startListening() et startListeningLastCrashes() telles quelles) ...
    private fun startListening() {
        if (_isUserStopped.value) return
        listenerRegistration = db.collection("predictions").document("latest")
            .addSnapshotListener { snapshot, error ->
                if (error != null) {
                    Log.e("FIRESTORE_DEBUG", "❌ Erreur predictions/latest: ${error.message}")
                    return@addSnapshotListener
                }
                if (snapshot != null && snapshot.exists()) {
                    val data = snapshot.data
                    if (data != null) {
                        try {
                            _prediction.value = PredictionData(
                                round_id = (data["round_id"] as? Number)?.toLong() ?: 0L,
                                target_score = (data["target_score"] as? String) ?: "0.00",
                                confidence = (data["confidence"] as? Number)?.toInt() ?: 0,
                                last_crash = (data["last_crash"] as? String) ?: "0.00x",
                                regime = (data["regime"] as? String) ?: "normal",
                                meta_state = (data["meta_state"] as? String) ?: "Analyse...",
                                model_epoch = (data["model_epoch"] as? Number)?.toInt() ?: 0,
                                timestamp = data["timestamp"]?.toString(),
                                sages_summary = parseSageSummary(data["sages_summary"]),
                                is_training = (data["is_training"] as? Boolean) ?: true
                            )
                            _isConnected.value = true
                        } catch (e: Exception) {
                            Log.e("FIRESTORE_DEBUG", "❌ Erreur parsing prediction: ${e.message}")
                        }
                    }
                }
            }
    }

    private fun startListeningLastCrashes() {
        Log.d("FIRESTORE_DEBUG", "👂 Début écoute sur: last_crashes / list")
        lastCrashesListenerRegistration = db.collection("last_crashes").document("list")
            .addSnapshotListener { snapshot, error ->
                if (error != null) {
                    Log.e("FIRESTORE_DEBUG", " Erreur last_crashes: ${error.message}")
                    return@addSnapshotListener
                }
                if (snapshot != null && snapshot.exists()) {
                    val data = snapshot.data
                    if (data != null) {
                        try {
                            val crashesRaw = data["crashes"] as? List<*>
                            val crashesList = crashesRaw?.mapNotNull { item ->
                                val crash = item as? Map<*, *> ?: return@mapNotNull null
                                CrashItem(
                                    value = crash["value"] as? String ?: "0.00x",
                                    raw_value = (crash["raw_value"] as? Number)?.toDouble() ?: 0.0,
                                    latency_ms = (crash["latency_ms"] as? Number)?.toInt() ?: 0,
                                    round_id = (crash["round_id"] as? Number)?.toLong() ?: 0L,
                                    timestamp = crash["timestamp"]?.toString()
                                )
                            } ?: emptyList()
                            _lastCrashes.value = crashesList
                        } catch (e: Exception) {
                            Log.e("FIRESTORE_DEBUG", "❌❌ ERREUR CRITIQUE PARSING CRASHS: ${e.message}", e)
                        }
                    }
                }
            }
    }

    private fun parseSageSummary(data: Any?): SageSummary? {
        return if (data is Map<*, *>) {
            SageSummary(
                memory = (data["memory"] as? String) ?: "0.00x (0%)",
                drift = (data["drift"] as? String) ?: "0.00x (0%)",
                velocity = (data["velocity"] as? String) ?: "0.00x (0%)"
            )
        } else null
    }

    fun fetchPerformanceStats() {
        viewModelScope.launch {
            kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.IO) {
                try {
                    Log.d("STATS_DEBUG", "📡 Tentative de connexion à: $backendBaseUrl/api/stats")
                    val url = URL("$backendBaseUrl/api/stats")
                    val connection = url.openConnection() as HttpURLConnection
                    connection.requestMethod = "GET"
                    connection.connectTimeout = 5000
                    connection.readTimeout = 5000

                    if (connection.responseCode == HttpURLConnection.HTTP_OK) {
                        val response = connection.inputStream.bufferedReader().use { it.readText() }
                        val json = JSONObject(response)
                        val status = json.optString("status")

                        if (status == "success") {
                            val regimeBreakdown = mutableMapOf<String, RegimeStat>()
                            val regimesJson = json.optJSONObject("regime_breakdown")
                            if (regimesJson != null) {
                                val keys = regimesJson.keys()
                                while (keys.hasNext()) {
                                    val key = keys.next()
                                    val obj = regimesJson.getJSONObject(key)
                                    regimeBreakdown[key] = RegimeStat(
                                        total = obj.optInt("total", 0),
                                        success = obj.optInt("success", 0),
                                        accuracy = obj.optDouble("accuracy", 0.0)
                                    )
                                }
                            }

                            val modelInfoJson = json.optJSONObject("model_info")
                            val modelInfo = if (modelInfoJson != null) {
                                ModelInfo(
                                    current_epoch = modelInfoJson.optInt("current_epoch", 0),
                                    total_rounds_trained = modelInfoJson.optInt("total_rounds_trained", 0)
                                )
                            } else null

                            _performanceStats.value = PerformanceStats(
                                status = "success",
                                message = "",
                                global_accuracy = json.optDouble("global_accuracy", 0.0),
                                average_error = json.optDouble("average_error", 0.0),
                                evolution_trend = json.optDouble("evolution_trend", 0.0),
                                total_evaluations = json.optInt("total_evaluations", 0),
                                regime_breakdown = regimeBreakdown,
                                model_info = modelInfo
                            )
                            Log.d("STATS_DEBUG", "✅ Statistiques chargées avec succès !")
                        } else {
                            // 🆕 GESTION EXPLICITE DU CAS "no_data"
                            val msg = json.optString("message", "En attente de données suffisantes...")
                            Log.w("STATS_DEBUG", "⚠️ Backend a répondu: $msg")
                            _performanceStats.value = PerformanceStats(
                                status = "no_data",
                                message = msg
                            )
                        }
                    } else {
                        Log.e("STATS_DEBUG", "❌ Erreur HTTP: ${connection.responseCode}")
                    }
                } catch (e: Exception) {
                    // 🆕 AFFICHAGE COMPLET DE L'ERREUR POUR LE DEBUG
                    Log.e("STATS_DEBUG", "❌ ÉCHEC DE CONNEXION AU BACKEND: ${e.message}")
                    e.printStackTrace()
                    _performanceStats.value = PerformanceStats(
                        status = "error",
                        message = "Impossible de joindre le serveur. Vérifie l'IP et le Pare-feu."
                    )
                }
            }
        }
    }

    fun stopPrediction() {
        _isUserStopped.value = true
        _isConnected.value = false
        listenerRegistration?.remove()
        lastCrashesListenerRegistration?.remove()
    }

    fun resumePrediction() {
        _isUserStopped.value = false
        startListening()
        startListeningLastCrashes()
    }

    fun getRegimeColor(regime: String): Int = when (regime.lowercase()) {
        "normal" -> 0xFF4CAF50.toInt()
        "high-rtp" -> 0xFF2196F3.toInt()
        "low-rtp" -> 0xFFFF9800.toInt()
        "volatile" -> 0xFFF44336.toInt()
        else -> 0xFF9E9E9E.toInt()
    }

    fun getRegimeIcon(regime: String): String = when (regime.lowercase()) {
        "normal" -> "🟢"
        "high-rtp" -> "🔵"
        "low-rtp" -> "🟠"
        "volatile" -> "🔴"
        else -> "⚪"
    }

    override fun onCleared() {
        listenerRegistration?.remove()
        lastCrashesListenerRegistration?.remove()
        Log.d("FIRESTORE_DEBUG", "🧹 ViewModel détruit, listeners supprimés")
    }
}