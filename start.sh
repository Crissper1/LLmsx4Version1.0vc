#!/bin/bash
echo "Iniciando Multi-LLM App..."
echo

# Activar el entorno virtual
source .venv/Scripts/activate

# Instalar dependencias si es necesario
pip install -r requirements.txt

# Iniciar el servidor Flask
python main.py
