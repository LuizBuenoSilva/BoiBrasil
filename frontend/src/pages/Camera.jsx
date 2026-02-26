import { useEffect, useRef, useState } from 'react'
import api from '../api/client'

const CAM_TYPES = [
  { value: 'ip',     label: 'IP Webcam (Android)' },
  { value: 'webcam', label: 'Webcam Local (USB)' },
  { value: 'rtsp',   label: 'RTSP' },
]

const PLACEHOLDERS = {
  ip:     'http://192.168.1.x:8080/video',
  webcam: '0',
  rtsp:   'rtsp://user:pass@192.168.1.x:554/stream',
}

const TYPE_HINTS = {
  ip:     'Instale o app "IP Webcam" no Android → inicie o servidor → copie a URL exibida na tela.',
  webcam: 'Use 0 para a webcam padrão, 1 para a segunda, etc.',
  rtsp:   'URL RTSP da câmera IP de segurança ou gravador NVR.',
}

export default function Camera() {
  const [cameras, setCameras]     = useState([])
  const [events, setEvents]       = useState([])
  const [wsStatus, setWsStatus]   = useState('connecting')
  const [showForm, setShowForm]   = useState(false)
  const [form, setForm]           = useState({ name: '', source_url: '', type: 'ip' })
  const wsRef = useRef(null)

  function loadCameras() {
    api.get('/cameras').then(r => setCameras(r.data)).catch(console.error)
  }

  useEffect(() => {
    loadCameras()

    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const ws = new WebSocket(`${protocol}://${window.location.host}/api/camera/events`)
    wsRef.current = ws

    ws.onopen = () => {
      setWsStatus('connected')
      const ping = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) ws.send('ping')
      }, 20000)
      ws._ping = ping
    }
    ws.onmessage = e => {
      try {
        const ev = JSON.parse(e.data)
        if (ev.event === 'auto_registered') {
          setEvents(prev => [ev, ...prev].slice(0, 25))
        }
      } catch {}
    }
    ws.onerror  = () => setWsStatus('error')
    ws.onclose  = () => { setWsStatus('disconnected'); clearInterval(ws._ping) }

    return () => { clearInterval(ws._ping); ws.close() }
  }, [])

  async function handleAddCamera(e) {
    e.preventDefault()
    await api.post('/cameras', form)
    setShowForm(false)
    setForm({ name: '', source_url: '', type: 'ip' })
    loadCameras()
  }

  async function handleToggle(cam) {
    await api.put(`/cameras/${cam.id}`, { is_active: !cam.is_active })
    loadCameras()
  }

  async function handleDelete(cam) {
    if (!confirm(`Remover câmera "${cam.name}"?`)) return
    await api.delete(`/cameras/${cam.id}`)
    loadCameras()
  }

  return (
    <div className="page">
      <div className="page-header">
        <h2 className="page-title">📷 Câmeras</h2>
        <span className={`ws-badge ${wsStatus}`}>
          {wsStatus === 'connected'
            ? '● Conectado'
            : wsStatus === 'connecting'
              ? '○ Conectando...'
              : '✕ Desconectado'}
        </span>
        <button className="btn-primary" onClick={() => setShowForm(v => !v)}>
          {showForm ? 'Cancelar' : '+ Câmera'}
        </button>
      </div>

      {/* ---- Formulário de adição ---- */}
      {showForm && (
        <form className="form-card" onSubmit={handleAddCamera} style={{ marginBottom: 24 }}>
          <h3>Adicionar Câmera</h3>
          <div className="form-row">
            <label>Nome
              <input
                value={form.name}
                required
                placeholder="Ex: Curral Principal"
                onChange={e => setForm({ ...form, name: e.target.value })}
              />
            </label>
            <label>Tipo
              <select
                value={form.type}
                onChange={e => setForm({ ...form, type: e.target.value, source_url: '' })}
              >
                {CAM_TYPES.map(t => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </label>
          </div>
          <label>URL / Fonte
            <input
              value={form.source_url}
              required
              placeholder={PLACEHOLDERS[form.type]}
              onChange={e => setForm({ ...form, source_url: e.target.value })}
            />
            <span style={{ fontSize: 11, color: '#888', marginTop: 3 }}>
              {TYPE_HINTS[form.type]}
            </span>
          </label>
          <button type="submit" className="btn-primary" style={{ alignSelf: 'flex-start' }}>
            Adicionar
          </button>
        </form>
      )}

      {/* ---- Grade de câmeras ---- */}
      {cameras.length === 0 ? (
        <div className="empty-msg" style={{ marginTop: 20 }}>
          Nenhuma câmera configurada.<br />
          <span style={{ fontSize: 12, color: '#aaa' }}>
            Clique em "+ Câmera" para adicionar uma câmera IP, webcam ou RTSP.
          </span>
        </div>
      ) : (
        <div className="cameras-grid">
          {cameras.map(cam => (
            <CameraCard key={cam.id} cam={cam} onToggle={handleToggle} onDelete={handleDelete} />
          ))}
        </div>
      )}

      {/* ---- Painel de eventos ---- */}
      {events.length > 0 && (
        <div className="events-panel" style={{ marginTop: 28 }}>
          <h3>Auto-cadastros ({events.length})</h3>
          <div className="event-list">
            {events.map((ev, i) => (
              <div key={i} className="event-item">
                <div className="event-photo">
                  {ev.photo_path ? (
                    <img
                      src={`/api/${ev.entity_type === 'animal' ? 'animals' : 'people'}/${ev.entity_id}/photo`}
                      alt={ev.name}
                      onError={e => { e.target.style.display = 'none' }}
                    />
                  ) : (
                    <span>{ev.entity_type === 'animal' ? '🐄' : '👤'}</span>
                  )}
                </div>
                <div className="event-info">
                  <span className="event-type-badge">
                    {ev.entity_type === 'animal' ? '🐄 Animal' : '👤 Pessoa'}
                  </span>
                  <strong>{ev.name}</strong>
                  {ev.camera_name && (
                    <span style={{ fontSize: 10, color: '#aaa' }}>📷 {ev.camera_name}</span>
                  )}
                  {ev.description && <p className="event-desc">{ev.description}</p>}
                  <div className="event-actions">
                    <a
                      href={ev.entity_type === 'animal' ? '/animals' : '/people'}
                      className="btn-sm btn-secondary"
                    >
                      Ver cadastro
                    </a>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="camera-legend" style={{ marginTop: 20 }}>
        <span className="legend-item"><span className="dot green" />Animal identificado</span>
        <span className="legend-item"><span className="dot orange" />Animal novo (em cadastro)</span>
        <span className="legend-item"><span className="dot blue" />Pessoa</span>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// CameraCard — card individual por câmera
// ---------------------------------------------------------------------------

function CameraCard({ cam, onToggle, onDelete }) {
  const [imgError, setImgError] = useState(false)

  // Ao reativar, força recarregamento do stream
  const streamSrc = cam.is_active
    ? `http://localhost:8000/api/cameras/${cam.id}/stream?t=${cam.id}`
    : null

  return (
    <div className="camera-card">
      <div className="camera-card-header">
        <h4>
          <span className={`cam-status-dot ${cam.is_active ? 'active' : 'inactive'}`} />
          {cam.name}
        </h4>
        <div style={{ display: 'flex', gap: 6 }}>
          <button
            className={`btn-sm ${cam.is_active ? 'btn-secondary' : 'btn-success'}`}
            onClick={() => { setImgError(false); onToggle(cam) }}
          >
            {cam.is_active ? '⏸ Pausar' : '▶ Ativar'}
          </button>
          <button className="btn-sm btn-danger" onClick={() => onDelete(cam)}>✕</button>
        </div>
      </div>

      <div className="camera-card-feed">
        {streamSrc && !imgError ? (
          <img
            src={streamSrc}
            alt={cam.name}
            onError={() => setImgError(true)}
          />
        ) : (
          <div className="cam-error">
            <span>{cam.is_active ? '📡' : '⏸'}</span>
            <p style={{ fontSize: 13 }}>
              {cam.is_active ? 'Conectando à câmera...' : 'Câmera pausada'}
            </p>
            {imgError && cam.is_active && (
              <p className="cam-error-hint">
                Verifique se a câmera está online e a URL está correta.
              </p>
            )}
          </div>
        )}
      </div>

      <div className="camera-card-footer">
        <span className="cam-url">{cam.source_url}</span>
        <span className="source-badge">{cam.type}</span>
      </div>
    </div>
  )
}
