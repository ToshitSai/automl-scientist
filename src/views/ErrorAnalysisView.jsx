import React from 'react';
import { AlertTriangle, AlertCircle, HelpCircle, Layers, Cpu, CheckCircle2 } from 'lucide-react';
import { INITIAL_ERROR_ANALYSIS } from '../mockData';

export default function ErrorAnalysisView() {
  const err = INITIAL_ERROR_ANALYSIS;

  return (
    <div className="p-8 space-y-8 max-w-7xl mx-auto">
      <div className="space-y-2">
        <div className="inline-flex items-center space-x-2 bg-amber-500/10 border border-amber-500/30 px-3 py-1 rounded-full text-xs font-mono text-amber-300">
          <AlertTriangle className="w-3.5 h-3.5" />
          <span>Post-Experiment Error Analysis Engine</span>
        </div>
        <h2 className="text-2xl font-extrabold text-white tracking-tight">
          Failure Mode & Error Analysis Breakdown
        </h2>
        <p className="text-slate-400 text-sm">
          After each experiment run, AutoML Scientist performs systematic error analysis to discover why the model failed and guide the next hypothesis iteration.
        </p>
      </div>

      {/* Top Counts */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
        <div className="glass-panel p-5 rounded-xl border-amber-500/20 space-y-1">
          <span className="text-xs text-slate-400 font-medium">False Positives (Legitimate flagged as Fraud)</span>
          <p className="text-3xl font-bold font-mono text-amber-400">{err.falsePositivesCount}</p>
          <p className="text-[11px] text-slate-400">Triggered on high-amount purchase anomalies (V4 variance)</p>
        </div>
        <div className="glass-panel p-5 rounded-xl border-red-500/20 space-y-1">
          <span className="text-xs text-slate-400 font-medium">False Negatives (Missed Fraud Cases)</span>
          <p className="text-3xl font-bold font-mono text-red-400">{err.falseNegativesCount}</p>
          <p className="text-[11px] text-slate-400">Concentrated in micro-transaction stealth fraud (&lt; $10.00)</p>
        </div>
      </div>

      {/* Why Did Model Fail? Diagnosis Box */}
      <div className="glass-panel p-6 rounded-xl border border-amber-500/40 space-y-3 bg-amber-950/20">
        <div className="flex items-center space-x-2 text-amber-400 font-mono text-xs font-bold uppercase">
          <HelpCircle className="w-4 h-4" />
          <span>&quot;Why Did The Model Fail?&quot; — Autonomous Diagnosis Report</span>
        </div>
        <p className="text-sm text-amber-100/90 leading-relaxed font-sans">
          {err.failureDiagnosis}
        </p>
      </div>

      {/* Slice-Level Analysis */}
      <div className="glass-panel p-6 rounded-xl space-y-4">
        <h3 className="font-bold text-sm text-slate-200 uppercase tracking-wider font-mono">
          Sub-Population & Slice-Level Performance Breakdown
        </h3>
        <div className="space-y-3">
          {err.sliceAnalysis.map((slice) => (
            <div key={slice.slice} className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="font-bold text-slate-200">{slice.slice}</span>
                <span className="font-mono text-emerald-400 font-bold bg-slate-950 px-2.5 py-1 rounded border border-slate-800">
                  Recall: {slice.recall} ({slice.fraudCount} cases)
                </span>
              </div>
              <p className="text-xs text-slate-400">{slice.note}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
