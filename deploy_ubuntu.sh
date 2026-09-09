#!/usr/bin/env bash
# =========================================================
# Baja los ultimos cambios de fontana_movimientos en el
# servidor Ubuntu y reinicia el servicio.
# (Paso "Ubuntu" de guia_despliegue_git.docx)
# =========================================================
set -e

PROYECTO="$HOME/fontana_movimientos"
SERVICIO="fontana"

echo "==============================================="
echo " Actualizando fontana_movimientos en el servidor"
echo "==============================================="
echo

cd "$PROYECTO"

echo "--- activando entorno virtual ---"
source venv/bin/activate

echo
echo "--- git pull ---"
git pull

echo
echo "--- pip install -r requirements.txt ---"
pip install -r requirements.txt

echo
echo "--- python manage.py migrate ---"
python manage.py migrate

echo
echo "--- python manage.py collectstatic --noinput ---"
python manage.py collectstatic --noinput

echo
echo "--- reiniciando servicio $SERVICIO ---"
sudo systemctl restart "$SERVICIO"

echo
echo "Listo. Estado del servicio:"
sudo systemctl status "$SERVICIO" --no-pager -l | head -n 10
