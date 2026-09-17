import React, { useState } from 'react';
import { FlaskConical, Search, Filter, ShieldCheck, CheckCircle2, ArrowUpDown } from 'lucide-react';
import { INITIAL_TREE_NODES } from '../mockData';

export default function ExperimentsView() {
  const [search, setSearch] = useState('');

  const experiments = [
    { id: 'EXP-001', name: 'Baseline XGBoost Raw', model: 'XGBoost', metric: 'PR-AUC: 0.841', status: 'SUCCESS', runtime: '12.1s', sandbox: 'Docker Isolated' },
    { id: 'EXP-002', name: 'Logistic Regression Scale', model: 'LogisticRegression', metric: 'PR-AUC: 0.712', status: 'SUCCESS', runtime: '2.4s', sandbox: 'Docker Isolated' },
    { id: 'EXP-003', name: 'Random Forest 200 Trees', model: 'RandomForest', metric: 'PR-AUC: 0.825', status: 'SUCCESS', runtime: '18.6s', sandbox: 'Docker Isolated' },
    { id: 'EXP-004', name: 'Class Weighting (scale_pos_weight)', model: 'XGBoost', metric: 'PR-AUC: 0.862', status: 'IMPROVED', runtime: '14.5s', sandbox: 'Docker Isolated' },
    { id: 'EXP-005', name: 'Threshold Optimization (0.34)', model: 'XGBoost', metric: 'PR-AUC: 0.884', status: 'BEST', runtime: '21.0s', sandbox: 'Docker Isolated' },
    { id: 'EXP-006', name: 'SMOTE Oversampling (k=5)', model: 'XGBoost + SMOTE', metric: 'PR-AUC: 0.849', status: 'PLATEAUED', runtime: '38.2s', sandbox: 'Docker Isolated' },
    { id: 'EXP-007', name: 'Isolation Forest Meta Feature', model: 'XGBoost + IsoForest', metric: 'PR-AUC: 0.858', status: 'SUCCESS', runtime: '28.7s', sandbox: 'Docker Isolated' },
    { id: 'EXP-008', name: 'Neural Net 3-Layer MLP', model: 'PyTorch MLP', metric: 'PR-AUC: 0.793', status: 'SUCCESS', runtime: '45.2s', sandbox: 'Docker Isolated' }
  ];

  const filtered = experiments.filter((e) =>
    e.name.toLowerCase().includes(search.toLowerCase()) ||
    e.model.toLowerCase().includes(search.toLowerCase()) ||
    e.id.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="p-8 space-y-8 max-w-7xl mx-auto">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div className="space-y-1">
          <div className="inline-flex items-center space-x-2 bg-cyan-500/10 border border-cyan-500/30 px-3 py-1 rounded-full text-xs font-mono text-cyan-300">
            <FlaskConical className="w-3.5 h-3.5" />
            <span>Experiment History Registry</span>
          </div>
          <h2 className="text-2xl font-extrabold text-white tracking-tight">
            Executed Experiments Tracking Table
          </h2>
        </div>

        <div className="flex items-center space-x-3 w-full sm:w-auto">
          <div className="relative flex-1 sm:w-64">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
            <input
              type="text"
              placeholder="Search experiments..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg pl-9 pr-4 py-2 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
            />
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="glass-panel rounded-xl overflow-hidden border border-slate-800">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-300">
            <thead className="bg-slate-900/90 text-slate-400 uppercase font-mono text-[10px] tracking-wider border-b border-slate-800">
              <tr>
                <th className="p-4">Exp ID</th>
                <th className="p-4">Experiment Title</th>
                <th className="p-4">Model Architecture</th>
                <th className="p-4">Primary Metric</th>
                <th className="p-4">Status</th>
                <th className="p-4">Runtime</th>
                <th className="p-4">Sandbox Mode</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/80">
              {filtered.map((exp) => (
                <tr key={exp.id} className="hover:bg-slate-800/40 transition-colors">
                  <td className="p-4 font-mono font-bold text-cyan-400">{exp.id}</td>
                  <td className="p-4 font-medium text-slate-200">{exp.name}</td>
                  <td className="p-4 font-mono text-slate-300">{exp.model}</td>
                  <td className="p-4 font-mono font-bold text-emerald-400">{exp.metric}</td>
                  <td className="p-4">
                    <span
                      className={`px-2.5 py-1 rounded-full text-[10px] font-mono font-bold border ${
                        exp.status === 'BEST'
                          ? 'bg-emerald-950 text-emerald-300 border-emerald-800'
                          : exp.status === 'IMPROVED'
                          ? 'bg-cyan-950 text-cyan-300 border-cyan-800'
                          : exp.status === 'PLATEAUED'
                          ? 'bg-amber-950 text-amber-300 border-amber-800'
                          : 'bg-slate-900 text-slate-300 border-slate-700'
                      }`}
                    >
                      {exp.status}
                    </span>
                  </td>
                  <td className="p-4 font-mono text-slate-400">{exp.runtime}</td>
                  <td className="p-4 flex items-center space-x-1.5 text-emerald-400">
                    <ShieldCheck className="w-3.5 h-3.5" />
                    <span className="font-mono text-[11px]">{exp.sandbox}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
