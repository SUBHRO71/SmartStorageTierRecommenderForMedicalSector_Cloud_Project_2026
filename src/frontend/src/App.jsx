import React, { lazy, Suspense } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './auth/CognitoAuth';
import ProtectedRoute from './auth/ProtectedRoute';
import { ArchiveProvider } from './archive/ArchiveContext';
import ArchiveShell from './archive/ArchiveShell';
const Overview = lazy(() => import('./archive/Overview'));
const Studies = lazy(() => import('./archive/Studies'));
import { Quality, Operations } from './archive/ArchiveLists';
const ImportStudy = lazy(() => import('./archive/ImportStudy'));
const StudyDetail = lazy(() => import('./archive/StudyDetail'));
const ArchiveCosts = lazy(() => import('./archive/ArchiveCosts'));
const ProjectGuide = lazy(() => import('./archive/ProjectGuide'));
const Login = lazy(() => import('./pages/Login'));

function App() {
  return (
    <AuthProvider>
      <Router>
        <div className="min-h-screen flex flex-col bg-gray-50">
          <Suspense fallback={<div className="p-8 text-center text-gray-500">Loading page...</div>}>
          <Routes>
            <Route path="/login" element={<Login />} />
            
            {/* Protected Routes */}
            <Route element={<ProtectedRoute><ArchiveProvider><ArchiveShell /></ArchiveProvider></ProtectedRoute>}>
              <Route index element={<Overview />} />
              <Route path="/studies" element={<Studies />} />
              <Route path="/studies/:id" element={<StudyDetail />} />
              <Route path="/quality" element={<Quality />} />
              <Route path="/operations" element={<Operations />} />
              <Route path="/costs" element={<ArchiveCosts />} />
              <Route path="/project/:section" element={<ProjectGuide />} />
              <Route path="/project" element={<Navigate to="/project/architecture" replace />} />
              <Route path="/import" element={<ImportStudy />} />
            </Route>
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
