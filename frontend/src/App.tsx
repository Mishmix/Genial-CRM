import { Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './auth/AuthContext';
import LoginPage from './pages/LoginPage';
import ConversationsPage from './pages/ConversationsPage';
import ConversationDetailPage from './pages/ConversationDetailPage';
import ClientsPage from './pages/ClientsPage';
import ClientDetailPage from './pages/ClientDetailPage';
import OrdersPage from './pages/OrdersPage';
import TemplatesPage from './pages/TemplatesPage';
import AISettingsPage from './pages/AISettingsPage';
import SettingsPage from './pages/SettingsPage';
import ExportPage from './pages/ExportPage';
import ReactivationPage from './pages/ReactivationPage';
import Layout from './components/Layout';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading, error } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-3xl animate-float">
            🤖
          </div>
          <div className="flex justify-center gap-1.5">
            {[0, 1, 2].map(i => (
              <div
                key={i}
                className="w-2 h-2 rounded-full bg-[var(--accent)]"
                style={{
                  animation: 'bounce 1s ease-in-out infinite',
                  animationDelay: `${i * 0.15}s`,
                }}
              />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center p-6">
        <div className="text-center max-w-md">
          <div className="text-6xl mb-4">🚫</div>
          <h2 className="text-xl font-bold mb-2">Access Denied</h2>
          <p className="text-[var(--text-secondary)] mb-6">{error}</p>
          <p className="text-sm text-[var(--text-muted)]">
            Please contact the administrator for access.
          </p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}

function PageWrapper({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}

function AppRoutes() {
  const { isAuthenticated } = useAuth();

  return (
    <Routes>
      <Route
        path="/login"
        element={isAuthenticated ? <Navigate to="/" replace /> : <LoginPage />}
      />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route index element={<PageWrapper><ConversationsPage /></PageWrapper>} />
        <Route path="conversations/:id" element={<PageWrapper><ConversationDetailPage /></PageWrapper>} />
        <Route path="clients" element={<PageWrapper><ClientsPage /></PageWrapper>} />
        <Route path="clients/:id" element={<PageWrapper><ClientDetailPage /></PageWrapper>} />
        <Route path="orders" element={<PageWrapper><OrdersPage /></PageWrapper>} />
        <Route path="templates" element={<PageWrapper><TemplatesPage /></PageWrapper>} />
        <Route path="ai" element={<PageWrapper><AISettingsPage /></PageWrapper>} />
        <Route path="reactivation" element={<PageWrapper><ReactivationPage /></PageWrapper>} />
        <Route path="export" element={<PageWrapper><ExportPage /></PageWrapper>} />
        <Route path="settings" element={<PageWrapper><SettingsPage /></PageWrapper>} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  );
}
