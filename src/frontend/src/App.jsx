import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './auth/CognitoAuth';
import ProtectedRoute from './auth/ProtectedRoute';
import Navbar from './components/Navbar';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import ScanBrowser from './pages/ScanBrowser';
import ScanDetail from './pages/ScanDetail';
import CostComparison from './pages/CostComparison';

function App() {
  return (
    <AuthProvider>
      <Router>
        <div className="min-h-screen flex flex-col bg-gray-50">
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
        </div>
      </Router>
    </AuthProvider>
  );
}

export default App;
