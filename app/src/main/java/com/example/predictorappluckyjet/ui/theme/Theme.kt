package com.example.predictorappluckyjet.ui.theme

import android.app.Activity
import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.core.view.WindowCompat

// ==========================================
// 🎭 THÈME CYBERPUNK DARK (Défaut)
// ==========================================

private val DarkColorScheme = darkColorScheme(
    primary = NeonViolet,
    secondary = RocketOrange,
    tertiary = ElectricYellow,

    background = DeepSpacePurple,
    surface = DarkPurple,

    onPrimary = PureWhite,
    onSecondary = PureWhite,
    onTertiary = DeepSpacePurple,
    onBackground = IceWhite,
    onSurface = IceWhite,

    primaryContainer = DarkPurple,
    secondaryContainer = DeepSpacePurple,
    tertiaryContainer = DarkPurple,

    error = ErrorRed,
    onError = PureWhite,
    errorContainer = DarkPurple,
    onErrorContainer = IceWhite
)

// ==========================================
// 🌞 THÈME LIGHT (Optionnel)
// ==========================================

private val LightColorScheme = lightColorScheme(
    primary = NeonViolet,
    secondary = RocketOrange,
    tertiary = ElectricYellow,

    background = IceWhite,
    surface = PureWhite,

    onPrimary = DeepSpacePurple,
    onSecondary = DeepSpacePurple,
    onTertiary = DeepSpacePurple,
    onBackground = DeepSpacePurple,
    onSurface = DeepSpacePurple,

    primaryContainer = LightViolet,
    secondaryContainer = BrightOrange,
    tertiaryContainer = GoldYellow
)

// ==========================================
//  COMPOSANT THÈME PRINCIPAL
// ==========================================

@Composable
fun PredictorAppLuckyJetTheme(
    darkTheme: Boolean = true, // Toujours dark theme par défaut
    dynamicColor: Boolean = false, // Désactivé pour garder les couleurs cyberpunk
    content: @Composable () -> Unit
) {
    val colorScheme = when {
        dynamicColor && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S -> {
            val context = LocalContext.current
            if (darkTheme) dynamicDarkColorScheme(context) else dynamicLightColorScheme(context)
        }
        darkTheme -> DarkColorScheme
        else -> LightColorScheme
    }

    val view = LocalView.current
    if (!view.isInEditMode) {
        SideEffect {
            val window = (view.context as Activity).window
            window.statusBarColor = DeepSpacePurple.toArgb()
            window.navigationBarColor = DeepSpacePurple.toArgb()
            WindowCompat.getInsetsController(window, view).isAppearanceLightStatusBars = darkTheme
            WindowCompat.getInsetsController(window, view).isAppearanceLightNavigationBars = darkTheme
        }
    }

    MaterialTheme(
        colorScheme = colorScheme,
        typography = Typography,
        content = content
    )
}

// ==========================================
// 🎯 EXTENSIONS POUR GLASSMORPHISM
// ==========================================

object GlassEffect {
    val Light = GlassSurfaceLight
    val Medium = GlassSurfaceMedium
    val Dark = GlassSurfaceDark
}

object NeonBorders {
    val Violet = NeonBorderViolet
    val Orange = NeonBorderOrange
    val Green = NeonBorderGreen
}