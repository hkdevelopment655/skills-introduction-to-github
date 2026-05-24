import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import { useEffect } from 'react'
import { useAuthStore } from './context/authStore'

// Pages
import LandingPage from './pages/LandingPage'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import ResetPasswordPage from './pages/ResetPasswordPage'
import HomePage from './pages/HomePage'
import CollectionsPage from './pages/CollectionsPage'
import ProductDetailPage from './pages/ProductDetailPage'
import VirtualTryOnPage from './pages/VirtualTryOnPage'
import GroupCartPage from './pages/GroupCartPage'
import GroupCartJoinPage from './pages/GroupCartJoinPage'
import CartPage from './pages/CartPage'
import CheckoutPage from './pages/CheckoutPage'
import ProfilePage from './pages/ProfilePage'
import AdminPage from './pages/AdminPage'
import GiftPoolPage from './pages/GiftPoolPage'
import NotFoundPage from './pages/NotFoundPage'
import BrandsPage from './pages/BrandsPage'

function ProtectedRoute({ children, adminOnly = false }) {
  const { isAuthenticated, user } = useAuthStore()
  if (!isAuthenticated) return <Navigate to="/login" replace />
  if (adminOnly && user?.role !== 'admin') return <Navigate to="/home" replace />
  return children
}

export default function App() {
  const { initAuth, isAuthenticated } = useAuthStore()

  useEffect(() => { initAuth() }, [])

  return (
    <BrowserRouter>
      <Toaster
        position="top-right"
        toastOptions={{
          style: { fontFamily: 'DM Sans, sans-serif', fontSize: '14px' },
          success: { iconTheme: { primary: '#1E3A8A', secondary: '#fff' } }
        }}
      />
      <Routes>
        <Route path="/" element={isAuthenticated ? <Navigate to="/home" /> : <LandingPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/reset-password/:token" element={<ResetPasswordPage />} />
        <Route path="/home" element={<ProtectedRoute><HomePage /></ProtectedRoute>} />
        <Route path="/collections" element={<ProtectedRoute><CollectionsPage /></ProtectedRoute>} />
        <Route path="/brands" element={<ProtectedRoute><BrandsPage /></ProtectedRoute>} />
        <Route path="/product/:id" element={<ProtectedRoute><ProductDetailPage /></ProtectedRoute>} />
        <Route path="/try-on" element={<ProtectedRoute><VirtualTryOnPage /></ProtectedRoute>} />
        <Route path="/group-cart" element={<ProtectedRoute><GroupCartPage /></ProtectedRoute>} />
        <Route path="/group-cart/join/:shareLink" element={<ProtectedRoute><GroupCartJoinPage /></ProtectedRoute>} />
        <Route path="/group-cart/:id" element={<ProtectedRoute><GroupCartPage /></ProtectedRoute>} />
        <Route path="/cart" element={<ProtectedRoute><CartPage /></ProtectedRoute>} />
        <Route path="/checkout" element={<ProtectedRoute><CheckoutPage /></ProtectedRoute>} />
        <Route path="/profile" element={<ProtectedRoute><ProfilePage /></ProtectedRoute>} />
        <Route path="/gift-pool/:id" element={<ProtectedRoute><GiftPoolPage /></ProtectedRoute>} />
        <Route path="/admin" element={<ProtectedRoute adminOnly><AdminPage /></ProtectedRoute>} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </BrowserRouter>
  )
}
