@echo off
echo Iniciando Multi-LLM App...
echo.

REM Activar el entorno virtual
call .venv\Scripts\activate.bat

REM Instalar dependencias si es necesario
pip install -r requirements.txt

REM Iniciar el servidor Flask
python main.py

pause
