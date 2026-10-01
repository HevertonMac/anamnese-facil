import { createContext, useContext, useState, useEffect } from 'react'
import client from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem('anamnese_token')
    if (token) {
      client.get('/auth/me')
        .then(r => setUser(r.data))
        .catch(() => localStorage.removeItem('anamnese_token'))
        .finally(() => setLoading(false))
    } else {
      setLoading(false)
    }
  }, [])

  async function login(email, password) {
    const { data } = await client.post('/auth/login', { email, password })
    localStorage.setItem('anamnese_token', data.access_token)
    const me = await client.get('/auth/me')
    setUser(me.data)
    return me.data
  }

  function logout() {
    localStorage.removeItem('anamnese_token')
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
