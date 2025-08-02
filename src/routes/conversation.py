from flask import Blueprint, request, jsonify
from src.models.user import db
from src.models.conversation import Conversation, ConversationMessage, LLMMemory
import uuid
from datetime import datetime
import re

conversation_bp = Blueprint('conversation', __name__)

@conversation_bp.route('/create', methods=['POST'])
def create_conversation():
    """Crear una nueva conversación"""
    try:
        conversation_id = str(uuid.uuid4())
        conversation = Conversation(id=conversation_id)
        db.session.add(conversation)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'conversation_id': conversation_id
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error al crear conversación: {str(e)}'}), 500

@conversation_bp.route('/<conversation_id>/history', methods=['GET'])
def get_conversation_history(conversation_id):
    """Obtener el historial de una conversación específica"""
    try:
        conversation = Conversation.query.get(conversation_id)
        if not conversation:
            return jsonify({'error': 'Conversación no encontrada'}), 404
        
        # Obtener mensajes agrupados por LLM
        messages_by_llm = {}
        for message in conversation.messages:
            if message.llm_id not in messages_by_llm:
                messages_by_llm[message.llm_id] = {
                    'llm_name': message.llm_name,
                    'messages': []
                }
            messages_by_llm[message.llm_id]['messages'].append(message.to_dict())
        
        # Obtener memoria de cada LLM
        memory_by_llm = {}
        memories = LLMMemory.query.filter_by(conversation_id=conversation_id).all()
        for memory in memories:
            if memory.llm_id not in memory_by_llm:
                memory_by_llm[memory.llm_id] = {}
            memory_by_llm[memory.llm_id][memory.memory_key] = memory.memory_value
        
        return jsonify({
            'success': True,
            'conversation_id': conversation_id,
            'messages_by_llm': messages_by_llm,
            'memory_by_llm': memory_by_llm,
            'created_at': conversation.created_at.isoformat(),
            'updated_at': conversation.updated_at.isoformat()
        })
    except Exception as e:
        return jsonify({'error': f'Error al obtener historial: {str(e)}'}), 500

@conversation_bp.route('/<conversation_id>/memory/<llm_id>', methods=['POST'])
def update_llm_memory(conversation_id, llm_id):
    """Actualizar información de memoria para un LLM específico"""
    try:
        data = request.get_json()
        memory_updates = data.get('memory', {})
        
        conversation = Conversation.query.get(conversation_id)
        if not conversation:
            return jsonify({'error': 'Conversación no encontrada'}), 404
        
        for key, value in memory_updates.items():
            # Buscar si ya existe esta clave de memoria
            existing_memory = LLMMemory.query.filter_by(
                conversation_id=conversation_id,
                llm_id=llm_id,
                memory_key=key
            ).first()
            
            if existing_memory:
                existing_memory.memory_value = value
                existing_memory.updated_at = datetime.utcnow()
            else:
                new_memory = LLMMemory(
                    conversation_id=conversation_id,
                    llm_id=llm_id,
                    memory_key=key,
                    memory_value=value
                )
                db.session.add(new_memory)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Memoria actualizada correctamente'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error al actualizar memoria: {str(e)}'}), 500

def extract_memory_from_response(response_text):
    """Extraer información de memoria del texto de respuesta del LLM"""
    memory = {}
    
    # Buscar nombres mencionados en la respuesta
    name_patterns = [
        r"mi nombre es (\w+)",
        r"me llamo (\w+)",
        r"soy (\w+)",
        r"puedes llamarme (\w+)"
    ]
    
    for pattern in name_patterns:
        match = re.search(pattern, response_text.lower())
        if match:
            memory['user_name'] = match.group(1).capitalize()
            break
    
    # Buscar preferencias mencionadas
    if "prefiero" in response_text.lower() or "me gusta" in response_text.lower():
        # Simplificado: guardar toda la frase que contenga preferencias
        sentences = response_text.split('.')
        for sentence in sentences:
            if "prefiero" in sentence.lower() or "me gusta" in sentence.lower():
                memory['preferences'] = sentence.strip()
                break
    
    return memory

@conversation_bp.route('/<conversation_id>/add_message', methods=['POST'])
def add_message_to_conversation(conversation_id, llm_id=None):
    """Agregar un mensaje a la conversación y extraer información de memoria"""
    try:
        data = request.get_json()
        llm_id = data.get('llm_id')
        llm_name = data.get('llm_name')
        role = data.get('role')  # 'user' o 'assistant'
        content = data.get('content')
        
        if not all([llm_id, llm_name, role, content]):
            return jsonify({'error': 'Faltan campos requeridos'}), 400
        
        conversation = Conversation.query.get(conversation_id)
        if not conversation:
            return jsonify({'error': 'Conversación no encontrada'}), 404
        
        # Crear nuevo mensaje
        message = ConversationMessage(
            conversation_id=conversation_id,
            llm_id=llm_id,
            llm_name=llm_name,
            role=role,
            content=content
        )
        db.session.add(message)
        
        # Si es un mensaje del usuario, extraer posible información de memoria
        if role == 'user':
            extracted_memory = extract_memory_from_response(content)
            for key, value in extracted_memory.items():
                # Actualizar memoria para todos los LLMs en esta conversación
                llm_ids = [msg.llm_id for msg in conversation.messages]
                # Agregar el LLM actual si no está en la lista
                if llm_id not in llm_ids:
                    llm_ids.append(llm_id)
                
                for current_llm_id in set(llm_ids):
                    existing_memory = LLMMemory.query.filter_by(
                        conversation_id=conversation_id,
                        llm_id=current_llm_id,
                        memory_key=key
                    ).first()
                    
                    if existing_memory:
                        existing_memory.memory_value = value
                        existing_memory.updated_at = datetime.utcnow()
                    else:
                        new_memory = LLMMemory(
                            conversation_id=conversation_id,
                            llm_id=current_llm_id,
                            memory_key=key,
                            memory_value=value
                        )
                        db.session.add(new_memory)
        
        # Actualizar timestamp de la conversación
        conversation.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Mensaje agregado correctamente'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error al agregar mensaje: {str(e)}'}), 500

@conversation_bp.route('/list', methods=['GET'])
def list_conversations():
    """Listar todas las conversaciones"""
    try:
        conversations = Conversation.query.order_by(Conversation.updated_at.desc()).all()
        
        result = []
        for conv in conversations:
            # Obtener el último mensaje para mostrar preview
            last_message = ConversationMessage.query.filter_by(
                conversation_id=conv.id
            ).order_by(ConversationMessage.timestamp.desc()).first()
            
            preview = ""
            if last_message:
                preview = last_message.content[:100] + ("..." if len(last_message.content) > 100 else "")
            
            result.append({
                'id': conv.id,
                'created_at': conv.created_at.isoformat(),
                'updated_at': conv.updated_at.isoformat(),
                'preview': preview,
                'message_count': len(conv.messages)
            })
        
        return jsonify({
            'success': True,
            'conversations': result
        })
    except Exception as e:
        return jsonify({'error': f'Error al listar conversaciones: {str(e)}'}), 500
