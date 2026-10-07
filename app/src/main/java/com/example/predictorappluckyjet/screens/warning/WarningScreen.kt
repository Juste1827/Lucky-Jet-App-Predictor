package com.example.predictorappluckyjet.screens.warning

import androidx.compose.animation.core.*
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material.icons.filled.Block
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.blur
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.predictorappluckyjet.ui.theme.*
import kotlinx.coroutines.delay

@Composable
fun WarningScreen(onFinished: () -> Unit) {
    // Animation de pulsation pour l'icône d'avertissement
    val infiniteTransition = rememberInfiniteTransition(label = "warning_pulse")
    val pulseScale by infiniteTransition.animateFloat(
        initialValue = 1f,
        targetValue = 1.1f,
        animationSpec = infiniteRepeatable(
            animation = tween(1000, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "pulseScale"
    )

    // Compte à rebours de 15 secondes
    var timeLeft by remember { mutableStateOf(15) }

    LaunchedEffect(Unit) {
        for (i in 15 downTo 0) {
            timeLeft = i
            delay(1000)
        }
        onFinished()
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(Color(0xFF0D0221)), // Fond très sombre (presque noir-violet)
        contentAlignment = Alignment.Center
    ) {
        // Effet de fond rouge/orange d'avertissement
        Box(
            modifier = Modifier
                .size(500.dp)
                .background(
                    Brush.radialGradient(
                        colors = listOf(
                            Color(0xFFFF6B35).copy(alpha = 0.15f), // Orange-rouge
                            Color.Transparent
                        ),
                        radius = 500f
                    )
                )
                .blur(80.dp)
        )

        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            // Icône d'avertissement avec animation
            Box(
                modifier = Modifier
                    .size(120.dp)
                    .background(
                        Brush.radialGradient(
                            colors = listOf(
                                Color(0xFFFFB74D).copy(alpha = 0.3f),
                                Color.Transparent
                            )
                        ),
                        shape = RoundedCornerShape(50)
                    )
                    .scale(pulseScale),
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    imageVector = Icons.Default.Warning,
                    contentDescription = "Avertissement",
                    tint = Color(0xFFFFB74D), // Orange doux
                    modifier = Modifier.size(80.dp)
                )
            }

            Spacer(modifier = Modifier.height(24.dp))

            // Titre principal
            Text(
                text = "AVERTISSEMENT",
                color = Color(0xFFFF6B35), // Orange-rouge vif
                style = MaterialTheme.typography.headlineMedium,
                fontWeight = FontWeight.Black,
                textAlign = TextAlign.Center,
                letterSpacing = 2.sp
            )

            Text(
                text = "IMPORTANT",
                color = Color(0xFFFFB74D), // Orange plus clair
                style = MaterialTheme.typography.headlineMedium,
                fontWeight = FontWeight.Bold,
                textAlign = TextAlign.Center,
                letterSpacing = 2.sp
            )

            Spacer(modifier = Modifier.height(24.dp))

            // Boîte de message principale - FOND SOMBRE pour meilleur contraste
            Surface(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(20.dp),
                color = Color(0xFF1A0B2E).copy(alpha = 0.95f), // Fond sombre violet
                border = androidx.compose.foundation.BorderStroke(
                    2.dp,
                    Brush.verticalGradient(
                        colors = listOf(Color(0xFFFF6B35), Color(0xFF9C27B0))
                    )
                )
            ) {
                Column(modifier = Modifier.padding(24.dp)) {
                    // Point 1
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = "",
                            fontSize = 24.sp
                        )
                        Spacer(modifier = Modifier.width(12.dp))
                        Text(
                            text = "Aucune prédiction n'est fiable à 100%",
                            color = Color(0xFFE0E0E0), // Blanc cassé très lisible
                            style = MaterialTheme.typography.bodyLarge,
                            fontWeight = FontWeight.Bold,
                            lineHeight = 24.sp
                        )
                    }

                    Spacer(modifier = Modifier.height(20.dp))

                    // Point 2
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.Top
                    ) {
                        Text(
                            text = "🎲",
                            fontSize = 24.sp
                        )
                        Spacer(modifier = Modifier.width(12.dp))
                        Column {
                            Text(
                                text = "Lucky Jet est un jeu de hasard",
                                color = Color(0xFFFFB74D), // Orange
                                style = MaterialTheme.typography.bodyMedium,
                                fontWeight = FontWeight.SemiBold
                            )
                            Text(
                                text = "Les prédictions sont des estimations statistiques et ne garantissent aucun résultat.",
                                color = Color(0xFFB0B0B0), // Gris clair lisible
                                style = MaterialTheme.typography.bodyMedium,
                                lineHeight = 22.sp
                            )
                        }
                    }

                    Spacer(modifier = Modifier.height(20.dp))

                    // Point 3
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = "⚡",
                            fontSize = 24.sp
                        )
                        Spacer(modifier = Modifier.width(12.dp))
                        Text(
                            text = "Jouez de manière responsable",
                            color = Color(0xFF4CAF50), // Vert
                            style = MaterialTheme.typography.bodyLarge,
                            fontWeight = FontWeight.Bold,
                            lineHeight = 24.sp
                        )
                    }

                    Spacer(modifier = Modifier.height(12.dp))

                    Text(
                        text = "Ne jouez que l'argent que vous pouvez vous permettre de perdre. Fixez-vous des limites.",
                        color = Color(0xFFB0B0B0), // Gris clair
                        style = MaterialTheme.typography.bodyMedium,
                        lineHeight = 22.sp,
                        textAlign = TextAlign.Center,
                        modifier = Modifier.fillMaxWidth()
                    )
                }
            }

            Spacer(modifier = Modifier.height(24.dp))

            // Badge -18 ans bien visible - FOND VIOLET avec bordure rouge
            Surface(
                shape = RoundedCornerShape(16.dp),
                color = Color(0xFF1A0B2E).copy(alpha = 0.95f),
                modifier = Modifier
                    .fillMaxWidth()
                    .height(80.dp)
                    .border(
                        3.dp,
                        Brush.horizontalGradient(
                            colors = listOf(Color(0xFFFF6B35), Color(0xFFD32F2F))
                        ),
                        RoundedCornerShape(16.dp)
                    )
            ) {
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(horizontal = 24.dp),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = "INTERDIT AUX MINEURS   - 18 ANS",
                        color = Color.White,
                        style = MaterialTheme.typography.titleLarge,
                        fontWeight = FontWeight.Black,
                        textAlign = TextAlign.Center,
                        letterSpacing = 1.5.sp,
                        modifier = Modifier.fillMaxWidth()
                    )
                }
            }

            Spacer(modifier = Modifier.height(20.dp))

            // Texte légal
            Text(
                text = "En continuant, vous reconnaissez avoir lu et accepté ces conditions. L'utilisation de cette application est à vos propres risques.",
                color = Color(0xFF808080), // Gris moyen
                style = MaterialTheme.typography.bodySmall,
                textAlign = TextAlign.Center,
                lineHeight = 18.sp,
                modifier = Modifier.padding(horizontal = 16.dp)
            )

            Spacer(modifier = Modifier.height(32.dp))

            // Compte à rebours amélioré - PLUS VISIBLE ET IMPACTANT
            Surface(
                shape = RoundedCornerShape(20.dp),
                color = Color(0xFF1A0B2E).copy(alpha = 0.9f),
                border = androidx.compose.foundation.BorderStroke(2.dp, NeonViolet),
                modifier = Modifier
                    .fillMaxWidth()
                    .height(100.dp)
            ) {
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(horizontal = 24.dp),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = "Redirection dans $timeLeft secondes",
                        color = Color.White,
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        textAlign = TextAlign.Center,
                        modifier = Modifier.fillMaxWidth()
                    )
                }
            }
        }
    }
}