import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './contexts/AuthContext'
import PrivateRoute from './components/PrivateRoute'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import PacientesPage from './pages/PacientesPage'
import PacienteDetalhe from './pages/PacienteDetalhe'
import BuscaSemanticaPage from './pages/BuscaSemanticaPage'
import GerarPacientePage from './pages/GerarPacientePage'

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<PrivateRoute><DashboardPage /></PrivateRoute>} />
      <Route path="/pacientes" element={<PrivateRoute><PacientesPage /></PrivateRoute>} />
      <Route path="/pacientes/:id" element={<PrivateRoute><PacienteDetalhe /></PrivateRoute>} />
      <Route path="/busca" element={<PrivateRoute><BuscaSemanticaPage /></PrivateRoute>} />
      <Route path="/gerar" element={<PrivateRoute><GerarPacientePage /></PrivateRoute>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  )
}
