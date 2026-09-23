import React from 'react';
import { useNavigate } from 'react-router-dom';
import TierBadge from './TierBadge';

const ScanTable = ({ scans }) => {
  const navigate = useNavigate();

  if (!scans || scans.length === 0) {
    return <div className="text-center py-8 text-gray-500">No medical scans found matching query.</div>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            <th scope="col" className="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Scan ID</th>
            <th scope="col" className="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Patient Profile & Findings</th>
            <th scope="col" className="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Current Class</th>
            <th scope="col" className="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Recommended Tier</th>
            <th scope="col" className="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">P(retrieve)</th>
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {scans.map((scan) => {
            const currentTier = scan.current_tier || scan.predicted_class || 'STANDARD';
            const predTier = scan.predicted_class || scan.predicted_tier || currentTier;
            const prob = scan.probability !== undefined ? scan.probability : (scan.prediction?.probability || 0.5);
            const patientAge = scan.patient_age || scan.age || 50;
            const patientGender = scan.patient_gender || 'M';
            const findings = scan.finding_labels || scan.modality || 'No Finding';

            return (
              <tr 
                key={scan.scan_id} 
                onClick={() => navigate(`/scans/${encodeURIComponent(scan.scan_id)}`)}
                className="hover:bg-navy-50 cursor-pointer transition-colors duration-150"
              >
                <td className="px-6 py-4 whitespace-nowrap text-sm font-semibold text-navy-900">
                  {scan.scan_id}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                  <div className="font-medium text-gray-900">DX Chest ({patientAge}y, {patientGender})</div>
                  <div className="text-xs text-gray-500 truncate max-w-xs">{findings}</div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <TierBadge tier={currentTier} />
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <TierBadge tier={predTier} />
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                  <div className="flex items-center">
                    <span className="mr-2 font-mono font-medium">{(prob * 100).toFixed(1)}%</span>
                    <div className="w-16 bg-gray-200 rounded-full h-1.5">
                      <div 
                        className="bg-blue-600 h-1.5 rounded-full" 
                        style={{ width: `${Math.min(100, Math.max(5, prob * 100))}%` }}
                      ></div>
                    </div>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};

export default ScanTable;
