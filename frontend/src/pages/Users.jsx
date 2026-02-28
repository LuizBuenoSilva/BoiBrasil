import { useEffect, useState } from 'react'
import api from '../api/client'
import { useAuth } from '../contexts/AuthContext'

const ROLES = [
  { value: 'operator', label: 'Operador' },
  { value: 'viewer',   label: 'Visualizador' },
  { value: 'admin',    label: 'Administrador' },
]

export default function Users() {
  const { user } = useAuth()
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ name: '', email: '', password: '', role: 'operator' })
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  function load() {
    api.get('/users').then(r => setUsers(r.data)).finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  async function handleCreate(e) {
    e.preventDefault()
    setError('')
    setSaving(true)
    try {
      await api.post('/users', form)
      setShowForm(false)
      setForm({ name: '', email: '', password: '', role: 'operator' })
      load()
    } catch (err) {
      setError(err.response?.data?.detail || 'Erro ao criar usuario')
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete(u) {
    if (!confirm('Excluir usuario "' + u.name + '"?')) return
    await api.delete('/users/' + u.id)
    load()
  }

  const roleLabel = (r) => ROLES.find(x => x.value === r)?.label || r

  if (loading) return <div className="page-loading">Carregando usuarios...</div>

  return (
    <div className="page">
      <div className="page-header">
        <h2 className="page-title">&#x1F465; Usuarios da Fazenda</h2>
        <span className="badge">{user?.farm_name}</span>
        <button className="btn-primary" onClick={() => setShowForm(v => !v)}>
          {showForm ? 'Cancelar' : '+ Usuario'}
        </button>
      </div>

      {showForm && (
        <form className="form-card" onSubmit={handleCreate} style={{ marginBottom: 24 }}>
          <h3>Adicionar Usuario</h3>
          <div className="form-row">
            <label>Nome
              <input
                value={form.name} required placeholder="Nome completo"
                onChange={e => setForm({ ...form, name: e.target.value })}
              />
            </label>
            <label>Perfil
              <select value={form.role} onChange={e => setForm({ ...form, role: e.target.value })}>
                {ROLES.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
              </select>
            </label>
          </div>
          <label>E-mail
            <input
              type="email" value={form.email} required placeholder="email@fazenda.com"
              onChange={e => setForm({ ...form, email: e.target.value })}
            />
          </label>
          <label>Senha
            <input
              type="password" value={form.password} required placeholder="Senha inicial"
              onChange={e => setForm({ ...form, password: e.target.value })}
            />
          </label>
          {error && <div className="error-msg">{error}</div>}
          <button type="submit" className="btn-primary" style={{ alignSelf: 'flex-start' }} disabled={saving}>
            {saving ? 'Salvando...' : 'Criar Usuario'}
          </button>
        </form>
      )}

      {users.length === 0 ? (
        <p className="empty-msg">Nenhum usuario cadastrado alem de voce.</p>
      ) : (
        <div className="table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th>Nome</th>
                <th>E-mail</th>
                <th>Perfil</th>
                <th>Desde</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {users.map(u => (
                <tr key={u.id}>
                  <td>
                    {u.name}
                    {u.id === user?.id && <span className="badge" style={{ marginLeft: 8, fontSize: 10 }}>Voce</span>}
                  </td>
                  <td>{u.email}</td>
                  <td><span className="role-badge">{roleLabel(u.role)}</span></td>
                  <td style={{ fontSize: 12, color: '#888' }}>{u.created_at?.split('T')[0] || u.created_at}</td>
                  <td>
                    {u.id !== user?.id && (
                      <button className="btn-sm btn-danger" onClick={() => handleDelete(u)}>Excluir</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
