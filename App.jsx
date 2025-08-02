import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button.jsx'
import { Textarea } from '@/components/ui/textarea.jsx'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card.jsx'
import { Badge } from '@/components/ui/badge.jsx'
import { Copy, Settings, Send, Loader2 } from 'lucide-react'
import './App.css'

function App() {
  const [prompt, setPrompt] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [availableLlms, setAvailableLlms] = useState([])
  const [llmResponses, setLlmResponses] = useState([])

  // Cargar LLMs disponibles al iniciar la aplicación
  useEffect(() => {
    fetchAvailableLlms()
  }, [])

  const fetchAvailableLlms = async () => {
    try {
      const response = await fetch('http://localhost:5000/api/llm/available')
      const data = await response.json()
      
      if (data.success) {
        const llmsWithColors = data.llms.map((llm, index) => ({
          ...llm,
          status: 'idle',
          response: '',
          color: ['bg-green-500', 'bg-blue-500', 'bg-purple-500', 'bg-orange-500'][index % 4]
        }))
        setAvailableLlms(llmsWithColors)
        setLlmResponses(llmsWithColors)
      }
    } catch (error) {
      console.error('Error al cargar LLMs disponibles:', error)
      // Fallback a LLMs por defecto si hay error
      const defaultLlms = [
        { 
          id: 'openai', 
          name: 'OpenAI GPT-4', 
          status: 'idle', 
          response: '',
          color: 'bg-green-500'
        },
        { 
          id: 'gemini', 
          name: 'Google Gemini', 
          status: 'idle', 
          response: '',
          color: 'bg-blue-500'
        },
        { 
          id: 'claude', 
          name: 'Anthropic Claude', 
          status: 'idle', 
          response: '',
          color: 'bg-purple-500'
        },
        { 
          id: 'llama', 
          name: 'Meta Llama', 
          status: 'idle', 
          response: '',
          color: 'bg-orange-500'
        }
      ]
      setAvailableLlms(defaultLlms)
      setLlmResponses(defaultLlms)
    }
  }

  const handleSubmit = async () => {
    if (!prompt.trim()) return
    
    setIsLoading(true)
    
    // Resetear estados de los LLMs
    setLlmResponses(prev => prev.map(llm => ({
      ...llm,
      status: 'loading',
      response: ''
    })))

    try {
      // Llamar al endpoint de simulación del backend
      const response = await fetch('http://localhost:5000/api/llm/simulate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          prompt: prompt,
          llm_ids: availableLlms.map(llm => llm.id)
        })
      })

      const data = await response.json()
      
      if (data.success) {
        // Actualizar las respuestas con los resultados del backend
        setLlmResponses(prev => prev.map(llm => {
          const result = data.results.find(r => r.id === llm.id)
          return result ? { ...llm, ...result } : llm
        }))
      } else {
        // Manejar error
        setLlmResponses(prev => prev.map(llm => ({
          ...llm,
          status: 'error',
          response: 'Error al obtener respuesta del servidor'
        })))
      }
    } catch (error) {
      console.error('Error al enviar prompt:', error)
      // Manejar error de conexión
      setLlmResponses(prev => prev.map(llm => ({
        ...llm,
        status: 'error',
        response: 'Error de conexión con el servidor'
      })))
    } finally {
      setIsLoading(false)
    }
  }

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text)
  }

  const getStatusBadge = (status) => {
    switch (status) {
      case 'loading':
        return <Badge variant="secondary" className="animate-pulse">Cargando...</Badge>
      case 'completed':
        return <Badge variant="default" className="bg-green-600">Completado</Badge>
      case 'error':
        return <Badge variant="destructive">Error</Badge>
      default:
        return <Badge variant="outline">Listo</Badge>
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800">
      <div className="container mx-auto px-4 py-8">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-slate-800 dark:text-slate-100 mb-2">
            Multi-LLM App
          </h1>
          <p className="text-slate-600 dark:text-slate-300 text-lg">
            Compara respuestas de múltiples modelos de IA con un solo prompt
          </p>
        </div>

        {/* Prompt Input Section */}
        <div className="max-w-4xl mx-auto mb-8">
          <Card className="shadow-lg">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Send className="w-5 h-5" />
                Escribe tu prompt
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <Textarea
                placeholder="Escribe aquí tu pregunta o prompt para enviar a todos los LLMs..."
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                className="min-h-[120px] resize-none"
              />
              <div className="flex justify-between items-center">
                <Button
                  variant="outline"
                  onClick={() => {/* Abrir configuración */}}
                  className="flex items-center gap-2"
                >
                  <Settings className="w-4 h-4" />
                  Configurar LLMs
                </Button>
                <Button
                  onClick={handleSubmit}
                  disabled={!prompt.trim() || isLoading}
                  className="flex items-center gap-2 px-6"
                >
                  {isLoading ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Send className="w-4 h-4" />
                  )}
                  Enviar a todos los LLMs
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* LLM Response Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-7xl mx-auto">
          {llmResponses.map((llm) => (
            <Card key={llm.id} className="shadow-lg hover:shadow-xl transition-shadow duration-300">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="flex items-center gap-3">
                    <div className={`w-3 h-3 rounded-full ${llm.color}`}></div>
                    {llm.name}
                  </CardTitle>
                  {getStatusBadge(llm.status)}
                </div>
              </CardHeader>
              <CardContent>
                <div className="min-h-[200px] max-h-[400px] overflow-y-auto">
                  {llm.status === 'loading' ? (
                    <div className="flex items-center justify-center h-32">
                      <div className="flex items-center gap-2 text-slate-500">
                        <Loader2 className="w-5 h-5 animate-spin" />
                        Generando respuesta...
                      </div>
                    </div>
                  ) : llm.response ? (
                    <div className="space-y-3">
                      <p className="text-slate-700 dark:text-slate-300 leading-relaxed whitespace-pre-wrap">
                        {llm.response}
                      </p>
                      <div className="flex justify-end pt-2 border-t">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => copyToClipboard(llm.response)}
                          className="flex items-center gap-2"
                        >
                          <Copy className="w-4 h-4" />
                          Copiar
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <div className="flex items-center justify-center h-32 text-slate-400">
                      Esperando prompt...
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Footer */}
        <div className="text-center mt-12 text-slate-500 dark:text-slate-400">
          <p>Prototipo de aplicación Multi-LLM - Desarrollado con React y Flask</p>
        </div>
      </div>
    </div>
  )
}

export default App

