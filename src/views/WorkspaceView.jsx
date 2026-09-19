import React from 'react';
import { 
  Workflow, 
  CheckCircle2, 
  Loader2, 
  Terminal, 
  GitFork, 
  Database, 
  BookOpen, 
  ShieldCheck, 
  AlertTriangle, 
  FileText
} from 'lucide-react';

export default function WorkspaceView({ activeProject, setCurrentView }) {
  const stageStates = activeProject?.stageStates || {};

  const pipelineSteps = [
    { id: 'step-1', stageKey: 'research_question', name: 'Research Goal Intake', icon: Workflow, desc: 'Parsing research objective and research question' },
    { id: 'step-2', stageKey: 'literature_search', name: 'Literature Search', icon: BookOpen, desc: 'Searching Semantic Scholar API for papers' },
    { id: 'step-3', stageKey: 'dataset_eda', name: 'Dataset Analysis', icon: Database, desc: 'Profiling rows, cols, target, missing data & imbalance' },
    { id: 'step-4', stageKey: 'baseline_training', name: 'Baseline Generation', icon: GitFork, desc: 'Fitting initial Logistic, Random Forest, XGBoost baselines' },
    { id: 'step-5', stageKey: 'hypothesis_generation', name: 'Hypothesis Formulation', icon: Workflow, desc: 'Generating testable ML hypotheses & experiment code' },
    { id: 'step-6', stageKey: 'sandboxed_execution', name: 'Sandboxed Experiment Run', icon: ShieldCheck, desc: 'Running experiments in isolated container/subprocess' },
    { id: 'step-7', stageKey: 'error_diagnostics', name: 'Error Diagnostics', icon: AlertTriangle, desc: 'Analyzing false positives, false negatives, slice errors' },
    { id: 'step-8', stageKey: 'research_report', name: 'Research Report', icon: FileText, desc: 'Compiling final markdown research paper' }
  ];

  const agentLogs = activeProject?.agentLogs || [];

  return (
    <div className="p-8 space-y-8 max-w-7xl mx-auto">
      {/* Header section */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2 text-xs font-mono text-cyan-400 mb-1">
            <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping"></span>
            <span>LIVE RESEARCH WORKSPACE ENGINE</span>
          </div>
          <h2 className="text-2xl font-extrabold text-white tracking-tight">
            {activeProject ? activeProject.name : 'No Active Research Project'}
          </h2>
        </div>
        <div className="flex items-center space-x-3">
          <button
            onClick={() => setCurrentView('tree')}
            className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-200 border border-slate-700 flex items-center space-x-2 cursor-pointer"
          >
            <GitFork className="w-4 h-4 text-purple-400" />
            <span>View Experiment Tree</span>
          </button>
          <button
            onClick={() => setCurrentView('report')}
            className="px-4 py-2 rounded-lg bg-cyan-500/20 hover:bg-cyan-500/30 text-xs font-semibold text-cyan-300 border border-cyan-500/40 flex items-center space-x-2 cursor-pointer"
          >
            <FileText className="w-4 h-4 text-cyan-400" />
            <span>View Final Report</span>
          </button>
        </div>
      </div>

      {/* Main split: Pipeline Stepper & Terminal Console */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Real Pipeline Agents */}
        <div className="lg:col-span-5 glass-panel p-6 rounded-xl space-y-4">
          <h3 className="font-bold text-sm text-slate-200 uppercase tracking-wider font-mono">
            Autonomous Pipeline Handoff
          </h3>
          <div className="space-y-2">
            {pipelineSteps.map((step, idx) => {
              const Icon = step.icon;
              const st = stageStates[step.stageKey] || 'NOT_STARTED';
              const isDone = st === 'COMPLETED';
              const isCurrent = st === 'RUNNING';
              const isUnconfigured = st === 'NOT_CONFIGURED';
              const isFailed = st === 'FAILED';
              
              return (
                <div
                  key={step.id}
                  className={`p-3 rounded-lg border flex items-center space-x-3 text-xs transition-all ${
                    isDone
                      ? 'bg-slate-900/80 border-slate-800 text-slate-300'
                      : isCurrent
                      ? 'bg-cyan-950/60 border-cyan-500/50 text-cyan-200 shadow-md shadow-cyan-500/10'
                      : isUnconfigured
                      ? 'bg-slate-950/40 border-slate-800/60 text-slate-500'
                      : isFailed
                      ? 'bg-rose-950/30 border-rose-500/30 text-rose-300'
                      : 'bg-slate-950/30 border-slate-900 text-slate-600'
                  }`}
                >
                  <div className="shrink-0">
                    {isDone ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    ) : isCurrent ? (
                      <Loader2 className="w-4 h-4 text-cyan-400 animate-spin" />
                    ) : isFailed ? (
                      <AlertTriangle className="w-4 h-4 text-rose-400" />
                    ) : (
                      <Icon className="w-4 h-4 text-slate-600" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-slate-200">{step.name}</span>
                      <span className="font-mono text-[10px] text-slate-400">
                        {isUnconfigured ? 'UNCONFIGURED' : `Step ${idx + 1}`}
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-400 truncate">{step.desc}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right: Real Terminal Console */}
        <div className="lg:col-span-7 glass-panel p-6 rounded-xl space-y-4 flex flex-col justify-between border-slate-800">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div className="flex items-center space-x-2">
              <Terminal className="w-4 h-4 text-cyan-400" />
              <span className="font-mono text-xs font-bold text-slate-200">
                Agent Telemetry Log
              </span>
            </div>
            <span className="text-[10px] font-mono bg-emerald-950 text-emerald-300 px-2 py-0.5 rounded border border-emerald-800">
              Project ID: {activeProject?.id || 'N/A'}
            </span>
          </div>

          <div className="bg-slate-950 p-4 rounded-lg border border-slate-800 font-mono text-[11px] text-slate-300 space-y-1.5 h-96 overflow-y-auto">
            {agentLogs.length > 0 ? (
              agentLogs.map((log, i) => (
                <div key={i} className="flex space-x-2">
                  <span className="text-slate-500 font-mono">[{log.agent}]</span>
                  <span className={log.status === 'FAILED' ? 'text-rose-400' : 'text-slate-300'}>
                    {log.message}
                  </span>
                </div>
              ))
            ) : (
              <div className="text-slate-500 italic">No agent logs recorded yet for this project.</div>
            )}
          </div>

          {/* Quick Stats bar */}
          <div className="grid grid-cols-3 gap-3 pt-2 text-center text-xs font-mono">
            <div className="bg-slate-900 p-2 rounded border border-slate-800">
              <span className="text-slate-400 block text-[10px]">BEST METRIC</span>
              <span className="text-emerald-400 font-bold truncate block">{activeProject?.bestMetric || 'N/A'}</span>
            </div>
            <div className="bg-slate-900 p-2 rounded border border-slate-800">
              <span className="text-slate-400 block text-[10px]">EXPERIMENTS</span>
              <span className="text-purple-400 font-bold">{activeProject?.experimentsCount || 0}</span>
            </div>
            <div className="bg-slate-900 p-2 rounded border border-slate-800">
              <span className="text-slate-400 block text-[10px]">STATUS</span>
              <span className="text-cyan-400 font-bold">{activeProject?.status || 'IDLE'}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
