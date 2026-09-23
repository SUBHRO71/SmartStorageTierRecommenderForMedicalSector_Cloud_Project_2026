import React, { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../auth/CognitoAuth';
import { ChartPieIcon, TableCellsIcon, CurrencyDollarIcon, ArrowRightOnRectangleIcon, MoonIcon, SunIcon } from '@heroicons/react/24/outline';
import { isMockMode } from '../api/client';

const Navbar = () => {
  const { signOut, user } = useAuth();
  const location = useLocation();
  const [darkMode, setDarkMode] = useState(() => localStorage.getItem('theme') === 'dark');

  useEffect(() => {
    document.documentElement.classList.toggle('dark', darkMode);
    localStorage.setItem('theme', darkMode ? 'dark' : 'light');
  }, [darkMode]);

  const navItems = [
    { name: 'Dashboard', path: '/', icon: ChartPieIcon },
    { name: 'Scan Browser', path: '/scans', icon: TableCellsIcon },
    { name: 'Cost Analysis', path: '/costs', icon: CurrencyDollarIcon },
  ];

  return (
    <nav className="bg-navy-900 text-white shadow-md">
      <div className="container mx-auto px-4 max-w-7xl">
        <div className="flex justify-between h-16">
          <div className="flex items-center space-x-8">
            <Link to="/" className="flex items-center flex-shrink-0 font-bold text-xl tracking-wide">
              MedStorage<span className="text-navy-300 font-light ml-1">AI</span>
            </Link>
            
            <div className="hidden md:flex space-x-4">
              {navItems.map((item) => {
                const isActive = location.pathname === item.path || (item.path !== '/' && location.pathname.startsWith(item.path));
                const Icon = item.icon;
                return (
                  <Link
                    key={item.name}
                    to={item.path}
                    className={`flex items-center px-3 py-2 rounded-md text-sm font-medium transition-colors duration-200 ${
                      isActive ? 'border-b-2
