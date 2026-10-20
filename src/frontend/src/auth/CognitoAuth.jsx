import React, { createContext, useContext, useState, useEffect } from 'react';
import { Amplify } from '@aws-amplify/core';
import { Auth } from '@aws-amplify/auth';
import { userPoolId, clientId, region } from '../runtime';

// Configure Amplify (only if real env vars are present, otherwise mock)
if (userPoolId) {
  Amplify.configure({
    Auth: {
      region,
      userPoolId,
      userPoolWebClientId: clientId,
    }
  });
}

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  
  // Use mock auth if no AWS configuration is provided
  const isMockAuth = !userPoolId;

  useEffect(() => {
    checkUser();
  }, []);

  const checkUser = async () => {
    try {
      if (isMockAuth) {
        const storedUser = localStorage.getItem('mockUser');
        if (storedUser) {
          setUser(JSON.parse(storedUser));
        }
      } else {
        const cognitoUser = await Auth.currentAuthenticatedUser();
        setUser(cognitoUser);
      }
    } catch (error) {
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  const signIn = async (username, password) => {
    if (isMockAuth) {
      // Mock sign in
      return new Promise((resolve, reject) => {
        setTimeout(() => {
          if (username === 'admin@hospital.com' && password === 'password') {
            const mockUser = { username, attributes: { email: username, name: 'Dr. Admin' } };
            localStorage.setItem('mockUser', JSON.stringify(mockUser));
            setUser(mockUser);
            resolve(mockUser);
          } else {
            reject(new Error('Invalid credentials (use admin@hospital.com / password)'));
          }
        }, 1000);
      });
    } else {
      const authResult = await Auth.signIn(username, password);
      if (authResult.challengeName) {
        throw new Error('Your account requires a password or verification step. Ask the administrator to complete account setup.');
      }
      setUser(authResult);
      return authResult;
    }
  };

  const signOut = async () => {
    if (isMockAuth) {
      localStorage.removeItem('mockUser');
      setUser(null);
    } else {
      await Auth.signOut();
      setUser(null);
    }
  };

  if (loading) {
    return <div className="min-h-screen flex items-center justify-center bg-gray-50 text-navy-900">Loading application...</div>;
  }

  return (
    <AuthContext.Provider value={{ user, signIn, signOut, isAuthenticated: !!user }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
