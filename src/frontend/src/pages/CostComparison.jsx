import React, { useState, useEffect } from 'react';
import apiClient from '../api/client';
import CostComparisonChart from '../components/CostComparisonChart';
import { ChartBarIcon, ArrowTrendingDownIcon } from '@heroicons/react/24/outline';

const CostComparison = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchCosts = async () => {
      try {
        const res = await apiClient.get('/costs?horizon=12');
        setData(res.data);
      } catch (error) {
        console.error("Error fetching cost data:", error);
        setError(error.response?.data?.error?.message || error.message || 'Backend unavailable');
      } finally {
        setLoading(false);
      }
    };
    fetchCosts();
  }, []);

  if (loading) return <div className="p-8 text-center text-gray-500">Loading cost models...</div>;
  if (!data) return <div className="p-8 text-center text-red-500">Unable to load cost comparison: {error}</div>;

  const baseline = data.policies.find(p => p.name === 'All Standard')?.cost || 0;
  const mlModel = data.policies.find(p => p.name === 'Current Policy')?.cost || 0;
  const savingsPct = baseline ? ((baseline - mlModel) / baseline * 100).toFixed(1) : 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-navy-900">Cost & Policy Comparison</h1>
        <p className="text-gray-500 mt-1">Comparing the current pretrained-score policy against baseline simulations over a {data.horizon}-month horizon.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="md:col-span-2 card p-6">
          <div className="flex items-center space-x-2 mb-6">
            <ChartBarIcon className="h-6 w-6 text-navy-600" />
            <h2 className="text-lg font-semibold text-gray-900">Projected Total Cost</h2>
          </div>
          <CostComparisonChart data={data} />
        </div>

        <div className="space-y-6">
          <div className="card p-6 bg-gradient-to-br from-navy-900 to-navy-800 text-white">
            <div className="flex items-center space-x-2 mb-2">
              <ArrowTrendingDownIcon className="h-6 w-6 text-green-400" />
              <h2 className="text-lg font-semibold">Estimated Savings</h2>
            </div>
            <p className="text-4xl font-bold text-green-400">{savingsPct}%</p>
            <p className="text-sm text-gray-300 mt-2">vs All Standard storage</p>
            <p className="text-sm text-gray-300 mt-1">${new Intl.NumberFormat('en').format(baseline - mlModel)} saved over {data.horizon} months.</p>
          </div>
          <p className="text-xs text-gray-500 px-1">
            Scope: {data.scope || 'simulation'} · Currency: {data.currency || 'USD'} · Policy: {data.policy_version || 'unspecified'}
          </p>
          
          <div className="card p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Policy Breakdown</h2>
            <div className="space-y-4">
              {data.policies.map((policy, idx) => (
                <div key={idx} className="border-b border-gray-100 last:border-0 pb-3 last:pb-0">
                  <div className="flex justify-between items-center mb-1">
                    <span className={`font-medium ${policy.name === 'Current Policy' ? 'text-navy-700 font-bold' : 'text-gray-700'}`}>
                      {policy.name}
                    </span>
                    <span className="font-mono text-gray-900">${new Intl.NumberFormat('en').format(policy.cost)}</span>
                  </div>
                  <div className="flex justify-between items-center text-xs text-gray-500">
                    <span>Wrongly Archived Rate:</span>
                    <span className={policy.wrongly_archived_rate >= 5.0 ? 'text-red-500 font-medium' : 'text-green-600 font-medium'}>
                      {policy.wrongly_archived_rate}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default CostComparison;
