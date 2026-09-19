import React, { useState, useEffect } from 'react';
import { BarChart3, Loader2 } from 'lucide-react';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, Legend } from 'recharts';
import { fetchProjectTree, fetchProjectBaselines } from '../api';

export default function ResultsView({ activeProject }) {
  const [chartData, setChartData] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!activeProject?.id) return;
    setLoading(true);
    Promise.all([
      fetchProjectBaselines(activeProject.id),
      fetchProjectTree(activeProject.id)
    ]).then(([baselines, nodes]) => {
      const data = [];
      baselines.forEach((b) => {
        data.push({
          name: b.name,
          PrimaryMetric: listFirstMetricVal(b.metrics),
          Status: b.status
        });
      });
      nodes.forEach((n) => {
        data.push({
          name: n.title,
          PrimaryMetric: n.metricValue,
          Status: n.status
        });
      });
      setChartData(data);
      setLoading(false);
    });
  }, [activeProject?.id]);

  const listFirstMetricVal = (metrics) => {
    if (!metrics) return 0;
    const keys = Object.keys(metrics);
    return keys.length > 0 ? metrics[keys[0]] : 0;
  };

  if (!activeProject) {
    return (
      <div className="p-8 max-w-7xl mx-auto">
        <div className="glass-panel p-12 rounded-xl text-center space-y-3 border-slate-800">
          <BarChart3 className="w-10 h-10 text-slate-600 mx-auto" />
          <h3 className="text-lg font-bold text-slate-200 font-mono">Not configured</h3>
          <p className="text-xs text-slate-400">Select or start a research project to view evaluation results.</p>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="p-8 max-w-7xl mx-auto flex items-center justify-center min-h-[400px]">
        <div className="flex items-center space-x-3 text-cyan-400 font-mono text-sm">
          <Loader2 className="w-6 h-6 animate-spin" />
          <span>Compiling comparative evaluation metrics...</span>
        </div>
      </div>
    );
  }

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
          Track progression from baseline benchmarks to hypotheses nodes for &apos;{activeProject.name}&apos;.
        </p>
      </div>

      {/* Main Chart Card */}
      <div className="glass-panel p-6 rounded-xl space-y-6">
        <div className="flex items-center justify-between">
          <h3 className="font-bold text-sm text-slate-200 uppercase tracking-wider font-mono">
            Validation Metric Score Progression
          </h3>
          <span className="text-xs font-mono text-emerald-400 bg-emerald-950 px-3 py-1 rounded border border-emerald-800">
            Best Metric: {activeProject.bestMetric}
          </span>
        </div>

        {chartData.length > 0 ? (
          <div className="h-80 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 20, right: 30, left: 0, bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="name" stroke="#94a3b8" tick={{ fontSize: 11 }} />
                <YAxis domain={[0, 1.0]} stroke="#94a3b8" tick={{ fontSize: 11 }} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px', fontSize: '12px' }}
                />
                <Legend wrapperStyle={{ fontSize: '12px', paddingTop: '10px' }} />
                <Bar dataKey="PrimaryMetric" name="Validation Metric" fill="#06b6d4" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="p-8 text-center text-xs text-slate-400 font-mono">
            No result metrics logged yet for this project.
          </div>
        )}
      </div>
    </div>
  );
}
