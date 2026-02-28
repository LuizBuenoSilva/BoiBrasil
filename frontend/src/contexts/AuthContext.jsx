import { createContext, useContext, useState, useCallback } from 'react'
import api from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const stored = localStorage.getItem('user')
    return stored ? JSON.parse(stored) : null
  })

  const login = useCallback(async (email, password) => {
    const { data } = await api.post('/auth/login', { email, password })
    const userData = {
      id: data.user_id,
      name: data.name,
      role: data.role,
      farm_id: data.farm_id,
      farm_name: data.farm_name,
    }
    localStorage.setItem('token', data.access_token)
    localStorage.setItem('user', JSON.stringify(userData))
    setUser(userData)
    return data
  }, [])

  const register = useCallback(async (name, farm_name, email, password) => {
    const { data } = await api.post('/auth/register', { name, farm_name, email, password })
    const userData = {
      id: data.user_id,
      name: data.name,
      role: data.role,
      farm_id: data.farm_id,
      farm_name: data.farm_name,
    }
    localStorage.setItem('token', data.access_token)
    localStorage.setItem('user', JSON.stringify(userData))
    setUser(userData)
    return data
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider value={{ user, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
