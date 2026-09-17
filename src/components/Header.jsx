import React from 'react';
import { Cpu, Terminal, Shield, Zap, Sparkles, Database } from 'lucide-react';

export default function Header({ currentView, activeProject, activeProvider }) {
  return (
    <header className="h-16 border-b border-slate-800 bg-[#0F172A]/90 backdrop-blur-md px-6 flex items-center justify-between sticky top-0 z-40">
      {/* Left: Project title & active scope */}
      <div className="flex items-center space-x-4">
        <div className="flex items-center space-x-2">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-cyan-500 to-blue-600 flex items-center justify-center text-white font-bold shadow-lg shadow-cyan-500/20">
            <Sparkles className="w-4 h-4 text-white" />
          </div>
          <div>
            <h1 className="font-extrabold text-base tracking-tight bg-gradient-to-r from-white via-slate-200 to-cyan-400 bg-clip-text text-transparent">
              AutoML Scientist
            </h1>
            <p className="text-[10px] text-cyan-400/80 font-mono tracking-wider uppercase">
              Autonomous ML Research Engine v2.0
            </p>
          </div>
        </div>

        <div className="h-5 w-[1px] bg-slate-800 hidden sm:block"></div>

        <div className="hidden sm:flex items-center space-x-2 bg-slate-900/80 border border-slate-800 rounded-full px-3 py-1 text-xs">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
          <span className="text-slate-400">Active Scope:</span>
          <span className="text-slate-200 font-semibold">{activeProject ? activeProject.name : 'No Active Project'}</span>
        </div>
      </div>

      {/* Right: Engine metrics & status indicators */}
      <div className="flex items-center space-x-4">
        {/* Sandbox indicator */}
        <div className="hidden md:flex items-center space-x-2 bg-slate-900/60 border border-slate-800 text-xs px-2.5 py-1 rounded-md text-slate-300">
          <Shield className="w-3.5 h-3.5 text-emerald-400" />
          <span>Sandbox: <strong className="text-emerald-400">Docker Isolated</strong></span>
        </div>

        {/* LLM Provider */}
        <div className="hidden lg:flex items-center space-x-2 bg-slate-900/60 border border-slate-800 text-xs px-2.5 py-1 rounded-md text-slate-300">
          <Cpu className="w-3.5 h-3.5 text-cyan-400" />
          <span>LLM: <strong className="text-cyan-300">{activeProvider}</strong></span>
        </div>

        {/* Compute Budget */}
        <div className="flex items-center space-x-2 bg-cyan-950/40 border border-cyan-800/40 text-xs px-3 py-1 rounded-md text-cyan-200">
          <Zap className="w-3.5 h-3.5 text-amber-400" />
          <span className="font-mono">Budget: 42m / 60m</span>
        </div>
      </div>
    </header>
  );
}
