import React, { useState, useEffect } from 'react';
import { AlertTriangle, HelpCircle, Loader2 } from 'lucide-react';
import { fetchProjectErrorAnalysis } from '../api';

export default function ErrorAnalysisView({ activeProject }) {
  const [err, setErr] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!activeProject?.id) return;
    setLoading(true);
    fetchProjectErrorAnalysis(activeProject.id).then((data) => {
      setErr(data);
      setLoading(false);
    });
  }, [activeProject?.id]);

  if (!activeProject) {
    return (
      <div className="p-8 max-w-7xl mx-auto">
        <div className="glass-panel p-12 rounded-xl text-center space-y-3 border-slate-800">
          <AlertTriangle className="w-10 h-10 text-slate-600 mx-auto" />
          <h3 className="text-lg font-bold text-slate-200 font-mono">Not configured</h3>
          <p className="text-xs text-slate-400">Select or start a research project to view real error analysis diagnostics.</p>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="p-8 max-w-7xl mx-auto flex items-center justify-center min-h-[400px]">
        <div className="flex items-center space-x-3 text-amber-400 font-mono text-sm">
          <Loader2 className="w-6 h-6 animate-spin" />
          <span>Performing error diagnostics and slice analysis...</span>
        </div>
      </div>
    );
  }

  if (!err) {
    return (
      <div className="p-8 max-w-7xl mx-auto">
        <div className="glass-panel p-12 rounded-xl text-center space-y-3 border-slate-800">
          <AlertTriangle className="w-10 h-10 text-amber-500 mx-auto" />
          <h3 className="text-lg font-bold text-slate-200 font-mono">Not configured</h3>
          <p className="text-xs text-slate-400">Error analysis has not been executed yet for project '{activeProject.name}'.</p>
        </div>
      </div>
    );
  }

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
          <span className="text-xs text-slate-400 font-medium">False Positives (Class 0 predicted as Class 1)</span>
          <p className="text-3xl font-bold font-mono text-amber-400">{err.falsePositivesCount}</p>
        </div>
        <div className="glass-panel p-5 rounded-xl border-red-500/20 space-y-1">
          <span className="text-xs text-slate-400 font-medium">False Negatives (Missed Class 1 Targets)</span>
          <p className="text-3xl font-bold font-mono text-red-400">{err.falseNegativesCount}</p>
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
      {err.sliceAnalysis && err.sliceAnalysis.length > 0 && (
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
                    Accuracy: {slice.recall}
                  </span>
                </div>
                <p className="text-xs text-slate-400">{slice.note}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
