import { useEffect, useState } from 'react'
import api from '../api/client'
import { useAuth } from '../contexts/AuthContext'

const STATUS_OPTS = [
  { value: 'active',       label: 'Ativo',        color: '#2e7d32' },
  { value: 'sold',         label: 'Vendido',       color: '#1565c0' },
  { value: 'slaughtered',  label: 'Abatido',       color: '#b71c1c' },
  { value: 'transferred',  label: 'Transferido',   color: '#e65100' },
]

const statusInfo = (v) => STATUS_OPTS.find(s => s.value === v) || STATUS_OPTS[0]

export default function Animals() {
  const { user } = useAuth()
  const [animals, setAnimals]   = useState([])
  const [loading, setLoading]   = useState(true)
  const [search,  setSearch]    = useState('')
  const [filterStatus, setFilterStatus] = useState('')
  const [editing, setEditing]   = useState(null)
  const [editForm, setEditForm] = useState({
    name: '', description: '', breed: '', weight: '', status: 'active', sale_value: ''
  })

  function load() {
    const params = filterStatus ? { status: filterStatus } : {}
    api.get('/animals', { params })
      .then(r => setAnimals(r.data))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [filterStatus])  // eslint-disable-line

  const filtered = animals.filter(a =>
    [a.name, a.description, a.breed].some(f =>
      (f || '').toLowerCase().includes(search.toLowerCase())
    )
  )

  function startEdit(a) {
    setEditing(a.id)
    setEditForm({
      name:        a.name,
      description: a.description || '',
      breed:       a.breed || '',
      weight:      a.weight ?? '',
      status:      a.status || 'active',
      sale_value:  '',
    })
  }

  async function saveEdit(id) {
    const payload = {
      name:        editForm.name || undefined,
      description: editForm.description,
      breed:       editForm.breed,
      weight:      editForm.weight !== '' ? Number(editForm.weight) : undefined,
      status:      editForm.status,
      sale_value:  editForm.sale_value !== '' ? Number(editForm.sale_value) : undefined,
    }
    await api.put(`/animals/${id}`, payload)
    setEditing(null)
    load()
  }

  async function handleDelete(id, name) {
    if (!confirm(`Excluir "${name}" permanentemente?`)) return
    await api.delete(`/animals/${id}`)
    load()
  }

  if (loading) return <div className="page-loading">Carregando animais...</div>

  return (
    <div className="page">
      <div className="page-header">
        <h2 className="page-title">🐄 Animais</h2>
        <span className="badge">{animals.length} animal(is)</span>
      </div>

      <div className="toolbar">
        <input
          className="search-input"
          placeholder="Buscar por nome, raça ou descrição..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          style={{ marginBottom: 0 }}
        />
        <div className="filter-group">
          <button className={`btn-filter ${filterStatus === '' ? 'active' : ''}`} onClick={() => setFilterStatus('')}>Todos</button>
          {STATUS_OPTS.map(s => (
            <button
              key={s.value}
              className={`btn-filter ${filterStatus === s.value ? 'active' : ''}`}
              style={filterStatus === s.value ? { background: s.color, borderColor: s.color } : {}}
              onClick={() => setFilterStatus(s.value)}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>

      {filtered.length === 0 ? (
        <p className="empty-msg">Nenhum animal encontrado. A câmera ao vivo cadastra automaticamente.</p>
      ) : (
        <div className="card-grid">
          {filtered.map(animal => {
            const st = statusInfo(animal.status)
            return (
              <div key={animal.id} className="entity-card">
                <div className="entity-photo">
                  {animal.photo_path ? (
                    <img src={`/api/animals/${animal.id}/photo`} alt={animal.name} />
                  ) : (
                    <span className="photo-placeholder">🐄</span>
                  )}
                  <span className="status-chip" style={{ background: st.color }}>{st.label}</span>
                </div>

                <div className="entity-info">
                  {editing === animal.id ? (
                    <div className="edit-form">
                      <label>Nome
                        <input className="edit-input" value={editForm.name}
                          onChange={e => setEditForm({ ...editForm, name: e.target.value })} />
                      </label>
                      <label>Raça
                        <input className="edit-input" value={editForm.breed}
                          placeholder="ex: Nelore, Angus, Gir..."
                          onChange={e => setEditForm({ ...editForm, breed: e.target.value })} />
                      </label>
                      <label>Peso (kg)
                        <input className="edit-input" type="number" value={editForm.weight}
                          placeholder="ex: 380"
                          onChange={e => setEditForm({ ...editForm, weight: e.target.value })} />
                      </label>
                      <label>Status
                        <select className="edit-input" value={editForm.status}
                          onChange={e => setEditForm({ ...editForm, status: e.target.value, sale_value: '' })}>
                          {STATUS_OPTS.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
                        </select>
                      </label>
                      {(editForm.status === 'sold' || editForm.status === 'slaughtered') && (
                        <label style={{ color: editForm.status === 'sold' ? '#1565c0' : '#b71c1c' }}>
                          {editForm.status === 'sold' ? '💰 Valor de Venda (R$)' : '🔪 Valor do Abate (R$)'}
                          <input
                            className="edit-input"
                            type="number"
                            step="0.01"
                            min="0"
                            value={editForm.sale_value}
                            placeholder="0,00"
                            onChange={e => setEditForm({ ...editForm, sale_value: e.target.value })}
                          />
                          <small style={{ color: '#666', fontWeight: 400 }}>
                            Será lançado automaticamente no financeiro como receita.
                          </small>
                        </label>
                      )}
                      <label>Descrição
                        <textarea className="edit-textarea" value={editForm.description} rows={3}
                          onChange={e => setEditForm({ ...editForm, description: e.target.value })} />
                      </label>
                      <div className="action-row">
                        <button className="btn-sm btn-success" onClick={() => saveEdit(animal.id)}>Salvar</button>
                        <button className="btn-sm btn-secondary" onClick={() => setEditing(null)}>Cancelar</button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <h4 className="entity-name">{animal.name}</h4>
                      <div className="meta-row">
                        {animal.breed && <span className="meta-tag">🐂 {animal.breed}</span>}
                        {animal.weight && <span className="meta-tag">⚖️ {animal.weight} kg</span>}
                      </div>
                      <p className="entity-desc">{animal.description || 'Sem descrição'}</p>
                      <span className="entity-date">{animal.registered_at}</span>
                      <div className="action-row">
                        <button className="btn-sm btn-secondary" onClick={() => startEdit(animal)}>Editar</button>
                        {user?.role === 'admin' && (
                          <button className="btn-sm btn-danger" onClick={() => handleDelete(animal.id, animal.name)}>Excluir</button>
                        )}
                      </div>
                    </>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
