#!/bin/bash
set -e

# Intervalo en minutos (por defecto 60, pero se puede cambiar con env var)
INTERVAL_MINUTES=${RUN_INTERVAL_MINUTES:-60}

echo "Bot iniciado. Ejecutando cada ${INTERVAL_MINUTES} minutos..." | tee -a cron.log

# Ejecutar inmediatamente la primera vez
python run_bot.py 2>&1 | tee -a cron.log

# Luego ejecutar cada X minutos
while true; do
    sleep $((INTERVAL_MINUTES * 60))
    echo "$(date): Ejecutando bot nuevamente..." | tee -a cron.log
    python run_bot.py 2>&1 | tee -a cron.log || true  # || true para que continúe aunque falle una ejecución
done
