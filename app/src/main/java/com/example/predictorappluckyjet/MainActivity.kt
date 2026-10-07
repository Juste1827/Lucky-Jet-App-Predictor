package com.example.predictorappluckyjet

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import com.example.predictorappluckyjet.screens.dashboard.DashboardScreen
import com.example.predictorappluckyjet.screens.history.HistoryScreen
import com.example.predictorappluckyjet.screens.login.LoginScreen
import com.example.predictorappluckyjet.screens.onboarding.OnboardingScreen
import com.example.predictorappluckyjet.screens.splash.SplashScreen
import com.example.predictorappluckyjet.screens.warning.WarningScreen // ✅ Ajout de l'import
import com.example.predictorappluckyjet.ui.theme.PredictorAppLuckyJetTheme
import com.example.predictorappluckyjet.utils.SessionManager

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        setContent {
            PredictorAppLuckyJetTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    var currentScreen by remember { mutableStateOf("splash") }

                    val isLoggedIn = SessionManager.isLoggedIn(this)

                    when (currentScreen) {
                        "splash" -> {
                            SplashScreen(
                                onFinished = {
                                    // Après le logo (5s), on passe à l'avertissement
                                    currentScreen = "warning"
                                }
                            )
                        }
                        "warning" -> {
                            WarningScreen(
                                onFinished = {
                                    // Après l'avertissement (15s), on redirige selon la connexion
                                    currentScreen = if (isLoggedIn) "dashboard" else "onboarding"
                                }
                            )
                        }
                        "onboarding" -> {
                            OnboardingScreen(onFinished = { currentScreen = "login" })
                        }
                        "login" -> {
                            LoginScreen(onLoginSuccess = { currentScreen = "dashboard" })
                        }
                        "dashboard" -> {
                            DashboardScreen(
                                onShowHistory = { currentScreen = "history" }
                            )
                        }
                        "history" -> {
                            HistoryScreen(
                                onBack = { currentScreen = "dashboard" }
                            )
                        }
                    }
                }
            }
        }
    }
}