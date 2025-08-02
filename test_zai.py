import requests
import json
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configuración de Z.AI
ZAI_API_KEY = "3d5148a08e3041dd9dd31617128ea9d3.yoj4647nDm10DAPM"
ZAI_BASE_URL = "https://api.z.ai/api/paas/v4"

def test_zai_connection():
    """Probar la conexión básica con Z.AI"""
    print("🔗 Probando conexión con Z.AI...")
    print(f"API Key: {ZAI_API_KEY[:20]}...")
    print(f"Base URL: {ZAI_BASE_URL}")
    print("-" * 50)

def get_available_models():
    """Intentar obtener la lista de modelos disponibles"""
    print("📋 Intentando obtener modelos disponibles...")
    
    # Endpoint común para obtener modelos
    models_endpoint = f"{ZAI_BASE_URL}/models"
    
    headers = {
        'Authorization': f'Bearer {ZAI_API_KEY}',
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.get(models_endpoint, headers=headers)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            models = response.json()
            print("✅ Modelos disponibles:")
            print(json.dumps(models, indent=2, ensure_ascii=False))
            return models
        else:
            print(f"❌ Error al obtener modelos: {response.status_code}")
            print(f"Respuesta: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        return None

def test_model(model_name):
    """Probar un modelo específico con un prompt simple"""
    print(f"\n🧪 Probando modelo: {model_name}")
    print("-" * 30)
    
    url = f"{ZAI_BASE_URL}/chat/completions"
    headers = {
        'Authorization': f'Bearer {ZAI_API_KEY}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        'model': model_name,
        'messages': [
            {
                'role': 'system',
                'content': 'You are a helpful AI assistant.'
            },
            {
                'role': 'user',
                'content': 'Hola, ¿puedes presentarte brevemente?'
            }
        ],
        'temperature': 0.7,
        'top_p': 0.8,
        'max_tokens': 100
    }
    
    try:
        print(f"📤 Enviando request a: {url}")
        print(f"🔑 Headers: Authorization Bearer {ZAI_API_KEY[:20]}...")
        print(f"📦 Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")
        
        response = requests.post(url, headers=headers, json=payload)
        
        print(f"\n📥 Response Status: {response.status_code}")
        print(f"📥 Response Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Respuesta exitosa:")
            print(json.dumps(result, indent=2, ensure_ascii=False))
            
            # Extraer el contenido de la respuesta
            if 'choices' in result and len(result['choices']) > 0:
                content = result['choices'][0]['message']['content']
                print(f"\n💬 Respuesta del modelo:\n{content}")
                return True
        else:
            print(f"❌ Error {response.status_code}:")
            print(response.text)
            return False
            
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        return False

def test_account_info():
    """Intentar obtener información de la cuenta"""
    print("\n💳 Probando información de cuenta...")
    
    # Posibles endpoints para información de cuenta
    endpoints_to_try = [
        f"{ZAI_BASE_URL}/account",
        f"{ZAI_BASE_URL}/billing",
        f"{ZAI_BASE_URL}/usage",
        f"{ZAI_BASE_URL}/me"
    ]
    
    headers = {
        'Authorization': f'Bearer {ZAI_API_KEY}',
        'Content-Type': 'application/json'
    }
    
    for endpoint in endpoints_to_try:
        try:
            print(f"🔍 Probando: {endpoint}")
            response = requests.get(endpoint, headers=headers)
            print(f"   Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Respuesta: {json.dumps(data, indent=4, ensure_ascii=False)}")
            else:
                print(f"   ❌ Error: {response.text}")
                
        except Exception as e:
            print(f"   ❌ Error de conexión: {e}")

def main():
    """Función principal para probar Z.AI"""
    print("🤖 PROGRAMA DE PRUEBA Z.AI")
    print("=" * 50)
    
    # 1. Probar conexión
    test_zai_connection()
    
    # 2. Intentar obtener modelos disponibles
    models = get_available_models()
    
    # 3. Probar modelos específicos conocidos
    models_to_test = [
        'glm-4.5-flash',  # Modelo actualizado que vamos a probar
        'glm-4-flash',
        'glm-4.5',
        'glm-4',
        'chatglm3-6b',
        'chatglm2-6b'
    ]
    
    print(f"\n🧪 Probando modelos específicos...")
    print("=" * 50)
    
    working_models = []
    
    for model in models_to_test:
        success = test_model(model)
        if success:
            working_models.append(model)
        print("\n" + "-" * 50)
    
    # 4. Probar información de cuenta
    test_account_info()
    
    # 5. Resumen final
    print("\n📊 RESUMEN FINAL")
    print("=" * 50)
    print(f"✅ Modelos que funcionan: {working_models}")
    print(f"📊 Total de modelos probados: {len(models_to_test)}")
    print(f"✅ Modelos exitosos: {len(working_models)}")
    
    if working_models:
        print(f"\n🎯 Modelo recomendado para usar: {working_models[0]}")
    else:
        print("\n❌ Ningún modelo funcionó. Revisar API key o configuración.")

if __name__ == "__main__":
    main()
