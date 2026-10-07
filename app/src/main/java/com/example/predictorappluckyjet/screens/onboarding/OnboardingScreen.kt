package com.example.predictorappluckyjet.screens.onboarding

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.core.*
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.blur
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil.compose.AsyncImage
import com.example.predictorappluckyjet.ui.theme.*

// Données des pages d'onboarding
data class OnboardingPage(
    val title: String,
    val description: String
)

val onboardingPages = listOf(
    OnboardingPage(
        title = "Précision Chirurgicale",
        description = "Notre IA analyse les flux WebSocket en temps réel pour détecter les motifs cachés et les dettes de variance du jeu."
    ),
    OnboardingPage(
        title = "Moteur Neuronal Dual",
        description = "Trois sages algorithmiques et un espion de télémétrie travaillent en synergie pour valider chaque prédiction."
    ),
    OnboardingPage(
        title = "Prêt au Décollage",
        description = "Synchronisez votre compte en toute sécurité et laissez l'algorithme calculer les probabilités pour vous."
    )
)

// URL de votre logo Firebase
const val APP_LOGO_URL = "https://firebasestorage.googleapis.com/v0/b/lucky-jet-6f1bb.firebasestorage.app/o/ChatGPT%20Image%2022%20juil.%202026%2C%2001_48_46.png?alt=media&token=576c9cdc-2435-4f2f-bf9b-5cff145d6b1f"

@Composable
fun OnboardingScreen(onFinished: () -> Unit) {
    var currentPage by remember { mutableStateOf(0) }

    // Animation de flottement pour le logo (effet de propulsion)
    val infiniteTransition = rememberInfiniteTransition(label = "float")
    val offsetY by infiniteTransition.animateFloat(
        initialValue = 0f,
        targetValue = -20f,
        animationSpec = infiniteRepeatable(
            animation = tween(2000, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "offsetY"
    )

    // Animation de lueur (glow) autour du logo
    val glowAlpha by infiniteTransition.animateFloat(
        initialValue = 0.3f,
        targetValue = 0.8f,
        animationSpec = infiniteRepeatable(
            animation = tween(1500, easing = LinearEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "glowAlpha"
    )

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(DeepSpacePurple)
    ) {
        // Effet de fond : Nébuleuse / Glow
        Box(
            modifier = Modifier
                .size(400.dp)
                .align(Alignment.TopCenter)
                .offset(y = (-100).dp)
                .background(
                    Brush.radialGradient(
                        colors = listOf(NeonViolet.copy(alpha = glowAlpha), Color.Transparent),
                        radius = 400f
                    )
                )
                .blur(50.dp)
        )

        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.SpaceBetween
        ) {
            Spacer(modifier = Modifier.height(40.dp))

            // ✅ Zone du LOGO avec effet de lueur et flottement
            Box(
                modifier = Modifier
                    .size(200.dp)
                    .offset(y = offsetY.dp),
                contentAlignment = Alignment.Center
            ) {
                // Cercle de lueur derrière le logo
                Box(
                    modifier = Modifier
                        .size(220.dp)
                        .background(
                            Brush.radialGradient(
                                colors = listOf(
                                    NeonViolet.copy(alpha = 0.4f),
                                    Color.Transparent
                                )
                            ),
                            shape = RoundedCornerShape(50)
                        )
                        .blur(20.dp)
                )

                // Le logo lui-même
                AsyncImage(
                    model = APP_LOGO_URL,
                    contentDescription = "Logo Lucky Jet Predictor",
                    modifier = Modifier
                        .size(180.dp)
                        .clip(RoundedCornerShape(50))
                        .background(GlassSurfaceMedium),
                    contentScale = ContentScale.Crop
                )
            }

            Spacer(modifier = Modifier.height(32.dp))

            // Contenu de la page avec transition fluide
            AnimatedContent(
                targetState = currentPage,
                label = "PageTransition",
                modifier = Modifier.weight(1f)
            ) { targetPage ->
                Column(
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.Center,
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text(
                        text = onboardingPages[targetPage].title,
                        style = MaterialTheme.typography.headlineLarge,
                        color = IceWhite,
                        fontWeight = FontWeight.Bold,
                        textAlign = TextAlign.Center
                    )

                    Spacer(modifier = Modifier.height(16.dp))

                    Text(
                        text = onboardingPages[targetPage].description,
                        style = MaterialTheme.typography.bodyLarge,
                        color = TextSecondary,
                        textAlign = TextAlign.Center,
                        lineHeight = 24.sp
                    )
                }
            }

            // Indicateurs de page (Dots)
            Row(
                horizontalArrangement = Arrangement.Center,
                modifier = Modifier.padding(bottom = 16.dp)
            ) {
                onboardingPages.forEachIndexed { index, _ ->
                    Box(
                        modifier = Modifier
                            .padding(horizontal = 4.dp)
                            .size(if (index == currentPage) 24.dp else 8.dp, 8.dp)
                            .clip(RoundedCornerShape(4.dp))
                            .background(
                                if (index == currentPage) NeonViolet else TextDisabled
                            )
                    )
                }
            }

            // Bouton d'action
            Button(
                onClick = {
                    if (currentPage < onboardingPages.lastIndex) {
                        currentPage++
                    } else {
                        onFinished()
                    }
                },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(56.dp),
                shape = RoundedCornerShape(16.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = NeonViolet,
                    contentColor = PureWhite
                )
            ) {
                Text(
                    text = if (currentPage < onboardingPages.lastIndex) "SUIVANT" else "COMMENCER L'EXPÉRIENCE",
                    style = MaterialTheme.typography.labelLarge,
                    fontWeight = FontWeight.Bold,
                    letterSpacing = 1.sp
                )
            }

            Spacer(modifier = Modifier.height(24.dp))
        }
    }
}