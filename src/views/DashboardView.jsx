import React from 'react';
import { 
  PlusCircle, 
  FlaskConical, 
  GitFork, 
  TrendingUp, 
  ShieldCheck, 
  Sparkles, 
  ChevronRight,
  Database,
  BarChart2
} from 'lucide-react';

export default function DashboardView({ setCurrentView, projects, activeProject }) {
  return (
    <div className="p-8 space-y-8 max-w-7xl mx-auto">
      {/* Hero Welcome Banner */}
      <div className="relative overflow-hidden rounded-2xl glass-panel p-8 border border-cyan-500/20 bg-gradient-to-r from-slate-900 via-slate-900/90 to-cyan-950/40">
        <div className="scanline-effect"></div>
        <div className="relative z-10 flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
          <div className="space-y-2 max-w-2xl">
            <div className="inline-flex items-center space-x-2 bg-cyan-500/10 border border-cyan-500/30 px-3 py-1 rounded-full text-xs font-mono text-cyan-300">
              <Sparkles className="w-3.5 h-3.5" />
              <span>Autonomous ML Research Engine</span>
            </div>
            <h2 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white">
              Welcome to AutoML Scientist
            </h2>
            <p className="text-slate-400 text-sm leading-relaxed">
              Define your machine learning objective. AutoML Scientist autonomously analyzes your dataset, discovers literature, formulates hypotheses, executes sandboxed experiments, and generates comprehensive research reports.
            </p>
          </div>
          <button
            onClick={() => setCurrentView('new_research')}
            className="flex items-center space-x-2 bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white px-5 py-3 rounded-xl font-semibold text-sm shadow-lg shadow-cyan-500/25 transition-all transform hover:-translate-y-0.5 cursor-pointer"
          >
            <PlusCircle className="w-4 h-4" />
            <span>Start New Research</span>
          </button>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        <div className="glass-panel p-5 rounded-xl space-y-2 border-slate-800/80">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-medium uppercase tracking-wider">Research Projects</span>
            <FlaskConical className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="text-2xl font-bold text-white">
            {projects.length}
          </div>
          <p className="text-xs text-slate-400 flex items-center space-x-1">
            <span className="text-emerald-400 font-semibold">{projects.filter(p => p.status === 'IN_PROGRESS').length} active</span>
            <span>in system</span>
          </p>
        </div>

        <div className="glass-panel p-5 rounded-xl space-y-2 border-slate-800/80">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-medium uppercase tracking-wider">Tree Experiments</span>
            <GitFork className="w-4 h-4 text-purple-400" />
          </div>
          <div className="text-2xl font-bold text-white">
            {activeProject ? activeProject.experimentsCount : 0}
          </div>
          <p className="text-xs text-slate-400 flex items-center space-x-1">
            <span>in active project</span>
          </p>
        </div>

        <div className="glass-panel p-5 rounded-xl space-y-2 border-slate-800/80">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-medium uppercase tracking-wider">Best Metric Score</span>
            <TrendingUp className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-xl font-bold text-emerald-400 truncate">
            {activeProject ? activeProject.bestMetric : 'Not calculated'}
          </div>
          <p className="text-xs text-slate-400 flex items-center space-x-1">
            <span>validation score</span>
          </p>
        </div>

        <div className="glass-panel p-5 rounded-xl space-y-2 border-slate-800/80">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-medium uppercase tracking-wider">Sandbox Engine</span>
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-sm font-bold text-white flex items-center space-x-2">
            <span>Active</span>
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse"></span>
          </div>
          <p className="text-xs text-slate-400 truncate">
            Process Sandbox Isolation
          </p>
        </div>
      </div>

      {/* Active Research Objective Card */}
      {activeProject ? (
        <div className="glass-panel p-6 rounded-xl border border-cyan-500/30 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <span className="w-3 h-3 rounded-full bg-cyan-400 animate-pulse"></span>
              <h3 className="text-lg font-bold text-white">{activeProject.name}</h3>
              <span className="bg-cyan-950 text-cyan-300 text-xs px-2.5 py-0.5 rounded-full border border-cyan-800 font-mono">
                {activeProject.status}
              </span>
            </div>
            <button
              onClick={() => setCurrentView('workspace')}
              className="text-xs text-cyan-400 hover:text-cyan-300 font-semibold flex items-center space-x-1 cursor-pointer"
            >
              <span>View Live Workspace</span>
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>

          <p className="text-sm text-slate-300 bg-slate-900/60 p-3 rounded-lg border border-slate-800 font-mono">
            Objective: &quot;{activeProject.objective}&quot;
          </p>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
            <div>
              <span className="text-slate-400 block">Dataset</span>
              <span className="text-slate-200 font-medium">{activeProject.datasetName}</span>
            </div>
            <div>
              <span className="text-slate-400 block">Best Model</span>
              <span className="text-cyan-300 font-medium">{activeProject.bestModel}</span>
            </div>
            <div>
              <span className="text-slate-400 block">LLM Engine</span>
              <span className="text-slate-200 font-medium">{activeProject.llmProvider}</span>
            </div>
            <div>
              <span className="text-slate-400 block">Compute Used</span>
              <span className="text-amber-400 font-mono font-medium">{activeProject.computeUsed}</span>
            </div>
          </div>
        </div>
      ) : (
        <div className="glass-panel p-8 rounded-xl border border-slate-800 text-center space-y-4">
          <p className="text-sm text-slate-400 font-mono">Not configured / No research project selected</p>
          <button
            onClick={() => setCurrentView('new_research')}
            className="px-4 py-2 bg-cyan-500 hover:bg-cyan-400 text-white font-bold text-xs rounded-lg cursor-pointer"
          >
            Create Your First Research Objective
          </button>
        </div>
      )}

      {/* Quick Access Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div 
          onClick={() => setCurrentView('dataset_analysis')}
          className="glass-panel-interactive p-6 rounded-xl cursor-pointer space-y-3"
        >
          <div className="w-10 h-10 rounded-lg bg-cyan-500/10 text-cyan-400 flex items-center justify-center">
            <Database className="w-5 h-5" />
          </div>
          <h4 className="text-base font-bold text-white">Dataset Analysis Report</h4>
          <p className="text-xs text-slate-400">
            View real statistical profiling results: row counts, missing values, class distributions, and recommended evaluation metrics.
          </p>
        </div>

        <div 
          onClick={() => setCurrentView('tree')}
          className="glass-panel-interactive p-6 rounded-xl cursor-pointer space-y-3"
        >
          <div className="w-10 h-10 rounded-lg bg-purple-500/10 text-purple-400 flex items-center justify-center">
            <GitFork className="w-5 h-5" />
          </div>
          <h4 className="text-base font-bold text-white">Directed Experiment Tree</h4>
          <p className="text-xs text-slate-400">
            Inspect the complete hypothesis search tree. Trace parent-child experiment nodes, stdout logs, and hyperparameter mutations.
          </p>
        </div>

        <div 
          onClick={() => setCurrentView('report')}
          className="glass-panel-interactive p-6 rounded-xl cursor-pointer space-y-3"
        >
          <div className="w-10 h-10 rounded-lg bg-emerald-500/10 text-emerald-400 flex items-center justify-center">
            <BarChart2 className="w-5 h-5" />
          </div>
          <h4 className="text-base font-bold text-white">Final Research Report</h4>
          <p className="text-xs text-slate-400">
            Read and export the auto-generated scientific research report complete with literature citations and mandatory AI disclosures.
          </p>
        </div>
      </div>
    </div>
  );
}
