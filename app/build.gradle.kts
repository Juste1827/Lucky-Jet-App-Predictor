plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
    // On applique le plugin Google Services
    alias(libs.plugins.google.services)
}

android {
    namespace = "com.example.predictorappluckyjet"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.example.predictorappluckyjet"
        minSdk = 24
        targetSdk = 35
        versionCode = 1
        versionName = "1.0"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
    buildFeatures {
        compose = true
    }
}

dependencies {
    // ==========================================
    // 🔥 NOUVELLES DÉPENDANCES POUR L'UI CYBERPUNK
    // ==========================================

    // Navigation Compose (pour gérer les écrans : Onboarding -> Login -> Dashboard)
    implementation("androidx.navigation:navigation-compose:2.8.5")

    // Material Icons Extended (pour avoir plus d'icônes futuristes et de contrôle)
    implementation("androidx.compose.material:material-icons-extended:1.7.6")

    // Coil (pour charger des images, des avatars ou des effets visuels de manière optimisée)
    implementation("io.coil-kt:coil-compose:2.7.0")

    // ==========================================
    // 📦 DÉPENDANCES EXISTANTES (Firebase & AndroidX)
    // ==========================================

    // Firebase BoM (Gère toutes les versions de Firebase automatiquement)
    implementation(platform("com.google.firebase:firebase-bom:33.7.0"))

    // Bibliothèques Firebase
    implementation("com.google.firebase:firebase-auth-ktx")
    implementation("com.google.firebase:firebase-firestore-ktx")
    implementation("com.google.firebase:firebase-analytics-ktx")

    // ✅ PROTOBUF (requis par Timestamp)
    implementation(libs.protobuf.kotlin.lite)

    // IMPORTANT : Permet d'utiliser .await() avec Firebase (Coroutines)
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-play-services:1.9.0")

    // Dépendances AndroidX et Compose (via libs alias)
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.activity.compose)
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.ui)
    implementation(libs.androidx.ui.graphics)
    implementation(libs.androidx.ui.tooling.preview)
    implementation(libs.androidx.material3)

    // Tests
    testImplementation(libs.junit)
    androidTestImplementation(libs.androidx.junit)
    androidTestImplementation(libs.androidx.espresso.core)
    androidTestImplementation(platform(libs.androidx.compose.bom))
    androidTestImplementation(libs.androidx.ui.test.junit4)
    debugImplementation(libs.androidx.ui.tooling)
    debugImplementation(libs.androidx.ui.test.manifest)
}