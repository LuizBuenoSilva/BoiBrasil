import { useEffect, useState } from 'react'
import api from '../api/client'

export default function Movements() {
  const [movements, setMovements] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('')

  function load(type) {
    api.get('/movements', { params: { entity_type: type || undefined, limit: 200 } })
      .then(r => setMovements(r.data))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load(filter) }, [filter])

  const eventLabel = { entry: 'Entrada', exit: 'Saída' }
  const typeLabel = { animal: '🐄 Animal', person: '👤 Pessoa' }

  if (loading) return <div className="page-loading">Carregando movimentações...</div>

  return (
    <div className="page">
      <div className="page-header">
        <h2 className="page-title">↕️ Movimentações</h2>
        <div className="filter-group">
          <button className={`btn-filter ${filter === '' ? 'active' : ''}`} onClick={() => setFilter('')}>Todos</button>
          <button className={`btn-filter ${filter === 'animal' ? 'active' : ''}`} onClick={() => setFilter('animal')}>Animais</button>
          <button className={`btn-filter ${filter === 'person' ? 'active' : ''}`} onClick={() => setFilter('person')}>Pessoas</button>
        </div>
      </div>

      <div className="table-wrapper">
        <table className="data-table">
          <thead>
            <tr>
              <th>Tipo</th>
              <th>Nome</th>
              <th>Evento</th>
              <th>Origem</th>
              <th>Data/Hora</th>
              <th>Obs.</th>
            </tr>
          </thead>
          <tbody>
            {movements.length === 0 ? (
              <tr><td colSpan={6} className="empty-td">Nenhuma movimentação encontrada.</td></tr>
            ) : movements.map(m => (
              <tr key={m.id}>
                <td>{typeLabel[m.entity_type] || m.entity_type}</td>
                <td><strong>{m.entity_name}</strong></td>
                <td>
                  <span className={`event-badge ${m.event_type}`}>
                    {m.event_type === 'entry' ? '↓ Entrada' : '↑ Saída'}
                  </span>
                </td>
                <td><span className="source-badge">{m.source}</span></td>
                <td>{m.detected_at}</td>
                <td>{m.notes || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
