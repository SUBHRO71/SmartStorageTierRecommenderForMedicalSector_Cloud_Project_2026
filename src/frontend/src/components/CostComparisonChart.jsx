import React from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell } from 'recharts';

const CostComparisonChart = ({ data }) => {
  // Format data for chart
  const chartData = data.policies.map(policy => ({
    name: policy.name,
    Cost: policy.cost,
    // highlight the ML model
    fill: policy.name === 'Current Policy' ? '#1F3B63' : '#9fb3c8'
  }));

  return (
    <div className="h-80 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={chartData}
          margin={{ top: 20, right: 30, left: 20, bottom: 50 }}
        >
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis 
            dataKey="name" 
            angle={-25} 
            textAnchor="end" 
            height={60} 
            tick={{fontSize: 12}}
          />
          <YAxis 
            tickFormatter={(value) => `$${Number(value).toFixed(3)}`}
          />
          <Tooltip 
            formatter={(value) => [`$${Number(value).toFixed(4)}`, `${data.horizon}-month cost`]}
            cursor={{fill: '#f0f4f8'}}
          />
          <Bar dataKey="Cost" radius={[4, 4, 0, 0]}>
            {chartData.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.fill} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};

export default CostComparisonChart;
