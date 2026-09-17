import React from 'react';
import { BarChart3, TrendingUp, ShieldCheck } from 'lucide-react';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, Legend } from 'recharts';

export default function ResultsView() {
  const chartData = [
    { name: 'Logistic Reg', PR_AUC: 0.712, F1: 0.694, Recall: 0.612 },
    { name: 'Random Forest', PR_AUC: 0.825, F1: 0.814, Recall: 0.756 },
    { name: 'XGB Raw Baseline', PR_AUC: 0.841, F1: 0.835, Recall: 0.781 },
    { name: 'Exp 1: Pos Weight', PR_AUC: 0.862, F1: 0.838, Recall: 0.841 },
    { name: 'Exp 1.1: PosW + Thresh', PR_AUC: 0.884, F1: 0.842, Recall: 0.880 },
    { name: 'Exp 2: SMOTE', PR_AUC: 0.849, F1: 0.820, Recall: 0.815 },
    { name: 'Exp 3: IsoForest Meta', PR_AUC: 0.858, F1: 0.830, Recall: 0.802 }
  ];

  return (
    <div className="p-8 space-y-8 max-w-7xl mx-auto">
      <div className="space-y-2">
        <div className="inline-flex items-center space-x-2 bg-cyan-500/10 border border-cyan-500/30 px-3 py-1 rounded-full text-xs font-mono text-cyan-300">
          <BarChart3 className="w-3.5 h-3.5" />
          <span>Results & Comparative Evaluation</span>
        </div>
        <h2 className="text-2xl font-extrabold text-white tracking-tight">
          Metrics Comparison Across Experiment Tree
        </h2>
        <p className="text-slate-400 text-sm">
          Track progression from baseline benchmarks to the winning hypothesis node (Exp 1.1: Threshold Optimization + Pos-Weighting).
        </p>
      </div>

      {/* Main Chart Card */}
      <div className="glass-panel p-6 rounded-xl space-y-6">
        <div className="flex items-center justify-between">
          <h3 className="font-bold text-sm text-slate-200 uppercase tracking-wider font-mono">
            PR-AUC, F1-Score, and Recall Progression
          </h3>
          <span className="text-xs font-mono text-emerald-400 bg-emerald-950 px-3 py-1 rounded border border-emerald-800">
            Peak PR-AUC: 0.884 (+24.1% gain)
          </span>
        </div>

        <div className="h-80 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 20, right: 30, left: 0, bottom: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="name" stroke="#94a3b8" tick={{ fontSize: 11 }} />
              <YAxis domain={[0.5, 1.0]} stroke="#94a3b8" tick={{ fontSize: 11 }} />
              <Tooltip
                contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px', fontSize: '12px' }}
              />
              <Legend wrapperStyle={{ fontSize: '12px', paddingTop: '10px' }} />
              <Bar dataKey="PR_AUC" name="PR-AUC (Primary)" fill="#06b6d4" radius={[4, 4, 0, 0]} />
              <Bar dataKey="F1" name="F1 Score" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
              <Bar dataKey="Recall" name="Fraud Recall" fill="#10b981" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
