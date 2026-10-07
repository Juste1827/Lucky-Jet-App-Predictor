package com.example.predictorappluckyjet.viewmodel

import android.util.Log
import androidx.lifecycle.ViewModel
import com.google.firebase.firestore.FirebaseFirestore
import com.google.firebase.firestore.ListenerRegistration
import com.google.firebase.firestore.Query
import com.google.firebase.Timestamp
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

data class HistoryItem(
    val predicted_threshold: Double = 0.0, val actual_crash: Double = 0.0,
    val confidence_at_time: Int = 0, val was_successful: Boolean = false,
    val regime: String = "normal", val timestamp: Long = System.currentTimeMillis()
)

class HistoryViewModel : ViewModel() {
    // ⚠️ VÉRIFIE QUE CETTE LIGNE CONTIENT BIEN "app-predictor-lucky-jet"
    private val db = FirebaseFirestore.getInstance("app-predictor-lucky-jet")

    private val _history = MutableStateFlow<List<HistoryItem>>(emptyList())
    val history: StateFlow<List<HistoryItem>> = _history.asStateFlow()

    private val _isLoading = MutableStateFlow(true)
    val isLoading: StateFlow<Boolean> = _isLoading.asStateFlow()

    private var listenerRegistration: ListenerRegistration? = null

    init {
        Log.d("FIRESTORE_DEBUG", "🚀 Initialisation HistoryViewModel...")
        startListeningHistory()
    }

    private fun startListeningHistory() {
        Log.d("FIRESTORE_DEBUG", "👂 Début écoute sur: collection 'history'")
        listenerRegistration = db.collection("history")
            .orderBy("timestamp", Query.Direction.DESCENDING)
            .limit(50)
            .addSnapshotListener { snapshot, error ->
                if (error != null) {
                    Log.e("FIRESTORE_DEBUG", "❌ Erreur écoute history: ${error.message}") // ⚠️ Regarde cette ligne !
                    _isLoading.value = false
                    return@addSnapshotListener
                }

                if (snapshot != null) {
                    Log.d("FIRESTORE_DEBUG", "📦 Snapshot history reçu. Nombre de documents: ${snapshot.documents.size}")
                    try {
                        val historyList = snapshot.documents.mapNotNull { doc ->
                            val data = doc.data ?: return@mapNotNull null
                            val timestampLong = when (val ts = data["timestamp"]) {
                                is Timestamp -> ts.toDate().time
                                is Long -> ts
                                is Number -> ts.toLong()
                                else -> System.currentTimeMillis()
                            }
                            HistoryItem(
                                predicted_threshold = (data["predicted_threshold"] as? Number)?.toDouble() ?: 0.0,
                                actual_crash = (data["actual_crash"] as? Number)?.toDouble() ?: 0.0,
                                confidence_at_time = (data["confidence_at_time"] as? Number)?.toInt() ?: 0,
                                was_successful = data["was_successful"] as? Boolean ?: false,
                                regime = data["regime"] as? String ?: "normal",
                                timestamp = timestampLong
                            )
                        }
                        _history.value = historyList
                        _isLoading.value = false
                        Log.d("FIRESTORE_DEBUG", "✅✅✅ SUCCÈS: ${historyList.size} éléments d'historique affichés !")
                    } catch (e: Exception) {
                        Log.e("FIRESTORE_DEBUG", "❌❌❌ ERREUR CRITIQUE PARSING HISTORY: ${e.message}", e)
                        _isLoading.value = false
                    }
                }
            }
    }

    override fun onCleared() {
        listenerRegistration?.remove()
    }
}