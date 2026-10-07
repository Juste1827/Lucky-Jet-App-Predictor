# Utilise l'image officielle Playwright qui contient déjà Chrome et Linux
FROM mcr.microsoft.com/playwright:v1.61.1-noble

# Dossier de travail
WORKDIR /app

# Copier les fichiers de dépendances
COPY package*.json ./

# Installer les dépendances
RUN npm install --omit=dev

# Copier le reste du code (ton index.js)
COPY . .

# Exposer le port par défaut de Google Cloud Run
EXPOSE 8080

# Lancer l'application
CMD ["node", "index.js"]