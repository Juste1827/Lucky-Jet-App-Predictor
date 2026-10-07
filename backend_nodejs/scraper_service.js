const express = require('express');
const { chromium } = require('playwright-extra');
const stealth = require('puppeteer-extra-plugin-stealth')();
const path = require('path');

// Appliquer le plugin furtif
chromium.use(stealth);

const app = express();
app.use(express.json());

const PORT = 3001;
const PYTHON_API_URL = 'http://localhost:8000/api/crash';

// 🎯 CORRECTION CRITIQUE : Utiliser le même dossier de session que ton index.js
const userDataDir = path.join(__dirname, 'user_session');

let gameState = 'IDLE';
let lastPacketTime = Date.now();

async function runScraper() {
    console.log('🚀 Lancement du Scraper Node.js (Mode Persistent Context)...');

    // Utiliser launchPersistentContext comme dans ton index.js qui fonctionne
    const browser = await chromium.launchPersistentContext(userDataDir, {
        headless: false,
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-blink-features=AutomationControlled',
            '--disable-web-security'
        ],
        ignoreDefaultArgs: ['--enable-automation'],
        viewport: { width: 1280, height: 800 }
    });

    // Récupérer la première page ou en créer une nouvelle
    const page = browser.pages()[0] || await browser.newPage();

    page.on('websocket', ws => {
        if (!ws.url().includes('gamedev-tech.cc') && !ws.url().includes('luckyjet')) return;
        if (!ws._isLogged) {
            console.log("✅ FLUX WEBSOCKET CONNECTÉ :", ws.url().substring(0, 60));
            ws._isLogged = true;
        }

        ws.on('framereceived', (data) => {
            if (gameState === 'COOLDOWN') return;

            const payload = typeof data.payload === 'string' ? data.payload : data.payload.toString();
            const packetLatency = Date.now() - lastPacketTime;
            lastPacketTime = Date.now();

            if (payload.includes('"eventType": "changeState"') && payload.includes('"state": "flying"')) {
                if (gameState === 'IDLE') {
                    gameState = 'FLYING';
                    console.log('🚀 État: FLYING');
                }
            }

            if (payload.includes('"eventType": "stopCoefficient"')) {
                const match = payload.match(/"finalValue":\s*(\d+\.?\d*)/);
                if (match && gameState === 'FLYING') {
                    const crashValue = parseFloat(match[1]);
                    console.log(`💥 CRASH: ${crashValue}x | Latence: ${packetLatency}ms`);

                    gameState = 'COOLDOWN';

                    // Envoyer au backend Python
                    sendToPython({
                        crash_value: crashValue,
                        latency_ms: packetLatency,
                        timestamp: new Date().toISOString()
                    });

                    // Reset après 6 secondes (comme dans ton index.js)
                    setTimeout(() => {
                        gameState = 'IDLE';
                    }, 6000);
                }
            }
        });
    });

    try {
        console.log("⏳ Chargement de la page du jeu...");
        // Utiliser networkidle comme dans ton index.js qui fonctionne
        await page.goto('https://1win.com/fr-CI/casino/play/v_1wingames:luckyjet', {
            waitUntil: 'networkidle',
            timeout: 120000
        });
        console.log("✅ Page chargée. Le capteur est en ligne et l'affichage devrait être normal.");
    } catch (error) {
        console.log("⚠️ Délai de chargement dépassé, mais le capteur WebSocket reste actif.");
    }
}

async function sendToPython(data) {
    try {
        const response = await fetch(PYTHON_API_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });

        if (response.ok) {
            console.log('✅ Données envoyées à Python avec succès');
        } else {
            console.error(`❌ Erreur envoi Python: Status ${response.status}`);
        }
    } catch (error) {
        console.error('❌ Erreur de connexion à Python (assure-toi que le backend Python est lancé sur le port 8000):', error.message);
    }
}

app.get('/health', (req, res) => {
    res.json({ status: 'ok', gameState });
});

app.listen(PORT, () => {
    console.log(`🔧 Scraper Node.js écoute sur le port ${PORT}`);
    runScraper().catch(err => {
        console.error('❌ Erreur critique du scraper:', err);
        process.exit(1);
    });
});