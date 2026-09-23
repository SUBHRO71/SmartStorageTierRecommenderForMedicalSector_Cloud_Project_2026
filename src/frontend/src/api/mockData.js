const mockData = {
  dashboardSummary: {
    total_scans: 124500,
    tier_distribution: [
      { name: 'Standard', value: 45000, color: '#10B981' },
      { name: 'Infrequent Access', value: 25000, color: '#3B82F6' },
      { name: 'Glacier', value: 30000, color: '#F59E0B' },
      { name: 'Deep Archive', value: 24500, color: '#EF4444' }
    ],
    projected_monthly_cost: 1450.50,
    wrongly_archived_count: 124, // implies ~0.1% rate
    wrongly_archived_rate: 0.1
  },
  
  scansList: {
    total: 124500,
    page: 1,
    limit: 20,
    scans: [
      { scan_id: 'SCN-10023', modality: 'MRI', body_part: 'BRAIN', age: 45, current_tier: 'STANDARD', predicted_tier: 'GLACIER', probability: 0.89 },
      { scan_id: 'SCN-10024', modality: 'CT', body_part: 'CHEST', age: 62, current_tier: 'STANDARD', predicted_tier: 'STANDARD', probability: 0.95 },
      { scan_id: 'SCN-10025', modality: 'XRAY', body_part: 'KNEE', age: 28, current_tier: 'STANDARD', predicted_tier: 'DEEP_ARCHIVE', probability: 0.99 },
      { scan_id: 'SCN-10026', modality: 'PET', body_part: 'WHOLE_BODY', age: 55, current_tier: 'INFREQUENT_ACCESS', predicted_tier: 'GLACIER', probability: 0.76 },
      { scan_id: 'SCN-10027', modality: 'US', body_part: 'ABDOMEN', age: 34, current_tier: 'STANDARD', predicted_tier: 'STANDARD', probability: 0.82 },
    ]
  },

  scanDetail: {
    scan_id: 'SCN-10023',
    metadata: {
      patient_age: 45,
      patient_gender: 'M',
      modality: 'MRI',
      body_part: 'BRAIN',
      study_date: '2022-04-12T10:30:00Z',
      file_size_mb: 254.5,
      findings: 'Normal brain MRI. No acute intracranial abnormality.'
    },
    access_history: [
      { date: '2022-04-12T11:00:00Z', user: 'Dr. Smith', reason: 'Initial Read' },
      { date: '2022-04-15T09:15:00Z', user: 'Dr. Jones', reason: 'Follow-up Consultation' }
    ],
    prediction: {
      class: 'GLACIER',
      probability: 0.89,
      reason: 'Scan is older than 3 years (MRI). Only 2 accesses in history, none in the last 2 years. Body part (BRAIN) with normal findings typically has low readmission retrieval rate.'
    },
    timestamps: {
      uploaded_at: '2022-04-12T10:45:00Z',
      last_accessed_at: '2022-04-15T09:15:00Z',
      tier_last_modified_at: '2022-05-15T00:00:00Z'
    },
    cost_breakdown: {
      STANDARD: 5.85,
      INFREQUENT_ACCESS: 3.18,
      GLACIER: 1.02,
      DEEP_ARCHIVE: 0.25
    }
  },

  predictionResult: {
    class: 'GLACIER',
    probability: 0.91,
    reason: 'Updated prediction: Scan age now exceeds 4 years. Probability of retrieval is < 1%.',
    cost_breakdown: {
      STANDARD: 5.85,
      INFREQUENT_ACCESS: 3.18,
      GLACIER: 1.02,
      DEEP_ARCHIVE: 0.25
    }
  },

  costComparison: {
    horizon: 12, // months
    policies: [
      { name: 'All Standard', cost: 28500, wrongly_archived_rate: 0.0 },
      { name: 'Age-based (1yr=IA, 3yr=Glacier)', cost: 12400, wrongly_archived_rate: 8.5 },
      { name: 'AWS Intelligent Tiering', cost: 14200, wrongly_archived_rate: 0.0 }, // IT doesn't wrongly archive, it just charges retrieval
      { name: 'Our ML Model', cost: 9500, wrongly_archived_rate: 2.1 }
    ]
  }
};

export default mockData;
