module.exports = {
  MEMORY: {
    scales: [20, 100, 500, 3000, 10000],
    maxValuesPerContext: 50,
    ewmaDecay: 0.05 // Pour le compteur glissant
  },
  DNA: {
    levels: [
          { letter: 'A', max: 1.10 },  // Mort instantanée
          { letter: 'B', max: 1.20 },  // Crash très bas
          { letter: 'C', max: 1.40 },  // Crash bas
          { letter: 'D', max: 1.80 },  // Récupération faible
          { letter: 'E', max: 2.50 },  // Récupération moyenne
          { letter: 'F', max: 4.00 },  // Vol standard
          { letter: 'G', max: 8.00 },  // Vol chaud
          { letter: 'H', max: 15.00 }, // Vol très chaud
          { letter: 'I', max: 30.00 }, // Éruption
          { letter: 'J', max: 100.00 },// Légendaire (30x à 100x)
          { letter: 'K', max: Infinity }//  GOD TIER / JACKPOT (100x à 200x et au-delà)
        ],
    vlmm: {
      minLength: 2,
      maxLength: 11,
      minObservations: 3,
      scoreWeights: {
        confidence: 0.25,
        recency: 0.20,
        observations: 0.20,
        inverseEntropy: 0.15,
        stability: 0.20
      }
    }
  },
  LEARNING: {
    ewmaAlpha: 0.08, // Pour l'accuracy des Sages (réaction rapide)
    validationSplit: 0.20,
    rollingWindowSize: 100,
    minObservationsForPrediction: 5
  },
  SPY: {
    maxStressIndex: 3,
    betCountThreshold: 400,
    cashoutThreshold: 1000,
    correlationWindowSize: 50
  },
  CONFIDENCE: {
    maxCap: 96,
    minCap: 10
  },
  META_AI: {
    minAgreementThreshold: 0.60, // 60% des Sages doivent être d'accord
    divergencePenalty: 0.15, // Pénalité si les Sages divergent trop
    weakSignalThreshold: 0.40 // En dessous, on ignore le Sage
  }
};