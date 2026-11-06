import { useState, useEffect } from 'react'
import client from '../api/client'

// Cache em módulo, válido para o token atual (trocar de usuário refaz a leitura sem recarregar a página).
let cached = null
let cachedToken = null
let pending = null

const currentToken = () => localStorage.getItem('anamnese_token')

function load() {
  const token = currentToken()
  if (cached && cachedToken === token) return Promise.resolve(cached)
  if (!pending) {
    pending = client.get('/chat/config')
      .then(r => { cached = r.data; cachedToken = token; return cached })
      .catch(() => ({ models: [], can_choose_model: false, analytics_enabled: false }))
      .finally(() => { pending = null })
  }
  return pending
}

export default function useChatConfig() {
  const [config, setConfig] = useState(cachedToken === currentToken() ? cached : null)
  useEffect(() => {
    let alive = true
    load().then(c => { if (alive) setConfig(c) })
    return () => { alive = false }
  }, [])
  return config // null enquanto carrega
}
