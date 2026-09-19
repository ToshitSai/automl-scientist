import React, { useState } from 'react';
import AutoMLScientistLogo from './AutoMLScientistLogo';

export default function Sidebar({ 
  projects, 
  activeProject, 
  setActiveProject, 
  onNewResearch, 
  onOpenSettings
}) {
  const [searchQuery, setSearchQuery] = useState('');

  const filteredProjects = projects.filter(p => 
    p.name.toLowerCase().includes(searchQuery.toLowerCase()) || 
    p.objective.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Group projects by recency
  const groupProjects = (items) => {
    const today = [];
    const yesterday = [];
    const earlier = [];

    const now = new Date();
    items.forEach(p => {
      const pDate = new Date(p.createdAt || Date.now());
      const diffHours = (now - pDate) / (1000 * 60 * 60);

      if (diffHours < 24) today.push(p);
      else if (diffHours < 48) yesterday.push(p);
      else earlier.push(p);
    });

    return { today, yesterday, earlier };
  };

  const groups = groupProjects(filteredProjects);

  const renderProjectItem = (proj) => {
    const isSelected = activeProject?.id === proj.id;
    const isRunning = proj.status === 'IN_PROGRESS' || proj.status === 'QUEUED';
    const isCompleted = proj.status === 'COMPLETED';
    const isFailed = proj.status === 'FAILED';

    const cleanTitle = proj.name.replace(/^Research:\s*/, '');

    return (
      <button
        key={proj.id}
        onClick={() => setActiveProject(proj)}
        className={`w-full text-left px-3 py-2.5 rounded-lg transition-all text-xs flex items-center justify-between group ${
          isSelected 
            ? 'bg-[#1E293B] text-slate-100 border border-slate-700/60 font-medium' 
            : 'text-slate-400 hover:text-slate-200 hover:bg-[#161B26]'
        }`}
      >
        <span className="truncate max-w-[170px]" title={cleanTitle}>{cleanTitle}</span>
        
        <span className="shrink-0 flex items-center gap-1 text-[11px]">
          {isRunning && (
            <span className="inline-flex items-center text-cyan-400 gap-1 font-medium">
              <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse"></span>
              Researching
            </span>
          )}
          {isCompleted && (
            <span className="inline-flex items-center text-emerald-400 gap-1 font-medium">
              <span>✓</span>
              Done
            </span>
          )}
          {isFailed && (
            <span className="inline-flex items-center text-rose-400 gap-1 font-medium">
              ✕ Stopped
            </span>
          )}
        </span>
      </button>
    );
  };

  return (
    <aside className="w-[270px] shrink-0 h-screen bg-[#0D111A] border-r border-[#1E293B] flex flex-col justify-between select-none">
      {/* Top Header & Actions */}
      <div className="p-4 border-b border-[#1E293B]/60 flex flex-col gap-4">
        <AutoMLScientistLogo />

        <button
          onClick={onNewResearch}
          className="w-full py-2.5 px-3 rounded-xl bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 text-xs font-semibold flex items-center justify-center gap-2 transition-all hover:border-cyan-400/50 cursor-pointer shadow-sm"
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          + New Research
        </button>

        {/* Search */}
        <div className="relative">
          <svg className="w-3.5 h-3.5 absolute left-3 top-2.5 text-slate-500" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search research..."
            className="w-full bg-[#131822] border border-[#212B3B] rounded-xl pl-8 pr-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500/50"
          />
        </div>
      </div>

      {/* Scrollable Project History */}
      <div className="flex-1 overflow-y-auto p-3 space-y-4">
        {projects.length === 0 ? (
          <div className="py-12 text-center text-xs text-slate-500 italic">
            No research chats yet
          </div>
        ) : (
          <>
            {groups.today.length > 0 && (
              <div>
                <div className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold px-2 mb-1.5">
                  Today
                </div>
                <div className="space-y-1">
                  {groups.today.map(renderProjectItem)}
                </div>
              </div>
            )}

            {groups.yesterday.length > 0 && (
              <div>
                <div className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold px-2 mb-1.5">
                  Yesterday
                </div>
                <div className="space-y-1">
                  {groups.yesterday.map(renderProjectItem)}
                </div>
              </div>
            )}

            {groups.earlier.length > 0 && (
              <div>
                <div className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold px-2 mb-1.5">
                  Earlier
                </div>
                <div className="space-y-1">
                  {groups.earlier.map(renderProjectItem)}
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* Bottom Settings */}
      <div className="p-3 border-t border-[#1E293B] bg-[#090D14]">
        <button
          onClick={onOpenSettings}
          className="w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs text-slate-300 hover:text-slate-100 hover:bg-[#161B26] transition-all"
        >
          <span className="flex items-center gap-2 font-medium">
            <svg className="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.38a2 2 0 0 0-.73-2.73l-.15-.09a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
              <circle cx="12" cy="12" r="3" />
            </svg>
            Settings & System
          </span>
          <span className="text-[10px] text-slate-500 font-mono">v1.0</span>
        </button>
      </div>
    </aside>
  );
}
