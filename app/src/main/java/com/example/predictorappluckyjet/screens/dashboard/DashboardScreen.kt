package com.example.predictorappluckyjet.screens.dashboard

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.*
import androidx.compose.animation.expandVertically
import androidx.compose.animation.shrinkVertically
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowDownward
import androidx.compose.material.icons.filled.ArrowUpward
import androidx.compose.material.icons.filled.ExpandLess
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.PowerSettingsNew
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.blur
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.example.predictorappluckyjet.ui.theme.*
import com.example.predictorappluckyjet.viewmodel.DashboardViewModel

@Composable
fun DashboardScreen(
    onShowHistory: () -> Unit,
    viewModel: DashboardViewModel = viewModel()
) {
    // ✅ États du ViewModel
    val prediction by viewModel.prediction.collectAsState()
    val isConnected by viewModel.isConnected.collectAsState()
    val isUserStopped by viewModel.isUserStopped.collectAsState()
    val lastCrashes by viewModel.lastCrashes.collectAsState()

    // 🆕 État pour les statistiques de performance
    val performanceStats by viewModel.performanceStats.collectAsState()

    var showAnalysis by remember { mutableStateOf(false) }
    val scrollState = rememberScrollState()

    // Animation de pulsation pour le statut
    val infiniteTransition = rememberInfiniteTransition(label = "pulse")
    val pulseAlpha by infiniteTransition.animateFloat(
        initialValue = 0.4f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(1000, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "pulse"
    )

    // Animation de rotation (seulement si connecté et non arrêté)
    val rotationAngle by infiniteTransition.animateFloat(
        initialValue = 0f,
        targetValue = if (isConnected && !isUserStopped) 360f else 0f,
        animationSpec = infiniteRepeatable(
            animation = tween(8000, easing = LinearEasing),
            repeatMode = RepeatMode.Restart
        ),
        label = "rotation"
    )

    // Conversion explicite Int → Color pour le régime
    val regimeColorInt = prediction?.regime?.let { viewModel.getRegimeColor(it) } ?: 0xFF9E9E9E.toInt()
    val regimeColor = Color(regimeColorInt)
    val regimeIcon = prediction?.regime?.let { viewModel.getRegimeIcon(it) } ?: "⚪"

    val displayLastCrash = lastCrashes.firstOrNull()?.value ?: "0.00x"

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(DeepSpacePurple)
    ) {
        // Effet de fond Nébuleuse
        Box(
            modifier = Modifier
                .size(400.dp)
                .align(Alignment.Center)
                .background(
                    Brush.radialGradient(
                        colors = listOf(NeonViolet.copy(alpha = 0.15f), Color.Transparent),
                        radius = 400f
                    )
                )
                .blur(80.dp)
        )

        // ✅ Column avec verticalScroll et padding bottom pour éviter les coupures
        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(scrollState)
                .padding(horizontal = 24.dp)
                .padding(bottom = 32.dp) // ✅ Remplace le Spacer final pour un scroll propre
        ) {
            // === TOP BAR ===
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 40.dp, bottom = 20.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                IconButton(onClick = {
                    if (isUserStopped) viewModel.resumePrediction() else viewModel.stopPrediction()
                }) {
                    Icon(
                        imageVector = if (isUserStopped) Icons.Default.PlayArrow else Icons.Default.PowerSettingsNew,
                        contentDescription = if (isUserStopped) "Relancer" else "Arrêter",
                        tint = if (isUserStopped) EmeraldGreen else ErrorRed,
                        modifier = Modifier.size(32.dp)
                    )
                }

                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        modifier = Modifier
                            .size(12.dp)
                            .background(
                                color = if (isConnected && !isUserStopped) EmeraldGreen else ElectricYellow,
                                shape = CircleShape
                            )
                    )
                    Spacer(modifier = Modifier.width(10.dp))
                    Text(
                        text = if (isUserStopped) "MOTEUR EN PAUSE" else if (isConnected) "MOTEUR EN LIGNE" else "DÉCONNECTÉ",
                        color = if (isUserStopped) ElectricYellow else if (isConnected) EmeraldGreen else ErrorRed,
                        style = MaterialTheme.typography.labelLarge,
                        fontWeight = FontWeight.Bold
                    )
                }

                IconButton(onClick = onShowHistory) {
                    Icon(
                        imageVector = Icons.Default.History,
                        contentDescription = "Historique",
                        tint = IceWhite,
                        modifier = Modifier.size(32.dp)
                    )
                }
            }

            // === DERNIER CRASH ===
            Column(
                modifier = Modifier.fillMaxWidth().padding(vertical = 8.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Text(
                    text = "DERNIER CRASH",
                    color = TextSecondary,
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.SemiBold,
                    letterSpacing = 2.sp
                )
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    text = displayLastCrash,
                    color = IceWhite,
                    style = MaterialTheme.typography.headlineLarge,
                    fontWeight = FontWeight.Bold
                )
            }

            // === LISTE HORIZONTALE DES DERNIERS CRASHS ===
            if (lastCrashes.isNotEmpty()) {
                Spacer(modifier = Modifier.height(16.dp))
                Text(
                    text = "HISTORIQUE RÉCENT",
                    color = TextSecondary,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold
                )
                Spacer(modifier = Modifier.height(8.dp))

                LazyRow(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    items(lastCrashes.take(10)) { crash ->
                        val crashColor = when {
                            crash.raw_value >= 10.0 -> EmeraldGreen
                            crash.raw_value >= 2.0 -> NeonViolet
                            else -> ErrorRed
                        }

                        Surface(
                            modifier = Modifier.height(50.dp).width(70.dp),
                            shape = RoundedCornerShape(12.dp),
                            color = GlassSurfaceMedium,
                            border = BorderStroke(1.5.dp, crashColor.copy(alpha = 0.6f))
                        ) {
                            Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                                Text(
                                    text = crash.value,
                                    color = crashColor,
                                    fontWeight = FontWeight.Bold,
                                    fontSize = 15.sp
                                )
                            }
                        }
                    }
                }
            } else {
                Spacer(modifier = Modifier.height(16.dp))
                Text(
                    text = "En attente des premiers crashs du serveur...",
                    color = TextSecondary.copy(alpha = 0.6f),
                    style = MaterialTheme.typography.bodyMedium,
                    modifier = Modifier.fillMaxWidth()
                )
            }

            // === PRÉDICTION AVEC CERCLE NÉON VIOLET ===
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(320.dp)
                    .padding(vertical = 16.dp),
                contentAlignment = Alignment.Center
            ) {
                Box(
                    modifier = Modifier
                        .size(280.dp)
                        .rotate(rotationAngle)
                        .background(
                            brush = Brush.sweepGradient(
                                colors = listOf(
                                    NeonViolet.copy(alpha = 0.8f),
                                    NeonViolet.copy(alpha = 0.2f),
                                    NeonViolet.copy(alpha = 0.8f),
                                    NeonViolet.copy(alpha = 0.2f)
                                )
                            ),
                            shape = CircleShape
                        )
                        .blur(8.dp)
                )

                Box(
                    modifier = Modifier
                        .size(260.dp)
                        .background(color = GlassSurfaceDark, shape = CircleShape)
                        .border(BorderStroke(3.dp, NeonViolet), CircleShape)
                        .shadow(elevation = 20.dp, shape = CircleShape, spotColor = NeonViolet.copy(alpha = 0.6f)),
                    contentAlignment = Alignment.Center
                ) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text(
                            text = "${prediction?.target_score ?: "0.00"}x",
                            style = MaterialTheme.typography.displayLarge.copy(
                                brush = Brush.linearGradient(
                                    colors = listOf(
                                        Color(0xFFFFE0B2), Color(0xFFFFB74D), Color(0xFFFF9800),
                                        Color(0xFFFFE0B2), Color(0xFFFFCC80)
                                    ),
                                    start = Offset(0f, 0f),
                                    end = Offset(1000f, 1000f)
                                )
                            ),
                            fontWeight = FontWeight.Black,
                            fontSize = 64.sp
                        )

                        if (isUserStopped) {
                            Spacer(modifier = Modifier.height(8.dp))
                            Text(
                                text = "Appuyez sur Play pour relancer",
                                color = ElectricYellow,
                                style = MaterialTheme.typography.bodySmall,
                                fontWeight = FontWeight.Medium
                            )
                        }
                    }
                }
            }

            // === CONFIANCE IA ===
            Column(
                modifier = Modifier.fillMaxWidth().padding(vertical = 8.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Text(
                    text = "CONFIANCE IA",
                    color = TextSecondary,
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.SemiBold,
                    letterSpacing = 2.sp
                )
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    text = "${prediction?.confidence ?: 0}%",
                    color = if ((prediction?.confidence ?: 0) > 70) EmeraldGreen else ElectricYellow,
                    style = MaterialTheme.typography.headlineLarge,
                    fontWeight = FontWeight.Bold
                )
            }

            // === INDICATEUR DE RÉGIME ===
            Card(
                modifier = Modifier.fillMaxWidth().padding(vertical = 8.dp),
                colors = CardDefaults.cardColors(containerColor = GlassSurfaceMedium),
                border = BorderStroke(1.dp, regimeColor.copy(alpha = 0.5f)),
                shape = RoundedCornerShape(12.dp)
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth().padding(16.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = "RÉGIME",
                        color = TextSecondary,
                        style = MaterialTheme.typography.labelLarge,
                        fontWeight = FontWeight.Medium
                    )
                    Text(
                        text = "$regimeIcon ${prediction?.regime?.uppercase() ?: "NORMAL"}",
                        color = regimeColor,
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold
                    )
                }
            }

            // === 🆕 DASHBOARD DE PERFORMANCE IA (Logique améliorée) ===
            when (performanceStats?.status) {
                "success" -> {
                    val stats = performanceStats!!
                    Spacer(modifier = Modifier.height(24.dp))
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        colors = CardDefaults.cardColors(containerColor = GlassSurfaceMedium),
                        border = BorderStroke(1.dp, EmeraldGreen.copy(alpha = 0.3f)),
                        shape = RoundedCornerShape(16.dp)
                    ) {
                        Column(modifier = Modifier.padding(16.dp)) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text(
                                    text = "📊 PERFORMANCE IA",
                                    color = EmeraldGreen,
                                    style = MaterialTheme.typography.titleMedium,
                                    fontWeight = FontWeight.Bold
                                )
                                IconButton(onClick = { viewModel.fetchPerformanceStats() }) {
                                    Icon(
                                        imageVector = Icons.Default.Refresh,
                                        contentDescription = "Actualiser",
                                        tint = IceWhite,
                                        modifier = Modifier.size(20.dp)
                                    )
                                }
                            }
                            Spacer(modifier = Modifier.height(12.dp))

                            // Ligne principale : Précision Globale et Évolution
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                    Text(
                                        text = "${stats.global_accuracy}%",
                                        color = when {
                                            stats.global_accuracy >= 95.0 -> EmeraldGreen
                                            stats.global_accuracy >= 80.0 -> ElectricYellow
                                            else -> ErrorRed
                                        },
                                        style = MaterialTheme.typography.headlineLarge,
                                        fontWeight = FontWeight.Black
                                    )
                                    Text(
                                        text = "Précision Globale",
                                        color = TextSecondary,
                                        style = MaterialTheme.typography.bodySmall
                                    )
                                }

                                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                    Row(verticalAlignment = Alignment.CenterVertically) {
                                        Icon(
                                            imageVector = if (stats.evolution_trend >= 0) Icons.Default.ArrowUpward else Icons.Default.ArrowDownward,
                                            contentDescription = "Tendance",
                                            tint = if (stats.evolution_trend >= 0) EmeraldGreen else ErrorRed,
                                            modifier = Modifier.size(24.dp)
                                        )
                                        Text(
                                            text = "${if (stats.evolution_trend >= 0) "+" else ""}${stats.evolution_trend}%",
                                            color = if (stats.evolution_trend >= 0) EmeraldGreen else ErrorRed,
                                            style = MaterialTheme.typography.titleMedium,
                                            fontWeight = FontWeight.Bold
                                        )
                                    }
                                    Text(
                                        text = "Évolution (100 tours)",
                                        color = TextSecondary,
                                        style = MaterialTheme.typography.bodySmall
                                    )
                                }
                            }

                            Spacer(modifier = Modifier.height(16.dp))
                            HorizontalDivider(color = NeonBorderViolet.copy(alpha = 0.3f))
                            Spacer(modifier = Modifier.height(12.dp))

                            // Détail par régime
                            Text(
                                text = "Précision par Régime",
                                color = TextSecondary,
                                style = MaterialTheme.typography.bodyMedium,
                                fontWeight = FontWeight.SemiBold,
                                modifier = Modifier.padding(bottom = 8.dp)
                            )

                            if (stats.regime_breakdown.isNotEmpty()) {
                                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                    stats.regime_breakdown.forEach { (regime, stat) ->
                                        Row(
                                            modifier = Modifier.fillMaxWidth(),
                                            horizontalArrangement = Arrangement.SpaceBetween,
                                            verticalAlignment = Alignment.CenterVertically
                                        ) {
                                            Row(verticalAlignment = Alignment.CenterVertically) {
                                                Text(
                                                    text = viewModel.getRegimeIcon(regime),
                                                    fontSize = 16.sp
                                                )
                                                Spacer(modifier = Modifier.width(8.dp))
                                                Text(
                                                    text = regime.replaceFirstChar { it.uppercase() },
                                                    color = IceWhite,
                                                    style = MaterialTheme.typography.bodyMedium
                                                )
                                            }
                                            Row(verticalAlignment = Alignment.CenterVertically) {
                                                LinearProgressIndicator(
                                                    progress = { (stat.accuracy.toFloat() / 100f).coerceIn(0f, 1f) },
                                                    modifier = Modifier.width(80.dp).height(6.dp),
                                                    color = Color(viewModel.getRegimeColor(regime)),
                                                    trackColor = GlassSurfaceDark
                                                )
                                                Spacer(modifier = Modifier.width(8.dp))
                                                Text(
                                                    text = "${stat.accuracy.toInt()}%",
                                                    color = IceWhite,
                                                    style = MaterialTheme.typography.bodyMedium,
                                                    fontWeight = FontWeight.Bold
                                                )
                                            }
                                        }
                                    }
                                }
                            } else {
                                Text(
                                    text = "Aucune donnée par régime disponible",
                                    color = TextSecondary.copy(alpha = 0.6f),
                                    style = MaterialTheme.typography.bodySmall
                                )
                            }

                            Spacer(modifier = Modifier.height(12.dp))
                            Text(
                                text = "Tours évalués: ${stats.total_evaluations} | Epoch: ${stats.model_info?.current_epoch ?: 0} | Entraînements: ${stats.model_info?.total_rounds_trained ?: 0}",
                                color = TextSecondary.copy(alpha = 0.7f),
                                style = MaterialTheme.typography.bodySmall,
                                modifier = Modifier.fillMaxWidth()
                            )
                        }
                    }
                }

                "no_data" -> {
                    // 🆕 Affiche le message du backend au lieu du spinner infini
                    Spacer(modifier = Modifier.height(24.dp))
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        colors = CardDefaults.cardColors(containerColor = GlassSurfaceMedium),
                        shape = RoundedCornerShape(16.dp)
                    ) {
                        Row(
                            modifier = Modifier.padding(16.dp).fillMaxWidth(),
                            horizontalArrangement = Arrangement.Center,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(
                                text = performanceStats?.message ?: "En attente de données...",
                                color = ElectricYellow,
                                style = MaterialTheme.typography.bodyMedium,
                                fontWeight = FontWeight.Medium
                            )
                        }
                    }
                }

                "error" -> {
                    // 🆕 Affiche l'erreur de connexion
                    Spacer(modifier = Modifier.height(24.dp))
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        colors = CardDefaults.cardColors(containerColor = GlassSurfaceMedium),
                        shape = RoundedCornerShape(16.dp)
                    ) {
                        Row(
                            modifier = Modifier.padding(16.dp).fillMaxWidth(),
                            horizontalArrangement = Arrangement.Center,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(
                                text = performanceStats?.message ?: "Erreur de connexion",
                                color = ErrorRed,
                                style = MaterialTheme.typography.bodyMedium,
                                fontWeight = FontWeight.Medium
                            )
                        }
                    }
                }

                else -> {
                    // Seul cas où on affiche le spinner (au tout premier lancement)
                    Spacer(modifier = Modifier.height(24.dp))
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        colors = CardDefaults.cardColors(containerColor = GlassSurfaceMedium),
                        shape = RoundedCornerShape(16.dp)
                    ) {
                        Row(
                            modifier = Modifier.padding(16.dp).fillMaxWidth(),
                            horizontalArrangement = Arrangement.Center,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            CircularProgressIndicator(
                                modifier = Modifier.size(24.dp),
                                color = ElectricYellow,
                                strokeWidth = 2.dp
                            )
                            Spacer(modifier = Modifier.width(12.dp))
                            Text(
                                text = "Connexion au tableau de bord...",
                                color = TextSecondary,
                                style = MaterialTheme.typography.bodyMedium
                            )
                        }
                    }
                }
            }

            // === MODEL EPOCH (Legacy, conservé pour compatibilité) ===
            if ((prediction?.model_epoch ?: 0) > 0) {
                Spacer(modifier = Modifier.height(8.dp)) // ✅ Ajout d'espacement
                Text(
                    text = "🎓 Modèle v${prediction?.model_epoch} | Round #${prediction?.round_id ?: 0}",
                    color = TextSecondary.copy(alpha = 0.7f),
                    style = MaterialTheme.typography.bodySmall,
                    modifier = Modifier.padding(vertical = 4.dp)
                )
            }

            // === BOUTON AFFICHER/MASQUER L'ANALYSE ===
            Spacer(modifier = Modifier.height(16.dp)) // ✅ ESPACEMENT CRITIQUE AJOUTÉ ICI
            Button(
                onClick = { showAnalysis = !showAnalysis },
                modifier = Modifier.fillMaxWidth().height(60.dp),
                shape = RoundedCornerShape(16.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = GlassSurfaceMedium,
                    contentColor = IceWhite
                ),
                border = BorderStroke(1.dp, NeonBorderViolet),
                enabled = !isUserStopped
            ) {
                Text(
                    text = if (showAnalysis) "MASQUER L'ANALYSE" else "AFFICHER L'ANALYSE",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    letterSpacing = 1.sp
                )
                Spacer(modifier = Modifier.width(12.dp))
                Icon(
                    imageVector = if (showAnalysis) Icons.Default.ExpandLess else Icons.Default.ExpandMore,
                    contentDescription = null
                )
            }

            // === SECTION ANALYSE DÉROULANTE ===
            // ✅ CORRECTION CRITIQUE : Envelopper le contenu dans une Column pour une animation stable
            // Cela empêche Compose de mal calculer la hauteur lors de l'expansion dans un verticalScroll
            AnimatedVisibility(
                visible = showAnalysis,
                enter = expandVertically(animationSpec = tween(300, easing = FastOutSlowInEasing)),
                exit = shrinkVertically(animationSpec = tween(300, easing = FastOutSlowInEasing))
            ) {
                Column {
                    Spacer(modifier = Modifier.height(16.dp))
                    Surface(
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(20.dp),
                        color = GlassSurfaceDark,
                        border = BorderStroke(1.dp, NeonBorderViolet)
                    ) {
                        Column(modifier = Modifier.padding(20.dp)) {
                            Text(
                                text = "🤖 ÉTAT MÉTA-IA",
                                color = NeonViolet,
                                style = MaterialTheme.typography.titleMedium,
                                fontWeight = FontWeight.Bold
                            )
                            Spacer(modifier = Modifier.height(8.dp))
                            Text(
                                text = prediction?.meta_state ?: "En attente de données...",
                                color = IceWhite,
                                style = MaterialTheme.typography.bodyLarge
                            )

                            Spacer(modifier = Modifier.height(20.dp))

                            Text(
                                text = "🏛️ VOTE DES SAGES",
                                color = NeonViolet,
                                style = MaterialTheme.typography.titleMedium,
                                fontWeight = FontWeight.Bold
                            )
                            Spacer(modifier = Modifier.height(12.dp))

                            prediction?.sages_summary?.let { sages ->
                                Row(
                                    modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
                                    horizontalArrangement = Arrangement.SpaceBetween
                                ) {
                                    Text(text = "• Memory", color = TextSecondary, style = MaterialTheme.typography.bodyLarge)
                                    Text(text = sages.memory, color = IceWhite, style = MaterialTheme.typography.bodyLarge, fontWeight = FontWeight.Medium)
                                }
                                Row(
                                    modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
                                    horizontalArrangement = Arrangement.SpaceBetween
                                ) {
                                    Text(text = "• Drift", color = TextSecondary, style = MaterialTheme.typography.bodyLarge)
                                    Text(text = sages.drift, color = IceWhite, style = MaterialTheme.typography.bodyLarge, fontWeight = FontWeight.Medium)
                                }
                                Row(
                                    modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
                                    horizontalArrangement = Arrangement.SpaceBetween
                                ) {
                                    Text(text = "• Velocity", color = TextSecondary, style = MaterialTheme.typography.bodyLarge)
                                    Text(text = sages.velocity, color = IceWhite, style = MaterialTheme.typography.bodyLarge, fontWeight = FontWeight.Medium)
                                }
                            } ?: run {
                                Text(
                                    text = "Données des sages non disponibles",
                                    color = TextSecondary.copy(alpha = 0.6f),
                                    style = MaterialTheme.typography.bodyMedium
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}