import React from 'react';

const TIER_CONFIG = {
  STANDARD: { bg: 'bg-green-100', text: 'text-green-800', label: 'Standard' },
  INFREQUENT_ACCESS: { bg: 'bg-blue-100', text: 'text-blue-800', label: 'Infrequent Access' },
  GLACIER: { bg: 'bg-amber-100', text: 'text-amber-800', label: 'Glacier' },
  DEEP_ARCHIVE: { bg: 'bg-purple-100', text: 'text-purple-800', label: 'Deep Archive' }
};

const TierBadge = ({ tier }) => {
  const config = TIER_CONFIG[tier] || { bg: 'bg-gray-100', text: 'text-gray-800', label: tier };
  
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${config.bg} ${config.text}`}>
      {config.label}
    </span>
  );
};

export default TierBadge;
