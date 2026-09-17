import React from 'react';
import { Database, AlertOctagon, AlertTriangle, CheckCircle2, FileSpreadsheet, Info, Award } from 'lucide-react';
import { INITIAL_DATASET_REPORT } from '../mockData';

export default function DatasetAnalysisView() {
  const report = INITIAL_DATASET_REPORT;

  return (
    <div className="p-8 space-y-8 max-w-7xl mx-auto">
      <div className="space-y-2">
        <div className="inline-flex items-center space-x-2 bg-cyan-500/10 border border-cyan-500/30 px-3 py-1 rounded-full text-xs font-mono text-cyan-300">
          <Database className="w-3.5 h-3.5" />
          <span>Automated Dataset Profiler & Report</span>
        </div>
        <h2 className="text-2xl font-extrabold text-white tracking-tight">
          Dataset Analysis: {report.filename}
        </h2>
        <p className="text-slate-400 text-sm">
          AutoML Scientist automatically profiles tabular schema, class imbalance ratio, target candidates, data leakage risks, and metric suitability.
        </p>
      </div>

      {/* Top Stat Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-5">
        <div className="glass-panel p-5 rounded-xl space-y-1">
          <span className="text-xs text-slate-400 font-medium">Total Rows</span>
          <p className="text-2xl font-bold font-mono text-white">{report.rowCount.toLocaleString()}</p>
        </div>
        <div className="glass-panel p-5 rounded-xl space-y-1">
          <span className="text-xs text-slate-400 font-medium">Total Features</span>
          <p className="text-2xl font-bold font-mono text-white">{report.columnCount} Cols</p>
        </div>
        <div className="glass-panel p-5 rounded-xl space-y-1">
          <span className="text-xs text-slate-400 font-medium">Target Candidate</span>
          <p className="text-2xl font-bold font-mono text-cyan-400">&apos;{report.targetCandidate}&apos;</p>
        </div>
        <div className="glass-panel p-5 rounded-xl space-y-1">
          <span className="text-xs text-slate-400 font-medium">File Size</span>
          <p className="text-2xl font-bold font-mono text-slate-300">{report.fileSize}</p>
        </div>
      </div>

      {/* Class Distribution & Imbalance Warning */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
        <div className="md:col-span-6 glass-panel p-6 rounded-xl space-y-4">
          <h3 className="font-bold text-sm text-slate-200 uppercase tracking-wider font-mono">
            Class Target Distribution
          </h3>
          <div className="space-y-3">
            {report.classDistribution.map((item) => (
              <div key={item.label} className="space-y-1">
                <div className="flex items-center justify-between text-xs font-mono">
                  <span className="text-slate-300">{item.label}</span>
                  <span className="text-cyan-400 font-bold">{item.count.toLocaleString()} ({item.percentage}%)</span>
                </div>
                <div className="w-full bg-slate-900 h-2 rounded-full overflow-hidden">
                  <div
                    className={`h-full ${item.percentage < 1 ? 'bg-amber-400' : 'bg-cyan-500'}`}
                    style={{ width: `${Math.max(item.percentage, 1.5)}%` }}
                  ></div>
                </div>
              </div>
            ))}
          </div>

          <div className="p-4 rounded-xl bg-amber-950/40 border border-amber-500/40 flex items-start space-x-3 text-xs">
            <AlertOctagon className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
            <div>
              <h4 className="font-bold text-amber-300">Extreme Class Imbalance Alert</h4>
              <p className="text-amber-200/80 leading-relaxed mt-1">
                Positive fraud class constitutes only 0.17% of total dataset. Standard accuracy yields 99.83% baseline without predicting any fraud. Metrics must be set to PR-AUC and Recall@Precision.
              </p>
            </div>
          </div>
        </div>

        {/* Recommended Metrics */}
        <div className="md:col-span-6 glass-panel p-6 rounded-xl space-y-4">
          <h3 className="font-bold text-sm text-slate-200 uppercase tracking-wider font-mono flex items-center space-x-2">
            <Award className="w-4 h-4 text-emerald-400" />
            <span>Recommended Evaluation Metrics</span>
          </h3>

          <div className="space-y-3">
            {report.recommendedMetrics.map((m) => (
              <div key={m.name} className="p-3 rounded-lg bg-slate-900/80 border border-slate-800 space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-bold text-slate-200">{m.name}</span>
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-cyan-950 text-cyan-300 border border-cyan-800">
                    {m.importance}
                  </span>
                </div>
                <p className="text-[11px] text-slate-400">{m.reason}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Detected Data Quality Issues */}
      <div className="glass-panel p-6 rounded-xl space-y-4">
        <h3 className="font-bold text-sm text-slate-200 uppercase tracking-wider font-mono">
          Detected Data Quality & Profiling Issues
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {report.detectedIssues.map((issue) => (
            <div key={issue.title} className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-2">
              <span className={`text-[10px] font-mono px-2 py-0.5 rounded font-bold ${
                issue.severity === 'CRITICAL' ? 'bg-red-950 text-red-300 border border-red-800' :
                issue.severity === 'MEDIUM' ? 'bg-amber-950 text-amber-300 border border-amber-800' :
                'bg-slate-800 text-slate-300'
              }`}>
                {issue.severity}
              </span>
              <h4 className="font-bold text-sm text-slate-100">{issue.title}</h4>
              <p className="text-xs text-slate-400 leading-relaxed">{issue.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
