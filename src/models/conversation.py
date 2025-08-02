from src.models.user import db
from datetime import datetime
import json

class Conversation(db.Model):
    """Modelo para almacenar conversaciones con múltiples LLMs"""
    id = db.Column(db.String(36), primary_key=True)  # UUID para la sesión
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relación con los mensajes
    messages = db.relationship('ConversationMessage', backref='conversation', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Conversation {self.id}>'

class ConversationMessage(db.Model):
    """Modelo para almacenar mensajes individuales de cada LLM en una conversación"""
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.String(36), db.ForeignKey('conversation.id'), nullable=False)
    llm_id = db.Column(db.String(50), nullable=False)  # ID del LLM (zai, gemini, mistral, etc.)
    llm_name = db.Column(db.String(100), nullable=False)  # Nombre display del LLM
    role = db.Column(db.String(20), nullable=False)  # 'user' o 'assistant'
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Message {self.id} - {self.llm_id}>'
    
    def to_dict(self):
        """Convierte el mensaje a diccionario para APIs"""
        return {
            'role': self.role,
            'content': self.content,
            'timestamp': self.timestamp.isoformat()
        }

class LLMMemory(db.Model):
    """Modelo para almacenar información persistente de memoria para cada LLM"""
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.String(36), db.ForeignKey('conversation.id'), nullable=False)
    llm_id = db.Column(db.String(50), nullable=False)
    memory_key = db.Column(db.String(100), nullable=False)  # ej: 'user_name', 'preferences', etc.
    memory_value = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Índice único para evitar duplicados
    __table_args__ = (db.UniqueConstraint('conversation_id', 'llm_id', 'memory_key'),)
    
    def __repr__(self):
        return f'<LLMMemory {self.llm_id}:{self.memory_key}>'
