import React, { lazy, Suspense } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './auth/CognitoAuth';
import ProtectedRoute from './auth/ProtectedRoute';
import Navbar from './components/Navbar';
const Login = lazy(() => import('./pages/Login'));
const Dashboard = lazy(() => import('./pages/Dashboard'));
const ScanBrowser = lazy(() => import('./pages/ScanBrowser'));
const ScanDetail = lazy(() => import('./pages/ScanDetail'));
const CostComparison = lazy(() => import('./pages/CostComparison'));

function App() {
  return (
    <AuthProvider>
      <Router>
        <div className="min-h-screen flex flex-col bg-gray-50">
          <Suspense fallback={<div className="p-8 text-center text-gray-500">Loading page...</div>}>
          <Routes>
            <Route path="/login" element={<Login />} />
            
            {/* Protected Routes */}
            <Route path="/" element={
              <ProtectedRoute>
                <Navbar />
                <main className="flex-grow container mx-auto px-4 py-8 max-w-7xl">
                  <Dashboard />
                </main>
              </ProtectedRoute>
            } />
            
            <Route path="/scans" element={
              <ProtectedRoute>
                <Navbar />
                <main className="flex-grow container mx-auto px-4 py-8 max-w-7xl">
                  <ScanBrowser />
                </main>
              </ProtectedRoute>
            } />
            
            <Route path="/scans/:id" element={
              <ProtectedRoute>
                <Navbar />
                <main className="flex-grow container mx-auto px-4 py-8 max-w-7xl">
                  <ScanDetail />
                </main>
              </ProtectedRoute>
            } />
            
            <Route path="/costs" element={
              <ProtectedRoute>
                <Navbar />
                <main className="flex-grow container mx-auto px-4 py-8 max-w-7xl">
                  <CostComparison />
                </main>
              </ProtectedRoute>
            } />
            
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
          </Suspense>
          <footer className="text-center text-xs text-gray-400 py-4">
            CloudTierRecommender — BCSE355L Cloud Architecture Design, 2026
          </footer>
        </div>
      </Router>
    </AuthProvider>
  );
}

export default App;
