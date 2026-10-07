package com.example.predictorappluckyjet.screens.splash

import androidx.compose.animation.core.*
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.blur
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.dp
import com.example.predictorappluckyjet.R // ✅ Import du dossier R de votre application
import com.example.predictorappluckyjet.ui.theme.*
import kotlinx.coroutines.delay

@Composable
fun SplashScreen(onFinished: () -> Unit) {
    // ✅ Délai augmenté à 5 secondes (5000 ms) pour un affichage bien visible et premium
    LaunchedEffect(Unit) {
        delay(5000)
        onFinished()
    }

    // Animation de flottement
    val infiniteTransition = rememberInfiniteTransition(label = "splash_float")
    val offsetY by infiniteTransition.animateFloat(
        initialValue = 0f,
        targetValue = -15f,
        animationSpec = infiniteRepeatable(
            animation = tween(2500, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "offsetY"
    )

    // Animation de lueur
    val glowAlpha by infiniteTransition.animateFloat(
        initialValue = 0.3f,
        targetValue = 0.8f,
        animationSpec = infiniteRepeatable(
            animation = tween(2500, easing = LinearEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "glowAlpha"
    )

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(DeepSpacePurple),
        contentAlignment = Alignment.Center
    ) {
        // Effet de fond Nébuleuse
        Box(
            modifier = Modifier
                .size(400.dp)
                .align(Alignment.Center)
                .background(
                    Brush.radialGradient(
                        colors = listOf(NeonViolet.copy(alpha = glowAlpha), Color.Transparent),
                        radius = 400f
                    )
                )
                .blur(60.dp)
        )

        // Logo avec animation (Chargement LOCAL instantané)
        Box(
            modifier = Modifier
                .size(180.dp)
                .offset(y = offsetY.dp),
            contentAlignment = Alignment.Center
        ) {
            // Cercle de lueur derrière le logo
            Box(
                modifier = Modifier
                    .size(200.dp)
                    .background(
                        Brush.radialGradient(
                            colors = listOf(NeonViolet.copy(alpha = 0.4f), Color.Transparent)
                        ),
                        shape = RoundedCornerShape(50)
                    )
                    .blur(20.dp)
            )

            // ✅ Utilisation de painterResource pour un chargement instantané (0 ms de latence)
            Image(
                painter = painterResource(id = R.drawable.logo_splash), // Assurez-vous que le nom correspond à votre fichier
                contentDescription = "Logo Lucky Jet Predictor",
                modifier = Modifier
                    .size(160.dp)
                    .clip(RoundedCornerShape(50))
                    .background(GlassSurfaceMedium),
                contentScale = ContentScale.Crop
            )
        }
    }
}