import React, { useState, useEffect } from 'react';
import apiClient from '../api/client';
import ScanTable from '../components/ScanTable';
import { MagnifyingGlassIcon, FunnelIcon } from '@heroicons/react/24/outline';

const ScanBrowser = () => {
  const [scans, setScans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [tierFilter, setTierFilter] = useState('ALL');
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchScans = async () => {
      setLoading(true);
      try {
        const params = new URLSearchParams({ limit: '50' });
        if (search) params.set('search', search);
        if (tierFilter !== 'ALL') params.set('tier', tierFilter);
        const res = await apiClient.get(`/scans?${params.toString()}`);
        setScans(res.data.scans || []);
        setError('');
      } catch (error) {
        console.error("Error fetching scans:", error);
        setError(error.response?.data?.error?.message || error.message || 'Backend unavailable');
      } finally {
        setLoading(false);
      }
    };
    fetchScans();
  }, [search, tierFilter]);

  const filteredScans = scans.filter(scan => {
    const scanId = (scan.scan_id || '').toLowerCase();
    const findings = (scan.finding_labels || scan.modality || '').toLowerCase();
    const patientId = String(scan.patient_id || '');
    
    const matchesSearch = scanId.includes(search.toLowerCase()) || 
                          findings.includes(search.toLowerCase()) ||
                          patientId.includes(search);
                          
    const scanTier = (scan.predicted_class || scan.predicted_tier || scan.current_tier || '').toUpperCase();
    const matchesTier = tierFilter === 'ALL' || scanTier === tierFilter.toUpperCase();
    return matchesSearch && matchesTier;
  });

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-navy-900">Medical Scan Browser</h1>
          <p className="text-gray-500 mt-1">Search, filter, and inspect storage tier recommendations across the repository.</p>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 flex flex-col md:flex-row gap-4">
        <div className="relative flex-grow">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <MagnifyingGlassIcon className="h-5 w-5 text-gray-400" />
          </div>
          <input
            type="text"
            className="block w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md leading-5 bg-white placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
            placeholder="Search by Scan ID, Findings, or Patient ID..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        
        <div className="flex items-center min-w-[200px]">
          <FunnelIcon className="h-5 w-5 text-gray-400 mr-2" />
          <select
            className="block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm rounded-md"
            value={tierFilter}
            onChange={(e) => setTierFilter(e.target.value)}
          >
            <option value="ALL">All Storage Tiers</option>
            <option value="STANDARD">Standard</option>
            <option value="STANDARD_IA">Standard-IA</option>
            <option value="GLACIER">Glacier</option>
            <option value="DEEP_ARCHIVE">Deep Archive</option>
          </select>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
        {error ? (
          <div className="p-8 text-center text-red-600">Unable to load scans: {error}</div>
        ) : loading ? (
          <div className="p-8 text-center text-gray-500">Loading scans from repository...</div>
        ) : (
          <ScanTable scans={filteredScans} />
        )}
      </div>
    </div>
  );
};

export default ScanBrowser;
