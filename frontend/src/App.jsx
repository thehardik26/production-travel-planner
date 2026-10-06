import { useEffect } from 'react'
import { Navigate, Route, Routes, useNavigate } from 'react-router-dom'
import AuthPage from './pages/AuthPage.jsx'
import DashboardPage from './pages/DashboardPage.jsx'
import { getToken } from './lib/api.js'

function ProtectedRoute({ children }) {
  return getToken() ? children : <Navigate to="/login" replace />
}

export default function App() {
  const navigate = useNavigate()

  useEffect(() => {
    // See lib/api.js's _handleUnauthorized - a 401 anywhere in the app
    // clears the token and fires this event; redirecting from this one
    // top-level listener means individual pages don't each need their
    // own "was I just logged out?" handling.
    function handleUnauthorized() {
      navigate('/login', { replace: true })
    }
    window.addEventListener('aura:unauthorized', handleUnauthorized)
    window.addEventListener('wanderplan:unauthorized', handleUnauthorized)
    return () => {
      window.removeEventListener('aura:unauthorized', handleUnauthorized)
      window.removeEventListener('wanderplan:unauthorized', handleUnauthorized)
    }
  }, [navigate])

  return (
    <Routes>
      <Route path="/" element={<Navigate to={getToken() ? '/dashboard' : '/login'} replace />} />
      <Route path="/login" element={<AuthPage mode="login" />} />
      <Route path="/signup" element={<AuthPage mode="signup" />} />
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <DashboardPage />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
