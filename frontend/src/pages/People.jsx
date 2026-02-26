import { useEffect, useState } from 'react'
import api from '../api/client'
import { useAuth } from '../contexts/AuthContext'

const ROLES = ['visitor', 'employee', 'manager']
const roleLabel = { visitor: 'Visitante', employee: 'Funcionário', manager: 'Gerente' }

export default function People() {
  const { user } = useAuth()
  const [people, setPeople] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [editing, setEditing] = useState(null)
  const [editForm, setEditForm] = useState({ name: '', role: 'visitor', description: '', weight: '' })

  function load() {
    api.get('/people').then(r => setPeople(r.data)).finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const filtered = people.filter(p =>
    p.name.toLowerCase().includes(search.toLowerCase()) ||
    (p.role || '').toLowerCase().includes(search.toLowerCase())
  )

  function startEdit(person) {
    setEditing(person.id)
    setEditForm({
      name:        person.name,
      role:        person.role || 'visitor',
      description: person.description || '',
      weight:      person.weight ?? '',
    })
  }

  async function saveEdit(id) {
    const payload = {
      name:        editForm.name || undefined,
      role:        editForm.role,
      description: editForm.description,
      weight:      editForm.weight !== '' ? Number(editForm.weight) : undefined,
    }
    await api.put(`/people/${id}`, payload)
    setEditing(null)
    load()
  }

  async function handleDelete(id, name) {
    if (!confirm(`Excluir "${name}" permanentemente?`)) return
    await api.delete(`/people/${id}`)
    load()
  }

  if (loading) return <div className="page-loading">Carregando pessoas...</div>

  return (
    <div className="page">
      <div className="page-header">
        <h2 className="page-title">👤 Pessoas Cadastradas</h2>
        <span className="badge">{people.length} pessoa(s)</span>
      </div>

      <input
        className="search-input"
        placeholder="Buscar por nome ou cargo..."
        value={search}
        onChange={e => setSearch(e.target.value)}
      />

      {filtered.length === 0 ? (
        <p className="empty-msg">Nenhuma pessoa encontrada. A câmera ao vivo cadastra automaticamente.</p>
      ) : (
        <div className="card-grid">
          {filtered.map(person => (
            <div key={person.id} className="entity-card">
              <div className="entity-photo">
                {person.photo_path ? (
                  <img src={`/api/people/${person.id}/photo`} alt={person.name} />
                ) : (
                  <span className="photo-placeholder">👤</span>
                )}
              </div>
              <div className="entity-info">
                {editing === person.id ? (
                  <div className="edit-form">
                    <label>Nome
                      <input className="edit-input" value={editForm.name}
                        onChange={e => setEditForm({ ...editForm, name: e.target.value })} />
                    </label>
                    <label>Cargo
                      <select className="edit-input" value={editForm.role}
                        onChange={e => setEditForm({ ...editForm, role: e.target.value })}>
                        {ROLES.map(r => <option key={r} value={r}>{roleLabel[r]}</option>)}
                      </select>
                    </label>
                    <label>Peso (kg)
                      <input className="edit-input" type="number" value={editForm.weight}
                        placeholder="ex: 70"
                        onChange={e => setEditForm({ ...editForm, weight: e.target.value })} />
                    </label>
                    <label>Descrição
                      <textarea className="edit-textarea" value={editForm.description} rows={2}
                        onChange={e => setEditForm({ ...editForm, description: e.target.value })} />
                    </label>
                    <div className="action-row">
                      <button className="btn-sm btn-success" onClick={() => saveEdit(person.id)}>Salvar</button>
                      <button className="btn-sm btn-secondary" onClick={() => setEditing(null)}>Cancelar</button>
                    </div>
                  </div>
                ) : (
                  <>
                    <h4 className="entity-name">{person.name}</h4>
                    <div className="meta-row">
                      <span className="role-badge">{roleLabel[person.role] || person.role}</span>
                      {person.weight && <span className="meta-tag">⚖️ {person.weight} kg</span>}
                    </div>
                    <p className="entity-desc">{person.description || 'Sem descrição'}</p>
                    <span className="entity-date">{person.registered_at}</span>
                    <div className="action-row">
                      <button className="btn-sm btn-secondary" onClick={() => startEdit(person)}>Editar</button>
                      {user?.role === 'admin' && (
                        <button className="btn-sm btn-danger" onClick={() => handleDelete(person.id, person.name)}>Excluir</button>
                      )}
                    </div>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
