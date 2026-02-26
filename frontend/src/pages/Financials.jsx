import { useEffect, useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import api from '../api/client'

const CATEGORY_LABELS = {
  venda_animal:   'Venda de Animal',
  abate:          'Abate',
  leite:          'Leite',
  servico:        'Serviço',
  subsidio:       'Subsídio',
  outros_entrada: 'Outros',
  racao:          'Ração',
  vacina:         'Vacina',
  medicamento:    'Medicamento',
  manutencao:     'Manutenção',
  funcionario:    'Funcionário',
  energia:        'Energia',
  transporte:     'Transporte',
  equipamento:    'Equipamento',
  outros_saida:   'Outros',
}

const CATS_INCOME  = ['venda_animal', 'abate', 'leite', 'servico', 'subsidio', 'outros_entrada']
const CATS_EXPENSE = ['racao', 'vacina', 'medicamento', 'manutencao', 'funcionario',
                      'energia', 'transporte', 'equipamento', 'outros_saida']

const brl = v => `R$ ${Number(v || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`

const INIT_FORM = {
  type: 'expense', category: 'racao', amount: '', description: '',
  occurred_at: new Date().toISOString().slice(0, 10),
}

export default function Financials() {
  const [records, setRecords]     = useState([])
  const [summary, setSummary]     = useState([])
  const [loading, setLoading]     = useState(true)
  const [filterType, setFilterType] = useState('')
  const [showForm, setShowForm]   = useState(false)
  const [form, setForm]           = useState(INIT_FORM)
  const [error, setError]         = useState('')
  const [totals, setTotals]       = useState({ income: 0, expense: 0, balance: 0 })

  function load() {
    const params = filterType ? { type: filterType } : {}
    Promise.all([
      api.get('/financials', { params }),
      api.get('/financials/summary'),
    ]).then(([r, s]) => {
      setRecords(r.data)
      setSummary(s.data)
    }).finally(() => setLoading(false))
  }

  function loadTotals() {
    api.get('/dashboard/stats').then(r => setTotals({
      income:  r.data.income_month  ?? 0,
      expense: r.data.expense_month ?? 0,
      balance: r.data.balance_month ?? 0,
    }))
  }

  useEffect(() => { load() }, [filterType])  // eslint-disable-line
  useEffect(() => { loadTotals() }, [])

  const typeCategories = form.type === 'income' ? CATS_INCOME : CATS_EXPENSE

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    if (!form.amount || Number(form.amount) <= 0) { setError('Informe um valor válido'); return }
    try {
      await api.post('/financials', { ...form, amount: Number(form.amount) })
      setShowForm(false)
      setForm(INIT_FORM)
      load()
      loadTotals()
    } catch (err) {
      setError(err.response?.data?.detail || 'Erro ao salvar')
    }
  }

  async function handleDelete(id) {
    if (!confirm('Excluir este lançamento?')) return
    await api.delete(`/financials/${id}`)
    load()
    loadTotals()
  }

  if (loading) return <div className="page-loading">Carregando financeiro...</div>

  const balColor = totals.balance >= 0 ? '#2e7d32' : '#c62828'

  return (
    <div className="page">
      <div className="page-header">
        <h2 className="page-title">💰 Financeiro</h2>
        <button className="btn-primary" onClick={() => setShowForm(!showForm)}>
          {showForm ? 'Cancelar' : '+ Adicionar'}
        </button>
      </div>

      {/* Monthly totals */}
      <div className="stats-grid" style={{ marginBottom: 20 }}>
        <div className="stat-card" style={{ borderTop: '4px solid #2e7d32' }}>
          <div className="stat-icon" style={{ color: '#2e7d32' }}>📈</div>
          <div className="stat-info">
            <span className="stat-value" style={{ fontSize: 18, color: '#2e7d32' }}>{brl(totals.income)}</span>
            <span className="stat-title">Receitas (mês)</span>
          </div>
        </div>
        <div className="stat-card" style={{ borderTop: '4px solid #c62828' }}>
          <div className="stat-icon" style={{ color: '#c62828' }}>📉</div>
          <div className="stat-info">
            <span className="stat-value" style={{ fontSize: 18, color: '#c62828' }}>{brl(totals.expense)}</span>
            <span className="stat-title">Despesas (mês)</span>
          </div>
        </div>
        <div className="stat-card" style={{ borderTop: `4px solid ${balColor}` }}>
          <div className="stat-icon" style={{ color: balColor }}>
            {totals.balance >= 0 ? '✅' : '⚠️'}
          </div>
          <div className="stat-info">
            <span className="stat-value" style={{ fontSize: 18, color: balColor }}>{brl(totals.balance)}</span>
            <span className="stat-title">Saldo (mês)</span>
          </div>
        </div>
      </div>

      {/* Add form */}
      {showForm && (
        <form className="form-card" onSubmit={handleSubmit}>
          <h3>Novo Lançamento</h3>
          <div className="form-row">
            <label>Tipo
              <select value={form.type} onChange={e => setForm({
                ...form, type: e.target.value,
                category: e.target.value === 'income' ? 'venda_animal' : 'racao',
              })}>
                <option value="income">Receita</option>
                <option value="expense">Despesa</option>
              </select>
            </label>
            <label>Categoria
              <select value={form.category} onChange={e => setForm({ ...form, category: e.target.value })}>
                {typeCategories.map(c => <option key={c} value={c}>{CATEGORY_LABELS[c]}</option>)}
              </select>
            </label>
          </div>
          <div className="form-row">
            <label>Valor (R$)
              <input type="number" step="0.01" min="0.01" value={form.amount}
                onChange={e => setForm({ ...form, amount: e.target.value })}
                required placeholder="0,00" />
            </label>
            <label>Data
              <input type="date" value={form.occurred_at}
                onChange={e => setForm({ ...form, occurred_at: e.target.value })} required />
            </label>
          </div>
          <label>Descrição
            <input value={form.description}
              onChange={e => setForm({ ...form, description: e.target.value })}
              placeholder="Observação ou detalhe" />
          </label>
          {error && <div className="error-msg">{error}</div>}
          <button type="submit" className="btn-primary">Salvar</button>
        </form>
      )}

      {/* Filter */}
      <div className="filter-group" style={{ marginBottom: 16 }}>
        <button className={`btn-filter ${filterType === '' ? 'active' : ''}`}
          onClick={() => setFilterType('')}>Todos</button>
        <button
          className={`btn-filter ${filterType === 'income' ? 'active' : ''}`}
          style={filterType === 'income' ? { background: '#2e7d32', borderColor: '#2e7d32' } : {}}
          onClick={() => setFilterType('income')}>Receitas</button>
        <button
          className={`btn-filter ${filterType === 'expense' ? 'active' : ''}`}
          style={filterType === 'expense' ? { background: '#c62828', borderColor: '#c62828' } : {}}
          onClick={() => setFilterType('expense')}>Despesas</button>
      </div>

      {/* Records table */}
      <div className="table-wrapper" style={{ marginBottom: 28 }}>
        <table className="data-table">
          <thead>
            <tr>
              <th>Tipo</th>
              <th>Categoria</th>
              <th>Valor</th>
              <th>Descrição</th>
              <th>Data</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {records.length === 0 ? (
              <tr><td colSpan={6} className="empty-td">Nenhum lançamento encontrado.</td></tr>
            ) : records.map(r => (
              <tr key={r.id}>
                <td>
                  <span className={`fin-badge ${r.type}`}>
                    {r.type === 'income' ? '↑ Receita' : '↓ Despesa'}
                  </span>
                </td>
                <td>{CATEGORY_LABELS[r.category] || r.category}</td>
                <td>
                  <strong style={{ color: r.type === 'income' ? '#2e7d32' : '#c62828' }}>
                    {brl(r.amount)}
                  </strong>
                </td>
                <td>{r.description || '—'}</td>
                <td>{r.occurred_at}</td>
                <td>
                  <button className="btn-sm btn-danger" onClick={() => handleDelete(r.id)}>✕</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Monthly chart */}
      {summary.length > 0 && (
        <div className="chart-card">
          <h3>Histórico Mensal (últimos 6 meses)</h3>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={summary} margin={{ top: 8, right: 24, left: 0, bottom: 0 }}>
              <XAxis dataKey="month" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} tickFormatter={v => `R$${(v / 1000).toFixed(0)}k`} />
              <Tooltip formatter={v => [brl(v)]} />
              <Legend />
              <Bar dataKey="income" name="Receitas" fill="#2e7d32" radius={[4, 4, 0, 0]} />
              <Bar dataKey="expense" name="Despesas" fill="#c62828" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}
