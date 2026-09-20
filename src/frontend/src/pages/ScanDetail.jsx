import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import apiClient from '../api/client';
import TierBadge from '../components/TierBadge';
import { ArrowLeftIcon, CpuChipIcon, ClockIcon, DocumentTextIcon, CurrencyDollarIcon } from '@heroicons/react/24/outline';

const ScanDetail = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [repredicting, setRepredicting] = useState(false);

  useEffect(() => {
    const fetchDetail = async () => {
      try {
        const res = await apiClient.get(`/scans/${id}`);
        setData(res.data);
      } catch (error) {
        console.error("Error fetching scan details:", error);
      } finally {
        setLoading(false);
      }
    };
    fetchDetail();
  }, [id]);

  const handleRepredict = async () => {
    setRepredicting(true);
    try {
      const res = await apiClient.post(`/scans/${id}/predict`);
      setData(prev => ({
        ...prev,
        predicted_class: res.data.predicted_class || res.data.class,
        probability: res.data.probability,
        reason: res.data.reason,
        cost_breakdown: res.data.cost_breakdown || prev.cost_breakdown
      }));
    } catch (error) {
      console.error("Error running prediction:", error);
      alert("Failed to re-run prediction");
    } finally {
      setRepredicting(false);
    }
  };

  if (loading) return <div className="p-8 text-center text-gray-500">Loading scan details...</div>;
  if (!data) return <div className="p-8 text-center text-red-500">Scan not found.</div>;

  // Normalization layer for backend/mock compatibility
  const scanId = data.scan_id || id;
  const predClass = data.predicted_class || data.prediction?.class || data.current_tier || 'STANDARD';
  const predProb = data.probability !== undefined ? data.probability : (data.prediction?.probability || 0.5);
  const predReason = data.reason || data.prediction?.reason || 'Calculated optimal tier minimizing total expected cost.';
  const costBreakdown = data.cost_breakdown || {
    'STANDARD': 0.0041,
    'STANDARD_IA': 0.0032,
    'GLACIER': 0.0044,
    'DEEP_ARCHIVE': 0.0096
  };
  
  const patientAge = data.patient_age || data.metadata?.patient_age || 50;
  const patientGender = data.patient_gender || data.metadata?.patient_gender || 'M';
  const viewPosition = data.view_position || data.metadata?.view_position || 'PA';
  const findingLabels = data.finding_labels || data.metadata?.findings || 'No Finding';
  const modality = data.metadata?.modality || 'DX (Digital Radiography)';
  const bodyPart = data.metadata?.body_part || 'CHEST';
  const fileSizeMb = data.object_size_bytes ? (data.object_size_bytes / (1024 * 1024)).toFixed(1) : (data.metadata?.file_size_mb || 15.0);
  const accessHistory = data.access_history || [
    { date: data.last_accessed || new Date().toISOString(), user: 'PACS Auto-Ingest', reason: 'Initial ingestion and feature extraction' }
  ];

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <div className="flex items-center space-x-4">
        <button 
          onClick={() => navigate(-1)} 
          className="p-2 rounded-full hover:bg-gray-200 transition-colors"
          title="Go Back"
        >
          <ArrowLeftIcon className="h-5 w-5 text-gray-600" />
        </button>
        <div>
          <h1 className="text-2xl font-bold text-navy-900">Scan: {scanId}</h1>
          <p className="text-sm text-gray-500">Modality: {modality} | Body Part: {bodyPart}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Left Column: Prediction (THE MONEY SCREEN) */}
        <div className="md:col-span-2 space-y-6">
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 border-l-4 border-l-blue-600">
            <div className="flex justify-between items-start mb-4">
              <div className="flex items-center space-x-2">
                <CpuChipIcon className="h-6 w-6 text-blue-600" />
                <h2 className="text-lg font-bold text-gray-900">AI Storage Tier Recommendation</h2>
              </div>
              <button 
                onClick={handleRepredict}
                disabled={repredicting}
                className="text-xs bg-blue-50 hover:bg-blue-100 text-blue-700 font-semibold px-3 py-1.5 rounded transition-colors disabled:opacity-50"
              >
                {repredicting ? 'Evaluating Model...' : 'Re-run Model'}
              </button>
            </div>
            
            <div className="bg-gray-50 p-4 rounded-lg mb-6 border border-gray-100 flex flex-col sm:flex-row justify-between items-center sm:items-start gap-4">
              <div>
                <p className="text-sm text-gray-500 mb-1">Recommended Storage Tier</p>
                <div className="text-2xl"><TierBadge tier={predClass} /></div>
              </div>
              
              <div className="w-full sm:w-1/2">
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-gray-500">Retrieval Probability P(retrieve)</span>
                  <span className="font-bold text-navy-900">{(predProb * 100).toFixed(1)}%</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div 
                    className="bg-blue-600 h-2 rounded-full transition-all duration-500" 
                    style={{ width: `${Math.min(100, Math.max(5, predProb * 100))}%` }}
                  ></div>
                </div>
              </div>
            </div>

            <div className="mb-2">
              <h3 className="text-sm font-semibold text-gray-900 uppercase tracking-wider mb-2">Clinical & Economic Rationale (The "Why")</h3>
              <div className="bg-blue-50 text-blue-950 p-4 rounded-md text-sm leading-relaxed border border-blue-100 font-sans">
                {predReason}
              </div>
            </div>
          </div>

          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <div className="flex items-center space-x-2 mb-4">
              <CurrencyDollarIcon className="h-5 w-5 text-gray-500" />
              <h2 className="text-lg font-semibold text-gray-900">Expected Annual Cost Comparison by Storage Class</h2>
            </div>
            
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Storage Class</th>
                    <th scope="col" className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Expected Total Cost / Yr</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {Object.entries(costBreakdown).map(([tier, cost]) => {
                    const isSelected = tier.toUpperCase() === predClass.toUpperCase();
                    return (
                      <tr key={tier} className={isSelected ? "bg-green-50" : ""}>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 font-medium">
                          <TierBadge tier={tier} />
                          {isSelected && <span className="ml-2 text-xs text-green-700 font-bold">(Argmin Optimal)</span>}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-right font-mono font-semibold">
                          ${typeof cost === 'number' ? cost.toFixed(4) : cost}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Right Column: Metadata & History */}
        <div className="space-y-6">
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <div className="flex items-center space-x-2 mb-4">
              <DocumentTextIcon className="h-5 w-5 text-gray-500" />
              <h2 className="text-lg font-semibold text-gray-900">Scan & Patient Profile</h2>
            </div>
            <div className="space-y-3 text-sm">
              <div className="flex justify-between border-b border-gray-100 pb-2">
                <span className="text-gray-500">Patient Age & Gender</span>
                <span className="font-medium">{patientAge} yrs, {patientGender}</span>
              </div>
              <div className="flex justify-between border-b border-gray-100 pb-2">
                <span className="text-gray-500">View Position</span>
                <span className="font-medium">{viewPosition}</span>
              </div>
              <div className="flex justify-between border-b border-gray-100 pb-2">
                <span className="text-gray-500">Follow-up Index</span>
                <span className="font-medium">{data.follow_up_number ?? 0}</span>
              </div>
              <div className="flex justify-between border-b border-gray-100 pb-2">
                <span className="text-gray-500">File Size</span>
                <span className="font-medium">{fileSizeMb} MB</span>
              </div>
              <div className="pt-2">
                <span className="text-gray-500 block mb-1">Radiological Findings</span>
                <p className="text-gray-900 bg-gray-50 p-2 rounded italic text-xs border border-gray-100">
                  {findingLabels}
                </p>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <div className="flex items-center space-x-2 mb-4">
              <ClockIcon className="h-5 w-5 text-gray-500" />
              <h2 className="text-lg font-semibold text-gray-900">Access History & Audit</h2>
            </div>
            {accessHistory.length === 0 ? (
              <p className="text-sm text-gray-500 italic">No access history recorded.</p>
            ) : (
              <ul className="relative border-l border-gray-200 ml-3 space-y-4">
                {accessHistory.map((record, idx) => (
                  <li key={idx} className="ml-4">
                    <div className="absolute w-2.5 h-2.5 bg-blue-600 rounded-full -left-[5.5px] mt-1.5 border border-white"></div>
                    <p className="text-xs text-gray-500">{record.date}</p>
                    <p className="text-sm font-medium text-gray-900">{record.user}</p>
                    <p className="text-xs text-gray-600">{record.reason}</p>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ScanDetail;
