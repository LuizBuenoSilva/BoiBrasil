import { useState } from 'react'
import { useNavigate, Navigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

export default function Login() {
  const { user, login, register } = useAuth()
  const navigate = useNavigate()
  const [mode, setMode] = useState('login')
  const [form, setForm] = useState({ name: '', farm_name: '', email: '', password: '' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  if (user) return <Navigate to="/" replace />

  function handleChange(e) {
    setForm({ ...form, [e.target.name]: e.target.value })
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      if (mode === 'login') {
        await login(form.email, form.password)
      } else {
        await register(form.name, form.farm_name, form.email, form.password)
      }
      navigate('/')
    } catch (err) {
      setError(err.response?.data?.detail || 'Erro ao autenticar')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-bg">
      <div className="login-card">
        <div className="login-logo">
          <span style={{ fontSize: 48 }}>&#x1F404;</span>
          <h1>Cattle AI</h1>
          <p>Sistema de Gestao de Rebanho</p>
        </div>

        <div className="login-tabs">
          <button
            className={"tab " + (mode === 'login' ? 'active' : '')}
            onClick={() => { setMode('login'); setError('') }}
          >
            Entrar
          </button>
          <button
            className={"tab " + (mode === 'register' ? 'active' : '')}
            onClick={() => { setMode('register'); setError('') }}
          >
            Criar Fazenda
          </button>
        </div>

        <form onSubmit={handleSubmit} className="login-form">
          {mode === 'register' && (
            <>
              <label>Nome completo
                <input name="name" value={form.name} onChange={handleChange} required placeholder="Joao Silva" />
              </label>
              <label>Nome da Fazenda
                <input name="farm_name" value={form.farm_name} onChange={handleChange} required placeholder="Fazenda Sao Joao" />
              </label>
            </>
          )}
          <label>E-mail
            <input type="email" name="email" value={form.email} onChange={handleChange} required placeholder="email@fazenda.com" />
          </label>
          <label>Senha
            <input type="password" name="password" value={form.password} onChange={handleChange} required placeholder="........" />
          </label>

          {error && <div className="error-msg">{error}</div>}

          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? 'Aguarde...' : mode === 'login' ? 'Entrar' : 'Criar Fazenda'}
          </button>
        </form>

        {mode === 'login' && (
          <p style={{ textAlign: 'center', fontSize: 12, color: '#888', marginTop: 12 }}>
            Novo por aqui? {' '}
            <button className="link-btn" onClick={() => { setMode('register'); setError('') }}>
              Cadastre sua fazenda
            </button>
          </p>
        )}
      </div>
    </div>
  )
}
