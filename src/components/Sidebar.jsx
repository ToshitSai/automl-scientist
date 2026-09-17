import React from 'react';
import { 
  LayoutDashboard, 
  PlusCircle, 
  Workflow, 
  GitFork, 
  FlaskConical, 
  Database, 
  Cpu, 
  BarChart3, 
  AlertTriangle, 
  BookOpen, 
  FileText, 
  Settings 
} from 'lucide-react';

export default function Sidebar({ currentView, setCurrentView }) {
  const menuItems = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'new_research', label: 'New Research', icon: PlusCircle, highlight: true },
    { id: 'workspace', label: 'Research Workspace', icon: Workflow },
    { id: 'tree', label: 'Experiment Tree', icon: GitFork },
    { id: 'experiments', label: 'Experiments', icon: FlaskConical },
    { id: 'dataset_analysis', label: 'Dataset Analysis', icon: Database },
    { id: 'models', label: 'Models', icon: Cpu },
    { id: 'results', label: 'Results', icon: BarChart3 },
    { id: 'error_analysis', label: 'Error Analysis', icon: AlertTriangle },
    { id: 'literature', label: 'Literature', icon: BookOpen },
    { id: 'report', label: 'Research Report', icon: FileText },
    { id: 'settings', label: 'Settings', icon: Settings }
  ];

  return (
    <aside className="w-64 bg-[#0F172A] border-r border-slate-800 flex flex-col justify-between shrink-0 min-h-[calc(100vh-4rem)]">
      <div className="py-4">
        <div className="px-4 mb-3">
          <p className="text-[10px] font-mono tracking-wider uppercase text-slate-500 font-semibold">
            Navigation
          </p>
        </div>
        <nav className="space-y-1 px-2">
          {menuItems.map((item) => {
            const Icon = item.icon;
            const isActive = currentView === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setCurrentView(item.id)}
                className={`w-full flex items-center space-x-3 px-3 py-2.5 rounded-lg text-xs font-medium transition-all ${
                  isActive
                    ? 'bg-gradient-to-r from-cyan-600/30 to-blue-600/20 text-cyan-300 border border-cyan-500/40 shadow-sm shadow-cyan-500/10'
                    : item.highlight
                    ? 'bg-cyan-500/10 text-cyan-400 hover:bg-cyan-500/20 border border-cyan-500/20'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
                }`}
              >
                <Icon className={`w-4 h-4 ${isActive ? 'text-cyan-400' : item.highlight ? 'text-cyan-400' : 'text-slate-400'}`} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
      </div>

      {/* Footer attribution notice */}
      <div className="p-4 border-t border-slate-800/80 bg-slate-950/40 text-[11px] text-slate-400 space-y-1">
        <div className="flex items-center space-x-1 text-slate-300 font-semibold">
          <span>AutoML Scientist</span>
          <span className="text-[9px] bg-cyan-950 text-cyan-300 px-1 rounded border border-cyan-800">v2</span>
        </div>
        <p className="text-[10px] text-slate-400 leading-tight">
          Derived from Sakana AI&apos;s AI Scientist-v2. See docs for attribution.
        </p>
      </div>
    </aside>
  );
}
