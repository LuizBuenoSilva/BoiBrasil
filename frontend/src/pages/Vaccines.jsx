import { useEffect, useState } from 'react'
import api from '../api/client'

export default function Vaccines() {
  const [vaccines, setVaccines] = useState([])
  const [animals, setAnimals] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({
    animal_id: '',
    vaccine_name: '',
    applied_at: new Date().toISOString().slice(0, 10),
    next_due: '',
    notes: '',
  })
  const [error, setError] = useState('')

  function load() {
    Promise.all([api.get('/vaccines'), api.get('/animals')])
      .then(([v, a]) => { setVaccines(v.data); setAnimals(a.data) })
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    if (!form.animal_id) { setError('Selecione um animal'); return }
    try {
      await api.post('/vaccines', { ...form, animal_id: Number(form.animal_id) })
      setShowForm(false)
      setForm({ animal_id: '', vaccine_name: '', applied_at: new Date().toISOString().slice(0, 10), next_due: '', notes: '' })
      load()
    } catch (err) {
      setError(err.response?.data?.detail || 'Erro ao salvar')
    }
  }

  async function handleDelete(id) {
    if (!confirm('Excluir este registro de vacina?')) return
    await api.delete(`/vaccines/${id}`)
    load()
  }

  if (loading) return <div className="page-loading">Carregando vacinas...</div>

  return (
    <div className="page">
      <div className="page-header">
        <h2 className="page-title">💉 Vacinas</h2>
        <button className="btn-primary" onClick={() => setShowForm(!showForm)}>
          {showForm ? 'Cancelar' : '+ Registrar Vacina'}
        </button>
      </div>

      {showForm && (
        <form className="form-card" onSubmit={handleSubmit}>
          <h3>Nova Vacinação</h3>
          <div className="form-row">
            <label>Animal
              <select value={form.animal_id} onChange={e => setForm({ ...form, animal_id: e.target.value })} required>
                <option value="">Selecione...</option>
                {animals.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
              </select>
            </label>
            <label>Vacina
              <input value={form.vaccine_name} onChange={e => setForm({ ...form, vaccine_name: e.target.value })} required placeholder="ex: Febre Aftosa" />
            </label>
          </div>
          <div className="form-row">
            <label>Data Aplicação
              <input type="date" value={form.applied_at} onChange={e => setForm({ ...form, applied_at: e.target.value })} required />
            </label>
            <label>Próxima Dose
              <input type="date" value={form.next_due} onChange={e => setForm({ ...form, next_due: e.target.value })} />
            </label>
          </div>
          <label>Observações
            <textarea value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} rows={2} />
          </label>
          {error && <div className="error-msg">{error}</div>}
          <button type="submit" className="btn-primary">Salvar</button>
        </form>
      )}

      <div className="table-wrapper">
        <table className="data-table">
          <thead>
            <tr>
              <th>Animal</th>
              <th>Vacina</th>
              <th>Aplicada em</th>
              <th>Próxima dose</th>
              <th>Aplicada por</th>
              <th>Obs.</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {vaccines.length === 0 ? (
              <tr><td colSpan={7} className="empty-td">Nenhuma vacina registrada.</td></tr>
            ) : vaccines.map(v => (
              <tr key={v.id}>
                <td><strong>{v.animal_name}</strong></td>
                <td>{v.vaccine_name}</td>
                <td>{v.applied_at}</td>
                <td>
                  {v.next_due
                    ? <span className={isOverdue(v.next_due) ? 'overdue' : ''}>{v.next_due}</span>
                    : '—'}
                </td>
                <td>{v.applied_by_name || '—'}</td>
                <td>{v.notes || '—'}</td>
                <td>
                  <button className="btn-sm btn-danger" onClick={() => handleDelete(v.id)}>✕</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function isOverdue(dateStr) {
  return new Date(dateStr) < new Date()
}
