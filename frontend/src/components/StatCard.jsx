export default function StatCard({ title, value, icon, color = '#2e7d32' }) {
  return (
    <div className="stat-card" style={{ borderTop: `4px solid ${color}` }}>
      <div className="stat-icon" style={{ color }}>{icon}</div>
      <div className="stat-info">
        <span className="stat-value">{value ?? '—'}</span>
        <span className="stat-title">{title}</span>
      </div>
    </div>
  )
}
