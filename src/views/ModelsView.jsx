import React, { useState, useEffect } from 'react';
import { Cpu, CheckCircle2, Info, Loader2 } from 'lucide-react';
import { fetchProjectBaselines } from '../api';

export default function ModelsView({ activeProject }) {
  const [baselines, setBaselines] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!activeProject?.id) return;
    setLoading(true);
    fetchProjectBaselines(activeProject.id).then((data) => {
      setBaselines(data);
      setLoading(false);
    });
  }, [activeProject?.id]);

  if (!activeProject) {
    return (
      <div className="p-8 max-w-7xl mx-auto">
        <div className="glass-panel p-12 rounded-xl text-center space-y-3 border-slate-800">
          <Cpu className="w-10 h-10 text-slate-600 mx-auto" />
          <h3 className="text-lg font-bold text-slate-200 font-mono">Not configured</h3>
          <p className="text-xs text-slate-400">Select or start a research project to view baseline models.</p>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="p-8 max-w-7xl mx-auto flex items-center justify-center min-h-[400px]">
        <div className="flex items-center space-x-3 text-cyan-400 font-mono text-sm">
          <Loader2 className="w-6 h-6 animate-spin" />
          <span>Fetching benchmark baseline model metrics...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="p-8 space-y-8 max-w-7xl mx-auto">
      <div className="space-y-2">
        <div className="inline-flex items-center space-x-2 bg-cyan-500/10 border border-cyan-500/30 px-3 py-1 rounded-full text-xs font-mono text-cyan-300">
          <Cpu className="w-3.5 h-3.5" />
          <span>Automated Baseline System</span>
        </div>
        <h2 className="text-2xl font-extrabold text-white tracking-tight">
          Baseline Models & Selection Rationale
        </h2>
        <p className="text-slate-400 text-sm">
          Before deep tree search hypothesis expansion, AutoML Scientist automatically fits real baseline models and evaluates them on validation splits.
        </p>
      </div>

      {/* Grid of Baselines */}
      {baselines.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {baselines.map((model) => (
            <div key={model.id} className="glass-panel p-6 rounded-xl space-y-4 border-slate-800">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <div>
                  <span className="text-[10px] font-mono text-slate-400 uppercase tracking-wider block">{model.type}</span>
                  <h3 className="font-bold text-lg text-white">{model.name}</h3>
                </div>
                <div className="flex items-center space-x-2">
                  <span className="bg-emerald-950 text-emerald-300 text-xs px-2.5 py-1 rounded-full font-mono border border-emerald-800 flex items-center space-x-1">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>Fit in {model.trainingTime}</span>
                  </span>
                </div>
              </div>

              {/* Why selected box */}
              <div className="bg-slate-900/80 p-3 rounded-lg border border-slate-800 space-y-1">
                <span className="text-[10px] font-mono text-cyan-400 uppercase font-bold flex items-center space-x-1">
                  <Info className="w-3 h-3" />
                  <span>BASELINE SELECTION RATIONALE:</span>
                </span>
                <p className="text-xs text-slate-300 leading-relaxed font-sans">
                  {model.whySelected}
                </p>
              </div>

              {/* Metrics Breakdown */}
              <div className="grid grid-cols-3 sm:grid-cols-4 gap-2 text-center font-mono text-xs pt-2">
                {Object.entries(model.metrics || {}).map(([key, val]) => (
                  <div key={key} className="bg-slate-950 p-2 rounded border border-slate-800">
                    <span className="text-slate-400 text-[9px] block uppercase">{key}</span>
                    <span className="text-cyan-300 font-bold">{val}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="glass-panel p-8 rounded-xl text-center space-y-2">
          <p className="text-xs text-slate-400 font-mono">No baseline models trained yet for project '{activeProject.name}'.</p>
        </div>
      )}
    </div>
  );
}
