import React, { useState, useEffect } from 'react';
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
  ChevronRight,
  FileText,
  Play
} from 'lucide-react';

export default function WorkspaceView({ activeProject, setCurrentView }) {
  const [activeStepIndex, setActiveStepIndex] = useState(6); // Step 7 sandbox execution

  const pipelineSteps = [
    { id: 'step-1', name: 'Research Goal Intake', icon: Workflow, desc: 'Parsing user research prompt & constraints' },
    { id: 'step-2', name: 'Research Questions', icon: Terminal, desc: 'Generating measurable scientific questions' },
    { id: 'step-3', name: 'Literature Search', icon: BookOpen, desc: 'Semantic Scholar literature check & citation retrieval' },
    { id: 'step-4', name: 'Dataset Analysis', icon: Database, desc: 'Profiling rows, cols, target, missing data & imbalance' },
    { id: 'step-5', name: 'Baseline Generation', icon: GitFork, desc: 'Fitting initial Logistic Regression, Random Forest, XGBoost' },
    { id: 'step-6', name: 'Hypothesis Formulation', icon: Workflow, desc: 'Generating testable ML hypotheses & parameter changes' },
    { id: 'step-7', name: 'Docker Sandbox Execution', icon: ShieldCheck, desc: 'Running experiment python scripts inside isolated Docker' },
    { id: 'step-8', name: 'Evaluation & Tracking', icon: GitFork, desc: 'Logging scalar metrics, PR-AUC, F1, and execution logs' },
    { id: 'step-9', name: 'Error Analysis', icon: AlertTriangle, desc: 'Decomposing false positives, false negatives, hard slices' },
    { id: 'step-10', name: 'Statistical Testing', icon: GitFork, desc: 'Running paired t-test & cross-validation confidence bounds' },
    { id: 'step-11', name: 'Research Report', icon: FileText, desc: 'Compiling final report with mandatory AI disclosure' }
  ];

  const mockLogs = [
    "[SYSTEM] Research Session Initialized for: 'Improve fraud detection'",
    "[LITERATURE] Semantic Scholar query: 'credit card fraud imbalance PR-AUC'",
    "[LITERATURE] Found 2 relevant papers. Hydrated BibTeX citations.",
    "[DATASET] Profiled 'credit_card_fraud.csv'. 284,807 rows, 31 cols.",
    "[DATASET_ALERT] CRITICAL: Positive class imbalance (0.17%). Recommending PR-AUC over Accuracy.",
    "[BASELINES] Fitted 4 baselines. XGBoost baseline PR-AUC: 0.841.",
    "[HYPOTHESIS] Generated Hypothesis A1: 'Adjusting scale_pos_weight=577.8 will boost fraud recall.'",
    "[SANDBOX] Container 'automl-exp-a1' spawned. RAM: 4GB, CPU: 2 cores.",
    "[SANDBOX] Executing: python experiment_a1.py ...",
    "[SANDBOX] Epoch 100/250 - Loss: 0.0412 - Val PR-AUC: 0.862",
    "[EVALUATION] Exp A1 finished in 14.5s. PR-AUC increased from 0.841 to 0.862 (+2.5%).",
    "[HYPOTHESIS] Generated Hypothesis A1.1: 'Threshold tuning at 0.34 post-scale.'",
    "[SANDBOX] Container 'automl-exp-a1-1' spawned. Running threshold optimization...",
    "[SANDBOX] Success! Peak PR-AUC: 0.884, F1: 0.842.",
    "[ERROR_ANALYSIS] 38 False Positives, 42 False Negatives remaining. Feature V14 shows heavy error attribution.",
    "[STATISTICS] Paired t-test vs Baseline: p-value = 0.0034 (Statistically Significant p < 0.01).",
    "[REPORT] Final research report updated."
  ];

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
            {activeProject ? activeProject.name : 'Fraud Detection Optimization'}
          </h2>
        </div>
        <div className="flex items-center space-x-3">
          <button
            onClick={() => setCurrentView('tree')}
            className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-200 border border-slate-700 flex items-center space-x-2"
          >
            <GitFork className="w-4 h-4 text-purple-400" />
            <span>View Experiment Tree</span>
          </button>
          <button
            onClick={() => setCurrentView('report')}
            className="px-4 py-2 rounded-lg bg-cyan-500/20 hover:bg-cyan-500/30 text-xs font-semibold text-cyan-300 border border-cyan-500/40 flex items-center space-x-2"
          >
            <FileText className="w-4 h-4 text-cyan-400" />
            <span>View Final Report</span>
          </button>
        </div>
      </div>

      {/* Main split: Pipeline Stepper & Terminal Console */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: 11-Step Pipeline */}
        <div className="lg:col-span-5 glass-panel p-6 rounded-xl space-y-4">
          <h3 className="font-bold text-sm text-slate-200 uppercase tracking-wider font-mono">
            Autonomous Pipeline Handoff
          </h3>
          <div className="space-y-2">
            {pipelineSteps.map((step, idx) => {
              const Icon = step.icon;
              const isCompleted = idx < activeStepIndex;
              const isCurrent = idx === activeStepIndex;
              return (
                <div
                  key={step.id}
                  className={`p-3 rounded-lg border flex items-center space-x-3 text-xs transition-all ${
                    isCompleted
                      ? 'bg-slate-900/80 border-slate-800 text-slate-300'
                      : isCurrent
                      ? 'bg-cyan-950/60 border-cyan-500/50 text-cyan-200 shadow-md shadow-cyan-500/10'
                      : 'bg-slate-950/30 border-slate-900 text-slate-600'
                  }`}
                >
                  <div className="shrink-0">
                    {isCompleted ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    ) : isCurrent ? (
                      <Loader2 className="w-4 h-4 text-cyan-400 animate-spin" />
                    ) : (
                      <Icon className="w-4 h-4 text-slate-600" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-slate-200">{step.name}</span>
                      <span className="font-mono text-[10px] text-slate-400">Step {idx + 1}</span>
                    </div>
                    <p className="text-[11px] text-slate-400 truncate">{step.desc}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right: Live Terminal Console */}
        <div className="lg:col-span-7 glass-panel p-6 rounded-xl space-y-4 flex flex-col justify-between border-slate-800">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div className="flex items-center space-x-2">
              <Terminal className="w-4 h-4 text-cyan-400" />
              <span className="font-mono text-xs font-bold text-slate-200">
                Docker Sandbox Execution Telemetry Log
              </span>
            </div>
            <span className="text-[10px] font-mono bg-emerald-950 text-emerald-300 px-2 py-0.5 rounded border border-emerald-800">
              Container ID: 7f89a2b0c1
            </span>
          </div>

          <div className="bg-slate-950 p-4 rounded-lg border border-slate-800 font-mono text-[11px] text-slate-300 space-y-1.5 h-96 overflow-y-auto">
            {mockLogs.map((log, i) => (
              <div
                key={i}
                className={
                  log.includes('CRITICAL')
                    ? 'text-amber-400 font-semibold'
                    : log.includes('BEST') || log.includes('Success')
                    ? 'text-emerald-400 font-semibold'
                    : log.includes('SANDBOX')
                    ? 'text-cyan-300'
                    : 'text-slate-400'
                }
              >
                {log}
              </div>
            ))}
          </div>

          {/* Quick Stats bar */}
          <div className="grid grid-cols-3 gap-3 pt-2 text-center text-xs font-mono">
            <div className="bg-slate-900 p-2 rounded border border-slate-800">
              <span className="text-slate-400 block text-[10px]">CURRENT BEST</span>
              <span className="text-emerald-400 font-bold">PR-AUC 0.884</span>
            </div>
            <div className="bg-slate-900 p-2 rounded border border-slate-800">
              <span className="text-slate-400 block text-[10px]">TREE DEPTH</span>
              <span className="text-purple-400 font-bold">3 Levels</span>
            </div>
            <div className="bg-slate-900 p-2 rounded border border-slate-800">
              <span className="text-slate-400 block text-[10px]">ELAPSED TIME</span>
              <span className="text-cyan-400 font-bold">42m 18s</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
