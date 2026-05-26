import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import { ThemeProvider } from './context/ThemeContext'
import { LangProvider } from './context/LangContext'
import { OfflineQueueProvider } from './hooks/useOfflineQueue'
import { useAuth } from './context/AuthContext'
import ProtectedRoute from './components/ProtectedRoute'
// Public pages
import Login from './pages/Login'
import Register from './pages/Register'
import VerifyEmail from './pages/VerifyEmail'
// Rep pages
import Today from './pages/rep/Today'
import GrowerDetail from './pages/rep/GrowerDetail'
import Anomalies from './pages/rep/Anomalies'
import Devices from './pages/rep/Devices'
// Manager pages
import Overview from './pages/manager/Overview'
import Reps from './pages/manager/Reps'
import RepDetail from './pages/manager/RepDetail'
import WeightsHistory from './pages/manager/WeightsHistory'

/** Redirects to the correct home based on role */
function RoleRedirect() {
  const { rep, isLoading } = useAuth()
  if (isLoading) {
    return (
      <div className="min-h-screen bg-forest-50 dark:bg-forest-950 flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-forest-700 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }
  if (!rep) return <Navigate to="/login" replace />
  if (rep.role === 'rep') return <Navigate to="/today" replace />
  return <Navigate to="/manager" replace />
}

export default function App() {
  return (
    <ThemeProvider>
      <LangProvider>
        <BrowserRouter>
          <AuthProvider>
            <OfflineQueueProvider>
              <Routes>
                {/* Root redirect */}
                <Route path="/" element={<RoleRedirect />} />
                {/* Public */}
                <Route path="/login"    element={<Login />} />
                <Route path="/register" element={<Register />} />
                {/* Rep routes */}
                <Route element={<ProtectedRoute requiredRole="rep" />}>
                  <Route path="/today"              element={<Today />} />
                  <Route path="/grower/:entity_id"  element={<GrowerDetail />} />
                  <Route path="/anomalies"          element={<Anomalies />} />
                  <Route path="/devices"            element={<Devices />} />
                </Route>
                {/* Manager routes */}
                <Route element={<ProtectedRoute requiredRole="manager" />}>
                  <Route path="/manager"                    element={<Overview />} />
                  <Route path="/manager/reps"               element={<Reps />} />
                  <Route path="/manager/reps/:rep_id"       element={<RepDetail />} />
                  <Route path="/manager/weights"            element={<WeightsHistory />} />
                </Route>
                {/* Email verification — public, token is the credential */}
                <Route path="/verify-email" element={<VerifyEmail />} />
                {/* Catch-all */}
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </OfflineQueueProvider>
          </AuthProvider>
        </BrowserRouter>
      </LangProvider>
    </ThemeProvider>
  )
}