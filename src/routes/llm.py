from flask import Blueprint, request, jsonify
import asyncio
import aiohttp
import json
import os
from concurrent.futures import ThreadPoolExecutor
import time
from src.models.user import db
from src.models.conversation import Conversation, ConversationMessage, LLMMemory
import uuid
import re

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
    """Endpoint para simular respuestas de LLMs con memoria (para desarrollo/demo)"""
    try:
        data = request.get_json()
        prompt = data.get('prompt', '')
        llm_ids = data.get('llm_ids', ['zai', 'gemini', 'mistral', 'llama'])
        conversation_id = data.get('conversation_id')
        
        if not prompt:
            return jsonify({'error': 'Prompt es requerido'}), 400
        
        # Si no hay conversation_id, crear una nueva conversación
        if not conversation_id:
            conversation_id = str(uuid.uuid4())
            conversation = Conversation(id=conversation_id)
            db.session.add(conversation)
            db.session.commit()
        else:
            conversation = Conversation.query.get(conversation_id)
            if not conversation:
                return jsonify({'error': 'Conversación no encontrada'}), 404
        
        # Guardar el mensaje del usuario para todos los LLMs
        for llm_id in llm_ids:
            if llm_id in LLM_CONFIGS:
                llm_name = LLM_CONFIGS[llm_id]['name']
            else:
                llm_name = 'Meta Llama' if llm_id == 'llama' else llm_id.title()
            
            user_message = ConversationMessage(
                conversation_id=conversation_id,
                llm_id=llm_id,
                llm_name=llm_name,
                role='user',
                content=prompt
            )
            db.session.add(user_message)
        
        # Extraer información de memoria del prompt del usuario
        extracted_memory = extract_memory_from_text(prompt)
        
        # Actualizar memoria para todos los LLMs
        for llm_id in llm_ids:
            for key, value in extracted_memory.items():
                existing_memory = LLMMemory.query.filter_by(
                    conversation_id=conversation_id,
                    llm_id=llm_id,
                    memory_key=key
                ).first()
                
                if existing_memory:
                    existing_memory.memory_value = value
                else:
                    new_memory = LLMMemory(
                        conversation_id=conversation_id,
                        llm_id=llm_id,
                        memory_key=key,
                        memory_value=value
                    )
                    db.session.add(new_memory)
        
        # Simular respuestas con memoria
        results = []
        for llm_id in llm_ids:
            if llm_id in LLM_CONFIGS:
                config = LLM_CONFIGS[llm_id]
                llm_name = config['name']
            else:
                llm_name = 'Meta Llama' if llm_id == 'llama' else llm_id.title()
            
            # Obtener memoria del LLM
            memories = LLMMemory.query.filter_by(
                conversation_id=conversation_id,
                llm_id=llm_id
            ).all()
            
            memory_context = ""
            for memory in memories:
                if memory.memory_key == 'user_name':
                    memory_context += f"Recuerda que el usuario se llama {memory.memory_value}. "
                elif memory.memory_key == 'preferences':
                    memory_context += f"Recuerda estas preferencias del usuario: {memory.memory_value}. "
            
            # Obtener historial de mensajes para este LLM
            previous_messages = ConversationMessage.query.filter_by(
                conversation_id=conversation_id,
                llm_id=llm_id
            ).order_by(ConversationMessage.timestamp.asc()).all()
            
            context_from_history = ""
            if len(previous_messages) > 1:  # Más de 1 mensaje (excluyendo el actual)
                context_from_history = "\n\nContexto de conversación previa:\n"
                for msg in previous_messages[:-1]:  # Excluir el último mensaje (actual)
                    context_from_history += f"{msg.role}: {msg.content}\n"
            
            # Simular tiempo de respuesta
            time.sleep(0.1)
            
            # Generar respuesta personalizada con memoria
            response_text = generate_memory_aware_response(
                llm_name, prompt, memory_context, context_from_history
            )
            
            # Guardar la respuesta del LLM
            assistant_message = ConversationMessage(
                conversation_id=conversation_id,
                llm_id=llm_id,
                llm_name=llm_name,
                role='assistant',
                content=response_text
            )
            db.session.add(assistant_message)
            
            results.append({
                'id': llm_id,
                'name': llm_name,
                'status': 'completed',
                'response': response_text
            })
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'results': results,
            'conversation_id': conversation_id
        })
        
    except Exception as e:
        db.session.rollback()
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

def extract_memory_from_text(text):
    """Extraer información de memoria del texto"""
    memory = {}
    text_lower = text.lower()
    
    # Buscar nombres mencionados
    name_patterns = [
        r"mi nombre es (\w+)",
        r"me llamo (\w+)",
        r"soy (\w+)",
        r"puedes llamarme (\w+)",
        r"mi nombre:\s*(\w+)",
        r"nombre:\s*(\w+)"
    ]
    
    for pattern in name_patterns:
        match = re.search(pattern, text_lower)
        if match:
            memory['user_name'] = match.group(1).capitalize()
            break
    
    # Buscar preferencias mencionadas
    preference_indicators = ["prefiero", "me gusta", "no me gusta", "odio", "amo"]
    for indicator in preference_indicators:
        if indicator in text_lower:
            sentences = text.split('.')
            for sentence in sentences:
                if indicator in sentence.lower():
                    memory['preferences'] = sentence.strip()
                    break
            break
    
    # Buscar información personal adicional
    if "trabajo" in text_lower or "profesión" in text_lower:
        memory['profession'] = text  # Simplificado
    
    return memory

def generate_memory_aware_response(llm_name, prompt, memory_context, conversation_context):
    """Generar una respuesta simulada que tenga en cuenta la memoria y el contexto"""
    
    # Respuestas base personalizadas por LLM
    base_responses = {
        'Z.AI GLM-4.5-Flash': "Como Z.AI, procesando tu consulta con mi arquitectura GLM-4.5-Flash...",
        'Google Gemini 2.0 Flash': "Gemini aquí. Utilizando mi capacidad multimodal para analizar tu pregunta...",
        'Mistral AI': "Mistral respondiendo. Con mi enfoque en la eficiencia y precisión...",
        'Meta Llama': "Llama procesando. Aplicando mi entrenamiento en conversaciones naturales..."
    }
    
    # Extraer nombre de usuario si está en la memoria
    user_name = None
    if "se llama" in memory_context:
        name_match = re.search(r"se llama (\w+)", memory_context)
        if name_match:
            user_name = name_match.group(1)
    
    # Respuesta personalizada
    response = base_responses.get(llm_name, f"{llm_name} respondiendo...")
    
    # Responder al prompt específico con contexto de memoria
    prompt_lower = prompt.lower()
    
    if "hola" in prompt_lower or "buenas" in prompt_lower:
        if user_name and "me llamo" not in prompt_lower:
            response += f"\n\n¡Hola de nuevo, {user_name}! Me alegra verte por aquí."
        elif "me llamo" in prompt_lower:
            # Extraer el nombre del prompt actual
            name_match = re.search(r"me llamo (\w+)", prompt_lower)
            if name_match:
                current_name = name_match.group(1).capitalize()
                response += f"\n\n¡Hola {current_name}! Es un placer conocerte. Recordaré tu nombre para futuras conversaciones."
        else:
            response += "\n\n¡Hola! Es un placer conocerte. ¿Cómo te llamas?"
    
    elif "cómo" in prompt_lower and ("está" in prompt_lower or "estas" in prompt_lower):
        if user_name:
            response += f"\n\n¡Muy bien, gracias por preguntar, {user_name}! Es genial poder continuar nuestra conversación."
        else:
            response += "\n\n¡Muy bien, gracias! ¿Cómo estás tú?"
    
    elif "qué" in prompt_lower and "tiempo" in prompt_lower:
        response += "\n\nNo tengo acceso a información meteorológica en tiempo real, pero puedo ayudarte con información general sobre el clima o sugerirte recursos confiables para consultar el pronóstico."
        if user_name:
            response += f" ¿Hay algo específico sobre el tiempo que te gustaría saber, {user_name}?"
    
    else:
        # Respuesta genérica pero personalizada
        if user_name:
            response += f"\n\n{user_name}, he analizado tu consulta '{prompt}' y puedo ofrecerte una perspectiva detallada utilizando las capacidades específicas de {llm_name}."
        else:
            response += f"\n\nHe analizado tu pregunta '{prompt}' y puedo ofrecerte una perspectiva detallada utilizando las capacidades específicas de {llm_name}."
    
    # Agregar características específicas del LLM
    llm_characteristics = {
        'Z.AI GLM-4.5-Flash': "Mi fortaleza está en el procesamiento rápido y eficiente de consultas complejas.",
        'Google Gemini 2.0 Flash': "Puedo procesar tanto texto como imágenes para darte respuestas más completas.",
        'Mistral AI': "Me especializo en respuestas precisas y bien estructuradas.",
        'Meta Llama': "Mi enfoque está en conversaciones naturales y comprensión contextual profunda."
    }
    
    if llm_name in llm_characteristics:
        response += f"\n\n{llm_characteristics[llm_name]}"
    
    # Agregar contexto de conversación si existe
    if conversation_context and not ("hola" in prompt_lower and "me llamo" in prompt_lower):
        response += "\n\nBasándome en nuestra conversación anterior, puedo mantener la continuidad en nuestro diálogo y adaptar mis respuestas a tus necesidades específicas."
    
    return response
