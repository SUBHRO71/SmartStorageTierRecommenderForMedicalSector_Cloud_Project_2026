import React, { useState, useEffect } from 'react';
import apiClient from '../api/client';
import StatCard from '../components/StatCard';
import TierDistributionChart from '../components/TierDistributionChart';
import ScanTable from '../components/ScanTable';
import { 
  DocumentChartBarIcon, 
  CurrencyDollarIcon, 
  ExclamationTriangleIcon,
  CircleStackIcon
} from '@heroicons/react/24/outline';

const Dashboard = () => {
  const [data, setData] = useState(null);
  const [recentScans, setRecentScans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [summaryRes, scansRes] = await Promise.all([
          apiClient.get('/dashboard/summary'),
          apiClient.get('/scans?limit=5')
        ]);
        
        setData(summaryRes.data);
        setRecentScans(scansRes.data.scans);
      } catch (error) {
        console.error("Error fetching dashboard data:", error);
        setError(error.response?.data?.error?.message || error.message || 'Backend unavailable');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  if (loading) {
    return <div className="animate-pulse space-y-6">
      <div className="h-8 bg-gray-200 rounded w-1/4"></div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {[1,2,3,4].map(i => <div key={i} className="h-24 bg-gray-200 rounded"></div>)}
      </div>
      <div className="h-64 bg-gray-200 rounded"></div>
    </div>;
  }

  if (!data) return <div className="rounded border border-red-200 bg-red-50 p-4 text-red-700">Unable to load the dashboard: {error}</div>;

  const isHighErrorRate = data.wrongly_archived_rate >= 5.0;

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-2xl font-bold text-navy-900">System Dashboard</h1>
          <p className="text-gray-500 mt-1">Overview of your medical image repository.</p>
        </div>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard 
          title="Total Scans Processed" 
          value={new Intl.NumberFormat('en').format(data.total_scans)}
          icon={DocumentChartBarIcon}
          colorClass="bg-blue-500"
        />
        <StatCard 
          title="Projected Monthly Cost" 
          value={`$${new Intl.NumberFormat('en').format(data.projected_monthly_cost)}`}
          icon={CurrencyDollarIcon}
          colorClass="bg-green-500"
        />
        <StatCard 
          title="Wrongly Archived Rate" 
          value={`${data.wrongly_archived_rate}%`}
          subtitle={`${data.wrongly_archived_count} scans required early retrieval`}
          icon={ExclamationTriangleIcon}
          colorClass={isHighErrorRate ? "bg-red-500" : "bg-emerald-500"}
        />
        <StatCard 
          title="Active Storage Tiers" 
          value="4"
          icon={CircleStackIcon}
          colorClass="bg-navy-500"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Chart Column */}
        <div className="card p-6 lg:col-span-1">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Tier Distribution</h2>
          <TierDistributionChart data={data.tier_distribution} />
        </div>

        {/* Table Column */}
        <div className="card lg:col-span-2 flex flex-col">
          <div className="p-6 border-b border-gray-200 flex justify-between items-center">
            <h2 className="text-lg font-semibold text-gray-900">Recent Automated Decisions</h2>
            <a href="/scans" className="text-sm font-medium text-blue-600 hover:text-blue-800">View all &rarr;</a>
          </div>
          <div className="flex-grow overflow-auto">
            <ScanTable scans={recentScans} />
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
