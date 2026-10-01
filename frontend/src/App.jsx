import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './contexts/AuthContext'
import PrivateRoute from './components/PrivateRoute'
import Layout from './components/Layout'
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
      <Route path="/" element={
        <PrivateRoute>
          <Layout><DashboardPage /></Layout>
        </PrivateRoute>
      } />
      <Route path="/pacientes" element={
        <PrivateRoute>
          <Layout><PacientesPage /></Layout>
        </PrivateRoute>
      } />
      <Route path="/pacientes/:id" element={
        <PrivateRoute>
          <Layout><PacienteDetalhe /></Layout>
        </PrivateRoute>
      } />
      <Route path="/busca" element={
        <PrivateRoute>
          <Layout><BuscaSemanticaPage /></Layout>
        </PrivateRoute>
      } />
      <Route path="/gerar" element={
        <PrivateRoute>
          <Layout><GerarPacientePage /></Layout>
        </PrivateRoute>
      } />
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
