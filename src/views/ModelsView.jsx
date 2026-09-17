import React from 'react';
import { Cpu, CheckCircle2, Clock, Zap, Info } from 'lucide-react';
import { INITIAL_BASELINES } from '../mockData';

export default function ModelsView() {
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
          Before deep tree search hypothesis expansion, AutoML Scientist automatically fits standard baseline models and explains WHY each candidate model was selected for the problem domain.
        </p>
      </div>

      {/* Grid of Baselines */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {INITIAL_BASELINES.map((model) => (
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
                <span>WHY SELECTED BY BASELINE AGENT:</span>
              </span>
              <p className="text-xs text-slate-300 leading-relaxed font-sans">
                {model.whySelected}
              </p>
            </div>

            {/* Metrics Breakdown */}
            <div className="grid grid-cols-3 sm:grid-cols-5 gap-2 text-center font-mono text-xs pt-2">
              <div className="bg-slate-950 p-2 rounded border border-slate-800">
                <span className="text-slate-400 text-[9px] block">PR-AUC</span>
                <span className="text-emerald-400 font-bold">{model.metrics.pr_auc}</span>
              </div>
              <div className="bg-slate-950 p-2 rounded border border-slate-800">
                <span className="text-slate-400 text-[9px] block">F1 SCORE</span>
                <span className="text-cyan-300 font-bold">{model.metrics.f1}</span>
              </div>
              <div className="bg-slate-950 p-2 rounded border border-slate-800">
                <span className="text-slate-400 text-[9px] block">RECALL</span>
                <span className="text-purple-300 font-bold">{model.metrics.recall}</span>
              </div>
              <div className="bg-slate-950 p-2 rounded border border-slate-800">
                <span className="text-slate-400 text-[9px] block">PRECISION</span>
                <span className="text-slate-200 font-bold">{model.metrics.precision}</span>
              </div>
              <div className="bg-slate-950 p-2 rounded border border-slate-800">
                <span className="text-slate-400 text-[9px] block">ROC-AUC</span>
                <span className="text-slate-300 font-bold">{model.metrics.roc_auc}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
