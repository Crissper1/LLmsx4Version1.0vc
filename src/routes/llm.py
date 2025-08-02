from flask import Blueprint, request, jsonify
import asyncio
import aiohttp
import json
import os
from concurrent.futures import ThreadPoolExecutor
import time

llm_bp = Blueprint('llm', __name__)

# Configuración de LLMs disponibles
LLM_CONFIGS = {
    'zai': {
        'name': 'Z.AI GLM-4.5-Flash',
        'api_url': 'https://api.z.ai/api/paas/v4/chat/completions',
        'headers': lambda api_key: {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        },
        'payload': lambda prompt: {
            'model': 'glm-4.5-flash',
            'messages': [
                {'role': 'system', 'content': 'You are a helpful AI assistant.'},
                {'role': 'user', 'content': prompt}
            ],
            'temperature': 0.7,
            'top_p': 0.8
        }
    },
    'gemini': {
        'name': 'Google Gemini 2.0 Flash',
        'api_url': 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent',
        'headers': lambda api_key: {
            'Content-Type': 'application/json'
        },
        'payload': lambda prompt: {
            'contents': [{'parts': [{'text': prompt}]}]
        }
    },
    'mistral': {
        'name': 'Mistral AI',
        'api_url': 'https://api.mistral.ai/v1/chat/completions',
        'headers': lambda api_key: {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        },
        'payload': lambda prompt: {
            'model': 'mistral-large-latest',
            'messages': [{'role': 'user', 'content': prompt}],
            'max_tokens': 1000
        }
    }
}

async def call_llm_api(session, llm_id, config, prompt, api_key, conversation_history=None):
    """Función asíncrona para llamar a la API de un LLM específico"""
    try:
        headers = config['headers'](api_key)
        
        # Construir el payload con historial de conversación
        if conversation_history and llm_id != 'gemini':
            # Para modelos que usan formato OpenAI (zai, mistral)
            messages = []
            if llm_id == 'zai':
                messages.append({'role': 'system', 'content': 'You are a helpful AI assistant.'})
            
            # Agregar historial de conversación
            for msg in conversation_history:
                messages.append(msg)
            
            # Agregar el nuevo prompt
            messages.append({'role': 'user', 'content': prompt})
            
            if llm_id == 'zai':
                payload = {
                    'model': 'glm-4.5-flash',
                    'messages': messages,
                    'temperature': 0.7,
                    'top_p': 0.8
                }
            elif llm_id == 'mistral':
                payload = {
                    'model': 'mistral-large-latest',
                    'messages': messages,
                    'max_tokens': 1000
                }
        else:
            # Usar payload original para primera interacción o Gemini
            payload = config['payload'](prompt)
        
        # Para Gemini, la API key va en la URL
        url = config['api_url']
        if llm_id == 'gemini':
            url += f'?key={api_key}'
        
        async with session.post(url, headers=headers, json=payload) as response:
            if response.status == 200:
                data = await response.json()
                
                # Extraer la respuesta según el formato de cada LLM
                if llm_id == 'zai':
                    content = data['choices'][0]['message']['content']
                elif llm_id == 'gemini':
                    content = data['candidates'][0]['content']['parts'][0]['text']
                elif llm_id == 'mistral':
                    content = data['choices'][0]['message']['content']
                else:
                    content = "Respuesta no procesada correctamente"
                
                return {
                    'id': llm_id,
                    'name': config['name'],
                    'status': 'completed',
                    'response': content
                }
            else:
                error_text = await response.text()
                return {
                    'id': llm_id,
                    'name': config['name'],
                    'status': 'error',
                    'response': f'Error {response.status}: {error_text}'
                }
    except Exception as e:
        return {
            'id': llm_id,
            'name': config['name'],
            'status': 'error',
            'response': f'Error de conexión: {str(e)}'
        }

@llm_bp.route('/query', methods=['POST'])
def query_llms():
    """Endpoint para enviar un prompt a múltiples LLMs"""
    try:
        data = request.get_json()
        prompt = data.get('prompt', '')
        llm_configs = data.get('llms', {})  # Diccionario con llm_id: api_key
        conversation_histories = data.get('conversation_histories', {})  # Historial por LLM
        
        if not prompt:
            return jsonify({'error': 'Prompt es requerido'}), 400
        
        if not llm_configs:
            return jsonify({'error': 'Al menos un LLM debe estar configurado'}), 400
        
        # Función para ejecutar las llamadas asíncronas
        async def make_requests():
            async with aiohttp.ClientSession() as session:
                tasks = []
                for llm_id, api_key in llm_configs.items():
                    if llm_id in LLM_CONFIGS:
                        config = LLM_CONFIGS[llm_id]
                        history = conversation_histories.get(llm_id, [])
                        task = call_llm_api(session, llm_id, config, prompt, api_key, history)
                        tasks.append(task)
                
                results = await asyncio.gather(*tasks)
                return results
        
        # Ejecutar las llamadas asíncronas en un hilo separado
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(make_requests())
        loop.close()
        
        return jsonify({
            'success': True,
            'results': results
        })
        
    except Exception as e:
        return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

@llm_bp.route('/simulate', methods=['POST'])
def simulate_llms():
    """Endpoint para simular respuestas de LLMs (para desarrollo/demo)"""
    try:
        data = request.get_json()
        prompt = data.get('prompt', '')
        llm_ids = data.get('llm_ids', ['openai', 'gemini', 'claude', 'llama'])
        
        if not prompt:
            return jsonify({'error': 'Prompt es requerido'}), 400
        
        # Simular respuestas con diferentes tiempos de respuesta
        results = []
        for llm_id in llm_ids:
            if llm_id in LLM_CONFIGS:
                config = LLM_CONFIGS[llm_id]
            else:
                # Para LLMs no configurados como Meta Llama
                config = {'name': 'Meta Llama' if llm_id == 'llama' else llm_id.title()}
            
            # Simular tiempo de respuesta
            time.sleep(0.1)  # Pequeña pausa para simular procesamiento
            
            response_text = f"""Esta es una respuesta simulada de {config['name']} para el prompt: "{prompt}".

En una implementación real, aquí aparecería la respuesta real del modelo de IA. Cada LLM tiene su propio estilo y enfoque para responder preguntas, lo que hace que la comparación sea muy útil para obtener diferentes perspectivas sobre el mismo tema.

{config['name']} se caracteriza por [características específicas del modelo que se mostrarían aquí en la implementación real]."""
            
            results.append({
                'id': llm_id,
                'name': config['name'],
                'status': 'completed',
                'response': response_text
            })
        
        return jsonify({
            'success': True,
            'results': results
        })
        
    except Exception as e:
        return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

@llm_bp.route('/available', methods=['GET'])
def get_available_llms():
    """Endpoint para obtener la lista de LLMs disponibles"""
    llms = []
    for llm_id, config in LLM_CONFIGS.items():
        llms.append({
            'id': llm_id,
            'name': config['name']
        })
    
    # Agregar Meta Llama que no está en la configuración real
    llms.append({
        'id': 'llama',
        'name': 'Meta Llama'
    })
    
    return jsonify({
        'success': True,
        'llms': llms
    })
