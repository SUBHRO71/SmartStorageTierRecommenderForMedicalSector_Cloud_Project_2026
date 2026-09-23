import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../auth/CognitoAuth';
import { ChartPieIcon, TableCellsIcon, CurrencyDollarIcon, ArrowRightOnRectangleIcon } from '@heroicons/react/24/outline';
import { isMockMode } from '../api/client';

const Navbar = () => {
  const { signOut, user } = useAuth();
  const location = useLocation();

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
                    className={`flex items-center px-3 py-2 rounded-md text-sm font-medium transition-colors duration-200 ${{
                      isActive ? 'bg-navy-800 text-white' : 'text-gray-300 hover:bg-navy-700 hover:text-white'
                    }`}
                  >
                    <Icon className="h-4 w-4 mr-2" />
                    {item.name}
                  </Link>
                );
              })}
            </div>
          </div>
          
          <div className="flex items-center">
            <span className={`inline-flex mr-4 rounded-full px-2 py-1 text-xs font-semibold ${isMockMode ? 'bg-amber-400 text-amber-950' : 'bg-emerald-500 text-white'}`}>
              {isMockMode ? 'MOCK DATA' : 'LIVE API'}
            </span>
            <div className="hidden md:block text-sm text-gray-300 mr-4">
              {user?.attributes?.email || user?.username || 'Doctor'}
            </div>
            <button
              onClick={signOut}
              className="flex items-center text-gray-300 hover:text-white transition-colors"
              title="Sign Out"
            >
              <ArrowRightOnRectangleIcon className="h-5 w-5" />
            </button>
          </div>
        </div>
      </div>
    </nav>
  );
};

export default Navbar;
