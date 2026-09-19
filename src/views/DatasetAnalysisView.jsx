import React, { useState, useEffect } from 'react';
import { Database, AlertOctagon, Award, Loader2 } from 'lucide-react';
import { fetchProjectDataset } from '../api';

export default function DatasetAnalysisView({ activeProject }) {
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!activeProject?.id) return;
    setLoading(true);
    fetchProjectDataset(activeProject.id).then((data) => {
      setReport(data);
      setLoading(false);
    });
  }, [activeProject?.id]);

  if (!activeProject) {
    return (
      <div className="p-8 max-w-7xl mx-auto">
        <div className="glass-panel p-12 rounded-xl text-center space-y-3 border-slate-800">
          <Database className="w-10 h-10 text-slate-600 mx-auto" />
          <h3 className="text-lg font-bold text-slate-200">No dataset selected</h3>
          <p className="text-xs text-slate-400">Select or start a research project to view real dataset profiling statistics.</p>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="p-8 max-w-7xl mx-auto flex items-center justify-center min-h-[400px]">
        <div className="flex items-center space-x-3 text-cyan-400 font-mono text-sm">
          <Loader2 className="w-6 h-6 animate-spin" />
          <span>Profiling dataset schema and calculating EDA stats...</span>
        </div>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="p-8 max-w-7xl mx-auto">
        <div className="glass-panel p-12 rounded-xl text-center space-y-3 border-slate-800">
          <Database className="w-10 h-10 text-amber-500 mx-auto" />
          <h3 className="text-lg font-bold text-slate-200">Not configured</h3>
          <p className="text-xs text-slate-400">Dataset analysis has not been executed yet for project &apos;{activeProject.name}&apos;.</p>
        </div>
      </div>
    );
  }

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
          <p className="text-2xl font-bold font-mono text-white">{report.rowCount?.toLocaleString() || 0}</p>
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

      {/* Class Distribution */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
        <div className="md:col-span-6 glass-panel p-6 rounded-xl space-y-4">
          <h3 className="font-bold text-sm text-slate-200 uppercase tracking-wider font-mono">
            Target Distribution ({report.taskType})
          </h3>
          <div className="space-y-3">
            {report.classDistribution && report.classDistribution.map((item) => (
              <div key={item.label} className="space-y-1">
                <div className="flex items-center justify-between text-xs font-mono">
                  <span className="text-slate-300">{item.label}</span>
                  <span className="text-cyan-400 font-bold">{item.count?.toLocaleString()} ({item.percentage}%)</span>
                </div>
                <div className="w-full bg-slate-900 h-2 rounded-full overflow-hidden">
                  <div
                    className={`h-full ${item.percentage < 5 ? 'bg-amber-400' : 'bg-cyan-500'}`}
                    style={{ width: `${Math.max(item.percentage, 2)}%` }}
                  ></div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Recommended Metrics */}
        <div className="md:col-span-6 glass-panel p-6 rounded-xl space-y-4">
          <h3 className="font-bold text-sm text-slate-200 uppercase tracking-wider font-mono flex items-center space-x-2">
            <Award className="w-4 h-4 text-emerald-400" />
            <span>Recommended Evaluation Metrics</span>
          </h3>

          <div className="space-y-3">
            {report.recommendedMetrics && report.recommendedMetrics.map((m) => (
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
        {report.detectedIssues && report.detectedIssues.length > 0 ? (
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
        ) : (
          <p className="text-xs text-slate-400 italic">No critical schema or quality issues detected.</p>
        )}
      </div>
    </div>
  );
}
