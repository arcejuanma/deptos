#!/bin/bash
set -e

# Intervalo en minutos (por defecto 60, pero se puede cambiar con env var)
INTERVAL_MINUTES=${RUN_INTERVAL_MINUTES:-60}

# Crear directorio de logs si no existe
mkdir -p logs

LOG_FILE="logs/cron.log"

echo "Bot iniciado. Ejecutando cada ${INTERVAL_MINUTES} minutos..." | tee -a "$LOG_FILE"

# Ejecutar inmediatamente la primera vez
python run_bot.py 2>&1 | tee -a "$LOG_FILE"

# Luego ejecutar cada X minutos
while true; do
    sleep $((INTERVAL_MINUTES * 60))
    echo "$(date): Ejecutando bot nuevamente..." | tee -a "$LOG_FILE"
    python run_bot.py 2>&1 | tee -a "$LOG_FILE" || true  # || true para que continúe aunque falle una ejecución
done
