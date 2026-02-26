import { useEffect, useState } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer,
  PieChart, Pie, Cell,
} from 'recharts'
import api from '../api/client'
import StatCard from '../components/StatCard'

const brl = v => `R$ ${Number(v || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`

const CATEGORY_LABELS = {
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

const PIE_COLORS = [
  '#e53935','#fb8c00','#fdd835','#43a047','#00acc1',
  '#1e88e5','#8e24aa','#6d4c41','#546e7a','#00897b',
]

const CustomPieLabel = ({ cx, cy, midAngle, outerRadius, name, percent }) => {
  if (percent < 0.05) return null
  const RADIAN = Math.PI / 180
  const r = outerRadius + 22
  const x = cx + r * Math.cos(-midAngle * RADIAN)
  const y = cy + r * Math.sin(-midAngle * RADIAN)
  return (
    <text x={x} y={y} fill="#333" textAnchor={x > cx ? 'start' : 'end'} dominantBaseline="central" fontSize={12}>
      {CATEGORY_LABELS[name] || name} ({(percent * 100).toFixed(0)}%)
    </text>
  )
}

export default function Dashboard() {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get('/dashboard/stats')
      .then(r => setStats(r.data))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="page-loading">Carregando dashboard...</div>

  const balColor = (stats?.balance_month ?? 0) >= 0 ? '#2e7d32' : '#c62828'
  const catData = (stats?.expense_by_category ?? []).map(c => ({
    name: c.category,
    value: c.total,
  }))

  return (
    <div className="page">
      <h2 className="page-title" style={{ marginBottom: 20 }}>Dashboard</h2>

      {/* Animais */}
      <h3 style={{ margin: '0 0 10px', color: '#555', fontSize: 14, fontWeight: 600, textTransform: 'uppercase', letterSpacing: 1 }}>
        Rebanho
      </h3>
      <div className="stats-grid" style={{ marginBottom: 24 }}>
        <StatCard title="Ativos" value={stats?.active_animals} icon="🐄" color="#2e7d32" />
        <StatCard title="Vendidos" value={stats?.sold_animals} icon="💰" color="#1565c0" />
        <StatCard title="Abatidos" value={stats?.slaughtered_animals} icon="🔪" color="#b71c1c" />
        <StatCard title="Pessoas Cadastradas" value={stats?.total_people} icon="👤" color="#e65100" />
      </div>

      {/* Financeiro do mês */}
      <h3 style={{ margin: '0 0 10px', color: '#555', fontSize: 14, fontWeight: 600, textTransform: 'uppercase', letterSpacing: 1 }}>
        Financeiro — mês atual
      </h3>
      <div className="stats-grid" style={{ marginBottom: 24 }}>
        <StatCard title="Receitas" value={brl(stats?.income_month)} icon="📈" color="#2e7d32" />
        <StatCard title="Despesas" value={brl(stats?.expense_month)} icon="📉" color="#c62828" />
        <StatCard
          title="Saldo"
          value={brl(stats?.balance_month)}
          icon={(stats?.balance_month ?? 0) >= 0 ? '✅' : '⚠️'}
          color={balColor}
        />
        <StatCard title="Vacinas (30 dias)" value={stats?.vaccines_upcoming} icon="💉" color="#6a1b9a" />
      </div>

      {/* Movimentações — gráfico de barras */}
      <div className="chart-card" style={{ marginBottom: 24 }}>
        <h3>Movimentações — Últimos 7 dias</h3>
        {stats?.activity_chart?.length > 0 ? (
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={stats.activity_chart} margin={{ top: 8, right: 24, left: 0, bottom: 0 }}>
              <XAxis dataKey="day" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip />
              <Legend />
              <Bar dataKey="entries" name="Entradas" fill="#2e7d32" radius={[4, 4, 0, 0]} />
              <Bar dataKey="exits" name="Saídas" fill="#c62828" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <p className="empty-msg">Nenhuma movimentação registrada ainda.</p>
        )}
      </div>

      {/* Despesas por categoria — pizza */}
      {catData.length > 0 && (
        <div className="chart-card">
          <h3>Despesas por Categoria — mês atual</h3>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={catData}
                cx="50%"
                cy="50%"
                outerRadius={100}
                dataKey="value"
                labelLine={false}
                label={CustomPieLabel}
              >
                {catData.map((_, i) => (
                  <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip formatter={v => [brl(v)]} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}
