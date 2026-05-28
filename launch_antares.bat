@echo off
start "" wsl.exe -d Ubuntu -- bash -c "source /mnt/c/antares_v2/antares/.venv/bin/activate && cd /mnt/c/antares_v2/antares && python antares_app.py"
