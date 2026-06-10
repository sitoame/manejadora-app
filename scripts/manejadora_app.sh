#!/bin/bash
source /home/dynatek/manejadora_app/my_venv/bin/activate
exec python3.10 -W 'ignore:semaphore_tracker:UserWarning' -u /home/dynatek/manejadora_app/main.py >> /home/dynatek/manejadora_app/logs/manejadora_app.log 2>&1
