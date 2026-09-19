import React, { useState, useEffect } from 'react';
import { FlaskConical, Search, ShieldCheck, Loader2 } from 'lucide-react';
import { fetchProjectTree } from '../api';

export default function ExperimentsView({ activeProject }) {
  const [search, setSearch] = useState('');
  const [treeNodes, setTreeNodes] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!activeProject?.id) return;
    setLoading(true);
    fetchProjectTree(activeProject.id).then((data) => {
      setTreeNodes(data);
      setLoading(false);
    });
  }, [activeProject?.id]);

  if (!activeProject) {
    return (
      <div className="p-8 max-w-7xl mx-auto">
        <div className="glass-panel p-12 rounded-xl text-center space-y-3 border-slate-800">
          <FlaskConical className="w-10 h-10 text-slate-600 mx-auto" />
          <h3 className="text-lg font-bold text-slate-200 font-mono">Not configured</h3>
          <p className="text-xs text-slate-400">Select or start a research project to view experiment records.</p>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="p-8 max-w-7xl mx-auto flex items-center justify-center min-h-[400px]">
        <div className="flex items-center space-x-3 text-cyan-400 font-mono text-sm">
          <Loader2 className="w-6 h-6 animate-spin" />
          <span>Fetching experiment history...</span>
        </div>
      </div>
    );
  }

  const filtered = treeNodes.filter((e) =>
    (e.title || '').toLowerCase().includes(search.toLowerCase()) ||
    (e.id || '').toLowerCase().includes(search.toLowerCase())
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
                <th className="p-4">Hypothesis</th>
                <th className="p-4">Primary Metric</th>
                <th className="p-4">Status</th>
                <th className="p-4">Runtime</th>
                <th className="p-4">Sandbox Mode</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/80">
              {filtered.length > 0 ? (
                filtered.map((exp) => (
                  <tr key={exp.id} className="hover:bg-slate-800/40 transition-colors">
                    <td className="p-4 font-mono font-bold text-cyan-400">{exp.id}</td>
                    <td className="p-4 font-medium text-slate-200">{exp.title}</td>
                    <td className="p-4 font-mono text-slate-400 truncate max-w-xs">{exp.hypothesis}</td>
                    <td className="p-4 font-mono font-bold text-emerald-400">{exp.metricName}: {exp.metricValue}</td>
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
                    <td className="p-4 font-mono text-slate-400">{exp.executionTime}</td>
                    <td className="p-4 flex items-center space-x-1.5 text-emerald-400">
                      <ShieldCheck className="w-3.5 h-3.5" />
                      <span className="font-mono text-[11px]">Process Sandbox</span>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={7} className="p-6 text-center text-slate-500 italic">
                    No matching experiment records found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
