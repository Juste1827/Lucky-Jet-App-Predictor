const express = require('express');
const admin = require("firebase-admin");
const { getFirestore } = require("firebase-admin/firestore");
const { chromium } = require('playwright-extra');
const stealth = require('puppeteer-extra-plugin-stealth')();
const path = require('path');
const Database = require('better-sqlite3');
const config = require('./config');

chromium.use(stealth);
const app = express();

const serviceAccount = require("./serviceAccountKey.json");
if (!admin.apps.length) {
    admin.initializeApp({ credential: admin.credential.cert(serviceAccount) });
}
const db = getFirestore("app-predictor-lucky-jet");
const userDataDir = path.join(__dirname, 'user_session');

// ========================================================
// === 🗄️ BASE DE DONNÉES LOCALE (SQLite) ===
// ========================================================
const localDb = new Database(path.join(__dirname, 'brain_local.db'));
localDb.pragma('journal_mode = WAL');
localDb.pragma('synchronous = NORMAL');

localDb.exec(`
    CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        crash_value REAL NOT NULL,
        dna_letter TEXT NOT NULL,
        timestamp INTEGER DEFAULT (strftime('%s', 'now'))
    );

    CREATE TABLE IF NOT EXISTS vlmm_contexts (
        context TEXT PRIMARY KEY,
        ewma_count REAL DEFAULT 0,
        last_seen INTEGER DEFAULT 0,
        median_value REAL DEFAULT 0,
        ewma_value REAL DEFAULT 0,
        variance REAL DEFAULT 0,
        stability REAL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS vlmm_transitions (
        context TEXT NOT NULL,
        next_state TEXT NOT NULL,
        ewma_count REAL DEFAULT 0,
        PRIMARY KEY (context, next_state)
    );

    CREATE TABLE IF NOT EXISTS sage_accuracy (
        sage_name TEXT PRIMARY KEY,
        ewma_accuracy REAL DEFAULT 0.5,
        total_predictions INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS regime_state (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        current_regime TEXT DEFAULT 'normal',
        cusum_pos REAL DEFAULT 0,
        cusum_neg REAL DEFAULT 0,
        mean_baseline REAL DEFAULT 2.0,
        std_baseline REAL DEFAULT 1.0
    );
`);

// Insertion initiale du régime si absent
localDb.prepare(`INSERT OR IGNORE INTO regime_state (id, current_regime) VALUES (1, 'normal')`).run();

// ========================================================
// ===  FONCTIONS UTILITAIRES AVANCÉES ===
// ========================================================

// Distance de Levenshtein (pour comparer les motifs ADN)
function levenshteinDistance(a, b) {
    const matrix = Array.from({ length: b.length + 1 }, (_, i) => [i]);
    for (let j = 0; j <= a.length; j++) matrix[0][j] = j;
    for (let i = 1; i <= b.length; i++) {
        for (let j = 1; j <= a.length; j++) {
            matrix[i][j] = b[i - 1] === a[j - 1]
                ? matrix[i - 1][j - 1]
                : Math.min(matrix[i - 1][j - 1] + 1, matrix[i][j - 1] + 1, matrix[i - 1][j] + 1);
        }
    }
    return matrix[b.length][a.length];
}

// Similarité normalisée (0 à 1)
function sequenceSimilarity(a, b) {
    const maxLen = Math.max(a.length, b.length);
    if (maxLen === 0) return 1;
    return 1 - (levenshteinDistance(a, b) / maxLen);
}

// Corrélation de Pearson
function pearsonCorrelation(x, y) {
    const n = Math.min(x.length, y.length);
    if (n < 3) return 0;
    const xSlice = x.slice(-n), ySlice = y.slice(-n);
    const meanX = xSlice.reduce((a, b) => a + b, 0) / n;
    const meanY = ySlice.reduce((a, b) => a + b, 0) / n;
    let num = 0, denX = 0, denY = 0;
    for (let i = 0; i < n; i++) {
        const dx = xSlice[i] - meanX, dy = ySlice[i] - meanY;
        num += dx * dy;
        denX += dx * dx;
        denY += dy * dy;
    }
    const den = Math.sqrt(denX * denY);
    return den === 0 ? 0 : num / den;
}

// Corrélation de Spearman (basée sur les rangs)
function spearmanCorrelation(x, y) {
    const rank = arr => arr.map(v => arr.filter(u => u < v).length + 1);
    return pearsonCorrelation(rank(x), rank(y));
}

// EWMA (Exponential Weighted Moving Average)
function ewma(values, alpha = config.LEARNING.ewmaAlpha) {
    if (values.length === 0) return 0;
    let result = values[0];
    for (let i = 1; i < values.length; i++) {
        result = alpha * values[i] + (1 - alpha) * result;
    }
    return result;
}

// Médiane
function median(arr) {
    if (arr.length === 0) return 0;
    const sorted = [...arr].sort((a, b) => a - b);
    const mid = Math.floor(sorted.length / 2);
    return sorted.length % 2 !== 0 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

// Percentile
function percentile(arr, p) {
    if (arr.length === 0) return 0;
    const sorted = [...arr].sort((a, b) => a - b);
    const idx = (p / 100) * (sorted.length - 1);
    const lower = Math.floor(idx);
    const upper = Math.ceil(idx);
    const weight = idx - lower;
    return upper >= sorted.length ? sorted[lower] : sorted[lower] * (1 - weight) + sorted[upper] * weight;
}

// Variance
function variance(arr) {
    if (arr.length < 2) return 0;
    const mean = arr.reduce((a, b) => a + b, 0) / arr.length;
    return arr.reduce((sum, v) => sum + Math.pow(v - mean, 2), 0) / (arr.length - 1);
}

// Écart-type
function stdDev(arr) {
    return Math.sqrt(variance(arr));
}

// ========================================================
// === 🧬 SÉQUENCEUR ADN ===
// ========================================================
function getDNALetter(val) {
    for (const level of config.DNA.levels) {
        if (val < level.max) return level.letter;
    }
    return 'J';
}

// ========================================================
// ===  CUSUM - DÉTECTION DE CHANGEMENT DE RÉGIME ===
// ========================================================
function updateCUSUM(crashValue) {
    const regime = localDb.prepare('SELECT * FROM regime_state WHERE id = 1').get();
    const threshold = 3.0; // Seuil de détection
    const drift = 0.5; // Dérive minimale à détecter

    // Mise à jour des CUSUM
    let cusumPos = regime.cusum_pos + (crashValue - regime.mean_baseline - drift);
    let cusumNeg = regime.cusum_neg - (crashValue - regime.mean_baseline + drift);
    cusumPos = Math.max(0, cusumPos);
    cusumNeg = Math.max(0, cusumNeg);

    let newRegime = regime.current_regime;

    // Détection de changement
    if (cusumPos > threshold || cusumNeg > threshold) {
        // Recalcul du baseline sur les 50 derniers tours
        const recent = localDb.prepare('SELECT crash_value FROM history ORDER BY id DESC LIMIT 50').all();
        if (recent.length > 10) {
            const values = recent.map(r => r.crash_value);
            const newMean = values.reduce((a, b) => a + b, 0) / values.length;
            const newStd = stdDev(values);

            if (newMean > regime.mean_baseline * 1.3) {
                newRegime = 'high-rtp';
            } else if (newMean < regime.mean_baseline * 0.7) {
                newRegime = 'low-rtp';
            } else if (newStd > regime.std_baseline * 2) {
                newRegime = 'volatile';
            } else {
                newRegime = 'normal';
            }

            // Reset CUSUM avec nouveau baseline
            cusumPos = 0;
            cusumNeg = 0;

            localDb.prepare(`
                UPDATE regime_state
                SET current_regime = ?, cusum_pos = ?, cusum_neg = ?,
                    mean_baseline = ?, std_baseline = ?
                WHERE id = 1
            `).run(newRegime, cusumPos, cusumNeg, newMean, newStd);
        }
    } else {
        localDb.prepare(`
            UPDATE regime_state SET cusum_pos = ?, cusum_neg = ? WHERE id = 1
        `).run(cusumPos, cusumNeg);
    }

    return newRegime;
}

// ========================================================
// === 🧠 VLMM AVEC SCORE SOPHISTIQUÉ ===
// ========================================================
function findBestVLMMContext(currentDNA) {
    const now = Date.now();
    const { minLength, maxLength, minObservations, scoreWeights } = config.DNA.vlmm;

    let bestContext = null;
    let bestScore = 0;

    for (let len = maxLength; len >= minLength; len--) {
        if (currentDNA.length < len) continue;
        const context = currentDNA.slice(-len);

        const ctxData = localDb.prepare('SELECT * FROM vlmm_contexts WHERE context = ?').get(context);
        if (!ctxData || ctxData.ewma_count < minObservations) continue;

        // Récence : plus le contexte a été vu récemment, mieux c'est
        const recency = Math.max(0, 1 - (now - ctxData.last_seen) / 3600000); // Décroissance sur 1h

        // Entropie inverse : moins il y a de transitions différentes, plus c'est stable
        const transitions = localDb.prepare('SELECT * FROM vlmm_transitions WHERE context = ?').all(context);
        const totalTransitions = transitions.reduce((sum, t) => sum + t.ewma_count, 0);
        let entropy = 0;
        for (const t of transitions) {
            const p = t.ewma_count / totalTransitions;
            if (p > 0) entropy -= p * Math.log2(p);
        }
        const maxEntropy = Math.log2(transitions.length || 1);
        const inverseEntropy = maxEntropy > 0 ? 1 - (entropy / maxEntropy) : 1;

        // Score composite
        const score = (
            scoreWeights.confidence * (ctxData.stability) +
            scoreWeights.recency * recency +
            scoreWeights.observations * Math.min(1, ctxData.ewma_count / 20) +
            scoreWeights.inverseEntropy * inverseEntropy +
            scoreWeights.stability * ctxData.stability
        );

        if (score > bestScore) {
            bestScore = score;
            bestContext = {
                dna: context,
                length: len,
                data: ctxData,
                transitions: transitions,
                score: score,
                inverseEntropy: inverseEntropy
            };
        }
    }

    return bestContext;
}

// ========================================================
// === 🏛️ SAGES (PRODUCTEURS DE SIGNAUX) ===
// ========================================================

function sageMemory() {
    const recent = localDb.prepare('SELECT dna_letter FROM history ORDER BY id DESC LIMIT 11').all();
    if (recent.length < config.DNA.vlmm.minLength) {
        return { target: 1.50, confidence: 0.30, state: "Apprentissage", signalStrength: 0 };
    }

    const currentDNA = recent.map(r => r.dna_letter).reverse().join('');
    const context = findBestVLMMContext(currentDNA);

    if (!context) {
        // Fallback : moyenne des 20 derniers
        const fallback = localDb.prepare('SELECT crash_value FROM history ORDER BY id DESC LIMIT 20').all();
        const avg = fallback.length > 0 ? fallback.reduce((s, r) => s + r.crash_value, 0) / fallback.length : 1.50;
        return { target: Math.max(1.10, avg * 0.85), confidence: 0.35, state: "Fallback", signalStrength: 0.30 };
    }

    // Trouver la transition la plus probable
    const totalTrans = context.transitions.reduce((s, t) => s + t.ewma_count, 0);
    let bestTransition = context.transitions[0];
    let maxCount = 0;
    for (const t of context.transitions) {
        if (t.ewma_count > maxCount) {
            maxCount = t.ewma_count;
            bestTransition = t;
        }
    }

    const probability = maxCount / totalTrans;
    const target = Math.max(1.10, context.data.ewma_value * 0.85);

    return {
        target: target,
        confidence: probability,
        state: `VLMM ${context.length}D: ${context.dna} (score: ${context.score.toFixed(2)})`,
        signalStrength: context.score,
        contextLength: context.length
    };
}

function sageDrift() {
    const recent = localDb.prepare('SELECT crash_value FROM history ORDER BY id DESC LIMIT 100').all();
    if (recent.length < 20) {
        return { target: 1.80, confidence: 0.40, state: "Collecte", signalStrength: 0.30 };
    }

    const values = recent.map(r => r.crash_value);
    const med = median(values);
    const ewmaVal = ewma(values);
    const p75 = percentile(values, 75);
    const vol = stdDev(values);

    const regime = localDb.prepare('SELECT current_regime FROM regime_state WHERE id = 1').get();

    let target, confidence, state;

    if (regime.current_regime === 'low-rtp') {
        target = Math.max(2.00, ewmaVal * 1.3);
        confidence = 0.70;
        state = `Dette variance (Méd: ${med.toFixed(2)}, σ: ${vol.toFixed(2)})`;
    } else if (regime.current_regime === 'high-rtp') {
        target = Math.max(1.20, ewmaVal * 0.70);
        confidence = 0.75;
        state = `Purge (Méd: ${med.toFixed(2)}, σ: ${vol.toFixed(2)})`;
    } else if (regime.current_regime === 'volatile') {
        target = Math.max(1.30, med * 0.80);
        confidence = 0.50;
        state = `Volatile (Méd: ${med.toFixed(2)}, σ: ${vol.toFixed(2)})`;
    } else {
        target = Math.max(1.30, ewmaVal * 0.85);
        confidence = 0.60;
        state = `Normal (Méd: ${med.toFixed(2)}, P75: ${p75.toFixed(2)})`;
    }

    return { target, confidence, state, signalStrength: confidence };
}

function sageVelocity(packetLatencies) {
    if (packetLatencies.length < 10) {
        return { target: 1.80, confidence: 0.40, state: "Collecte", signalStrength: 0.30 };
    }

    const recent = packetLatencies.slice(-20);
    const avgLatency = recent.reduce((a, b) => a + b, 0) / recent.length;
    const jitter = stdDev(recent);

    // Vérifier la corrélation latence/crash sur les 50 derniers tours
    const crashHistory = localDb.prepare('SELECT crash_value FROM history ORDER BY id DESC LIMIT 50').all();
    const crashValues = crashHistory.map(r => r.crash_value);
    const latencyHistory = packetLatencies.slice(-50);

    const correlation = crashValues.length === latencyHistory.length
        ? Math.abs(spearmanCorrelation(crashValues, latencyHistory))
        : 0;

    // Si la corrélation est faible, ce sage a peu de poids
    const signalStrength = Math.min(1, correlation * 2);

    let target, confidence, state;

    if (avgLatency > 250) {
        target = 1.25;
        confidence = 0.75;
        state = `Lag critique (${avgLatency.toFixed(0)}ms, jitter: ${jitter.toFixed(0)})`;
    } else if (avgLatency > 150) {
        target = 1.50;
        confidence = 0.60;
        state = `Latence modérée (${avgLatency.toFixed(0)}ms)`;
    } else if (jitter > 50) {
        target = 1.40;
        confidence = 0.55;
        state = `Jitter élevé (${jitter.toFixed(0)}ms)`;
    } else {
        target = 1.80;
        confidence = 0.55;
        state = `Réseau stable (${avgLatency.toFixed(0)}ms, corr: ${correlation.toFixed(2)})`;
    }

    return { target, confidence, state, signalStrength };
}

// ========================================================
// === 🤖 MÉTA-IA (COUCHE DE DÉCISION) ===
// ========================================================
function metaAIDecision(sages, regime) {
    // 1. Filtrer les signaux faibles
    const strongSignals = sages.filter(s => s.signalStrength >= config.META_AI.weakSignalThreshold);

    if (strongSignals.length === 0) {
        return {
            target: 1.50,
            confidence: 0.30,
            state: "Aucun signal fiable",
            ignoredSages: sages.map(s => s.name)
        };
    }

    // 2. Calculer la divergence entre les Sages
    const targets = strongSignals.map(s => s.target);
    const targetMedian = median(targets);
    const targetStd = stdDev(targets);
    const divergence = targetStd / (targetMedian || 1);

    // 3. Pondérer par l'accuracy EWMA de chaque Sage
    const weightedTargets = strongSignals.map(s => {
        const accuracy = localDb.prepare('SELECT ewma_accuracy FROM sage_accuracy WHERE sage_name = ?').get(s.name);
        const acc = accuracy ? accuracy.ewma_accuracy : 0.5;
        return { target: s.target, weight: acc * s.signalStrength };
    });

    const totalWeight = weightedTargets.reduce((sum, w) => sum + w.weight, 0);
    const finalTarget = weightedTargets.reduce((sum, w) => sum + w.target * w.weight, 0) / (totalWeight || 1);

    // 4. Calculer la confiance finale
    let finalConfidence = strongSignals.reduce((sum, s) => sum + s.confidence * s.signalStrength, 0) / (totalWeight || 1);

    // Pénalité de divergence
    finalConfidence *= (1 - divergence * config.META_AI.divergencePenalty);

    // Bonus si les Sages sont d'accord
    const agreement = 1 - Math.min(1, divergence);
    if (agreement > config.META_AI.minAgreementThreshold) {
        finalConfidence *= 1.1;
    }

    // 5. Ajustement selon le régime
    if (regime === 'volatile') finalConfidence *= 0.85;
    if (regime === 'low-rtp') finalTarget *= 1.1;

    finalConfidence = Math.max(config.CONFIDENCE.minCap / 100, Math.min(config.CONFIDENCE.maxCap / 100, finalConfidence));

    return {
        target: Math.max(1.10, finalTarget),
        confidence: finalConfidence,
        state: `Méta-IA: ${strongSignals.length} signaux forts, divergence: ${divergence.toFixed(2)}`,
        agreement: agreement,
        divergence: divergence
    };
}

// ========================================================
// === 💾 PERSISTANCE (SQLite local + Firestore résumé) ===
// ========================================================
async function loadBrainFromLocal() {
    const count = localDb.prepare('SELECT COUNT(*) as count FROM history').get();
    const regime = localDb.prepare('SELECT current_regime FROM regime_state WHERE id = 1').get();
    console.log(`🧠 Cerveau local restauré : ${count.count} tours, régime: ${regime.current_regime}`);
}

async function saveBrainToFirestore(summary) {
    try {
        // On ne sauvegarde que le résumé dans Firestore
        await db.collection("brain_state").doc("ai_summary").set({
            total_rounds: summary.totalRounds,
            current_regime: summary.regime,
            global_accuracy: summary.globalAccuracy,
            last_prediction: summary.lastPrediction,
            updatedAt: admin.firestore.FieldValue.serverTimestamp()
        }, { merge: true });
    } catch (error) {
        console.error("❌ Erreur Firestore:", error.message);
    }
}

// ========================================================
// === 🚀 TRAITEMENT DU CRASH ===
// ========================================================
let gameState = 'IDLE';
let lastPacketTime = Date.now();
let packetLatencies = [];
let lastPredictionTarget = 1.50;
let totalRounds = 0;
let successfulPredictions = 0;

async function triggerEnd(crashValue, packetLatency) {
    if (gameState === 'COOLDOWN') return;
    if (crashValue <= 1.01) return;

    gameState = 'COOLDOWN';
    totalRounds++;

    // 1. Enregistrer dans l'historique local
    const dna = getDNALetter(crashValue);
    localDb.prepare('INSERT INTO history (crash_value, dna_letter) VALUES (?, ?)').run(crashValue, dna);

    // 2. Mettre à jour le VLMM
    const recentDNA = localDb.prepare('SELECT dna_letter FROM history ORDER BY id DESC LIMIT 12').all();
    if (recentDNA.length >= config.DNA.vlmm.minLength + 1) {
        const dnaLetters = recentDNA.map(r => r.dna_letter).reverse();

        for (let len = config.DNA.vlmm.minLength; len <= Math.min(config.DNA.vlmm.maxLength, dnaLetters.length - 1); len++) {
            const context = dnaLetters.slice(-len - 1, -1).join('');
            const nextState = dnaLetters[dnaLetters.length - 1];

            // Upsert context
            const existing = localDb.prepare('SELECT * FROM vlmm_contexts WHERE context = ?').get(context);
            const decay = config.MEMORY.ewmaDecay;

            if (existing) {
                const newEwmaCount = existing.ewma_count * (1 - decay) + 1;
                const newEwmaValue = existing.ewma_value * (1 - decay) + crashValue * decay;
                const newVariance = variance([existing.ewma_value, crashValue]);
                const newStability = 1 / (1 + newVariance);

                localDb.prepare(`
                    UPDATE vlmm_contexts
                    SET ewma_count = ?, ewma_value = ?, variance = ?, stability = ?, last_seen = ?
                    WHERE context = ?
                `).run(newEwmaCount, newEwmaValue, newVariance, newStability, Date.now(), context);
            } else {
                localDb.prepare(`
                    INSERT INTO vlmm_contexts (context, ewma_count, ewma_value, variance, stability, last_seen)
                    VALUES (?, 1, ?, 0, 1, ?)
                `).run(context, crashValue, Date.now());
            }

            // Upsert transition
            const transExisting = localDb.prepare('SELECT * FROM vlmm_transitions WHERE context = ? AND next_state = ?').get(context, nextState);
            if (transExisting) {
                localDb.prepare('UPDATE vlmm_transitions SET ewma_count = ? WHERE context = ? AND next_state = ?')
                    .run(transExisting.ewma_count * (1 - decay) + 1, context, nextState);
            } else {
                localDb.prepare('INSERT INTO vlmm_transitions (context, next_state, ewma_count) VALUES (?, ?, 1)')
                    .run(context, nextState);
            }
        }
    }

    // 3. Mettre à jour le régime (CUSUM)
    const regime = updateCUSUM(crashValue);

    // 4. Évaluer les Sages sur la prédiction précédente
    const sages = [
        { name: 'memory', prediction: lastPredictionTarget },
        { name: 'drift', prediction: lastPredictionTarget * 0.95 },
        { name: 'velocity', prediction: lastPredictionTarget * 1.05 }
    ];

    for (const sage of sages) {
        const success = crashValue >= sage.prediction ? 1 : 0;
        const existing = localDb.prepare('SELECT * FROM sage_accuracy WHERE sage_name = ?').get(sage.name);

        if (existing) {
            const newAccuracy = existing.ewma_accuracy * (1 - config.LEARNING.ewmaAlpha) + success * config.LEARNING.ewmaAlpha;
            localDb.prepare('UPDATE sage_accuracy SET ewma_accuracy = ?, total_predictions = ? WHERE sage_name = ?')
                .run(newAccuracy, existing.total_predictions + 1, sage.name);
        } else {
            // ✅ CORRECTION ICI : Suppression du '1' en trop qui causait le RangeError
            localDb.prepare('INSERT INTO sage_accuracy (sage_name, ewma_accuracy, total_predictions) VALUES (?, ?, 1)')
                .run(sage.name, success);
        }
    }

    if (crashValue >= lastPredictionTarget) {
        successfulPredictions++;
    }

    // 5. Exécuter les Sages
    const s1 = sageMemory();
    const s2 = sageDrift();
    const s3 = sageVelocity(packetLatencies);

    const allSages = [
        { name: 'memory', ...s1 },
        { name: 'drift', ...s2 },
        { name: 'velocity', ...s3 }
    ];

    // 6. Méta-IA décide
    const decision = metaAIDecision(allSages, regime);
    lastPredictionTarget = decision.target;

    // 7. Afficher
    const accuracy = totalRounds > 0 ? (successfulPredictions / totalRounds * 100).toFixed(1) : '0.0';
    console.log(`\n${'='.repeat(60)}`);
    console.log(`💥 CRASH: ${crashValue.toFixed(2)}x | ADN: ${dna} | Régime: ${regime}`);
    console.log(`🎯 OBJECTIF: ${decision.target.toFixed(2)}x | CONFIANCE: ${(decision.confidence * 100).toFixed(0)}%`);
    console.log(`📊 Précision globale: ${accuracy}% | Tours: ${totalRounds}`);
    console.log(`${'='.repeat(60)}`);
    console.log(`🔍 [Analyse technique]`);
    console.log(`   ↳ ${decision.state}`);
    console.log(`   ↳ Mémoire: ${s1.target.toFixed(2)}x (force: ${s1.signalStrength.toFixed(2)})`);
    console.log(`   ↳ Dérive: ${s2.target.toFixed(2)}x (force: ${s2.signalStrength.toFixed(2)})`);
    console.log(`   ↳ Vélocité: ${s3.target.toFixed(2)}x (force: ${s3.signalStrength.toFixed(2)})`);
    console.log(`${'='.repeat(60)}\n`);

    // 8. Publication Firestore (résumé uniquement)
    await saveBrainToFirestore({
        totalRounds,
        regime,
        globalAccuracy: accuracy,
        lastPrediction: decision.target.toFixed(2)
    });

    // 9. Publication dans predictions.latest pour l'app Android
    try {
        await db.collection("predictions").doc("latest").set({
            target_score: decision.target.toFixed(2),
            confidence: Math.round(decision.confidence * 100),
            last_crash: `${crashValue.toFixed(2)}x`,
            regime: regime,
            meta_state: decision.state,
            sages_summary: {
                memory: `${s1.target.toFixed(2)}x (${(s1.signalStrength * 100).toFixed(0)}%)`,
                drift: `${s2.target.toFixed(2)}x (${(s2.signalStrength * 100).toFixed(0)}%)`,
                velocity: `${s3.target.toFixed(2)}x (${(s3.signalStrength * 100).toFixed(0)}%)`
            },
            timestamp: admin.firestore.FieldValue.serverTimestamp()
        });

        await db.collection("history").add({
            actual_crash: crashValue,
            predicted_threshold: decision.target,
            confidence_at_time: Math.round(decision.confidence * 100),
            was_successful: crashValue >= decision.target,
            regime: regime,
            timestamp: admin.firestore.FieldValue.serverTimestamp()
        });
    } catch (err) {
        console.error("❌ Erreur Firestore:", err.message);
    }

    setTimeout(() => {
        gameState = 'IDLE';
    }, 6000);
}

// ========================================================
// === 🕸️ CAPTEUR WEBSOCKET ===
// ========================================================
async function runEngine() {
    console.log("🚀 Lancement du Moteur Neuronal Avancé (Méta-IA + CUSUM + VLMM)...");

    await loadBrainFromLocal();

    const browser = await chromium.launchPersistentContext(userDataDir, {
        headless: false,
        args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-blink-features=AutomationControlled', '--disable-web-security'],
        ignoreDefaultArgs: ['--enable-automation'],
        viewport: { width: 1280, height: 800 }
    });

    const page = browser.pages()[0] || await browser.newPage();

    page.on('websocket', ws => {
        if (!ws.url().includes('gamedev-tech.cc') && !ws.url().includes('luckyjet')) return;
        if (!ws._isLogged) { console.log("✅ FLUX WEBSOCKET CONNECTÉ"); ws._isLogged = true; }

        ws.on('framereceived', (data) => {
            if (gameState === 'COOLDOWN') return;

            const payload = typeof data.payload === 'string' ? data.payload : data.payload.toString();
            const packetLatency = Date.now() - lastPacketTime;
            lastPacketTime = Date.now();

            packetLatencies.push(packetLatency);
            if (packetLatencies.length > 100) packetLatencies.shift();

            if (payload.includes('"eventType": "changeState"') && payload.includes('"state": "flying"')) {
                if (gameState === 'IDLE') {
                    gameState = 'FLYING';
                }
            }

            if (payload.includes('"eventType": "stopCoefficient"')) {
                const match = payload.match(/"finalValue":\s*(\d+\.?\d*)/);
                if (match && gameState === 'FLYING') {
                    triggerEnd(parseFloat(match[1]), packetLatency);
                }
            }
        });
    });

    try {
        console.log("⏳ Chargement de la page du jeu...");
        await page.goto('https://1win.com/fr-CI/casino/play/v_1wingames:luckyjet', { waitUntil: 'networkidle', timeout: 120000 });
        console.log("✅ Page chargée. Le Cerveau Neuronal Avancé est en ligne.");
    } catch (error) {
        console.log("⚠️ Délai de chargement dépassé. Le capteur WebSocket reste actif.");
    }
}

runEngine();
app.listen(8080, () => console.log("🌐 Serveur Express en écoute sur le port 8080"));