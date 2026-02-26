import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './contexts/AuthContext'
import ProtectedRoute from './components/ProtectedRoute'
import Layout from './components/Layout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Animals from './pages/Animals'
import People from './pages/People'
import Vaccines from './pages/Vaccines'
import Movements from './pages/Movements'
import Camera from './pages/Camera'
import Financials from './pages/Financials'

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route element={<ProtectedRoute />}>
            <Route element={<Layout />}>
              <Route path="/" element={<Dashboard />} />
              <Route path="/animals" element={<Animals />} />
              <Route path="/people" element={<People />} />
              <Route path="/vaccines" element={<Vaccines />} />
              <Route path="/movements" element={<Movements />} />
              <Route path="/camera" element={<Camera />} />
              <Route path="/financials" element={<Financials />} />
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
