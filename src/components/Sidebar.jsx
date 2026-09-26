import React, { useState, useEffect } from 'react';
import AutoMLScientistLogo from './AutoMLScientistLogo';

/**
 * Sidebar — persistent rail on desktop (>=1024px), slide-in drawer below.
 *
 * The mobile drawer OVERLAYS the chat (fixed, backdrop) instead of squeezing
 * it: main content keeps 100% of the viewport width when the drawer is closed.
 * `isOpen`/`onClose` only affect the mobile drawer; the desktop aside renders
 * exactly as before so desktop layout is untouched.
 */
export default function Sidebar({
  projects,
  activeProject,
  setActiveProject,
  onNewResearch,
  onOpenSettings,
  isMobileOpen = false,
  onMobileClose,
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
        className={`w-full text-left px-3 py-2.5 min-h-[44px] rounded-lg transition-all text-xs flex items-center justify-between gap-2 group ${
          isSelected
            ? 'bg-[#1E293B] text-slate-100 border border-slate-700/60 font-medium'
            : 'text-slate-400 hover:text-slate-200 hover:bg-[#161B26]'
        }`}
      >
        <span className="truncate min-w-0 flex-1" title={cleanTitle}>{cleanTitle}</span>

        <span className="shrink-0 flex items-center gap-1 text-[11px]">
          {isRunning && (
            <span className="inline-flex items-center text-cyan-400 gap-1 font-medium">
              <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse"></span>
              <span className="hidden min-[400px]:inline">Researching</span>
            </span>
          )}
          {isCompleted && (
            <span className="inline-flex items-center text-emerald-400 gap-1 font-medium">
              <span>✓</span>
              <span className="hidden min-[400px]:inline">Done</span>
            </span>
          )}
          {isFailed && (
            <span className="inline-flex items-center text-rose-400 gap-1 font-medium">
              ✕ <span className="hidden min-[400px]:inline">Stopped</span>
            </span>
          )}
        </span>
      </button>
    );
  };

  const sidebarBody = (
    <>
      {/* Top Header & Actions */}
      <div className="p-4 border-b border-[#1E293B]/60 flex flex-col gap-4">
        <div className="flex items-center justify-between gap-2">
          <AutoMLScientistLogo />
          {/* Close button — drawer only */}
          {onMobileClose && (
            <button
              type="button"
              onClick={onMobileClose}
              aria-label="Close menu"
              className="lg:hidden w-10 h-10 -mr-2 flex items-center justify-center rounded-lg text-slate-400 hover:text-slate-100 hover:bg-[#161B26] transition-colors"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" aria-hidden="true">
                <path d="M6 6l12 12M18 6L6 18" />
              </svg>
            </button>
          )}
        </div>

        <button
          onClick={() => { onNewResearch(); onMobileClose?.(); }}
          className="w-full py-2.5 px-3 rounded-xl bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 text-xs font-semibold flex items-center justify-center gap-2 transition-all hover:border-cyan-400/50 cursor-pointer shadow-sm"
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true">
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          + New Research
        </button>

        {/* Search */}
        <div className="relative">
          <svg className="w-3.5 h-3.5 absolute left-3 top-2.5 text-slate-500" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" aria-hidden="true">
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search research..."
            aria-label="Search research"
            className="w-full min-w-0 bg-[#131822] border border-[#212B3B] rounded-xl pl-8 pr-3 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500/50"
          />
        </div>
      </div>

      {/* Scrollable Project History */}
      <div className="flex-1 overflow-y-auto overscroll-contain p-3 space-y-4">
        {projects.length === 0 ? (
          <div className="py-12 text-center text-xs text-slate-500 italic">
            No research chats yet
          </div>
        ) : (
          <>
            {['today', 'yesterday', 'earlier'].map((g) =>
              groups[g].length > 0 ? (
                <div key={g}>
                  <div className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold px-2 mb-1.5">
                    {g === 'today' ? 'Today' : g === 'yesterday' ? 'Yesterday' : 'Earlier'}
                  </div>
                  <div className="space-y-1">
                    {groups[g].map(renderProjectItem)}
                  </div>
                </div>
              ) : null
            )}
          </>
        )}
      </div>

      {/* Bottom Settings */}
      <div
        className="p-3 border-t border-[#1E293B] bg-[#090D14]"
        style={{ paddingBottom: 'max(0.75rem, env(safe-area-inset-bottom))' }}
      >
        <button
          onClick={() => { onOpenSettings(); onMobileClose?.(); }}
          className="w-full flex items-center justify-between px-3 py-2.5 min-h-[44px] rounded-xl text-xs text-slate-300 hover:text-slate-100 hover:bg-[#161B26] transition-all"
        >
          <span className="flex items-center gap-2 font-medium">
            <svg className="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.38a2 2 0 0 0-.73-2.73l-.15-.09a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
              <circle cx="12" cy="12" r="3" />
            </svg>
            Settings &amp; System
          </span>
          <span className="text-[10px] text-slate-500 font-mono">v1.0</span>
        </button>
      </div>
    </>
  );

  return (
    <>
      {/* Desktop: permanent rail — unchanged design (>=1024px) */}
      <aside className="hidden lg:flex w-[270px] shrink-0 h-screen bg-[#0D111A] border-r border-[#1E293B] flex-col justify-between select-none">
        {sidebarBody}
      </aside>

      {/* Mobile / tablet: slide-in drawer overlaying the chat (<1024px) */}
      {isMobileOpen && (
        <div className="lg:hidden fixed inset-0 z-50" role="dialog" aria-modal="true" aria-label="Research menu">
          {/* Backdrop — click to close */}
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-[2px]"
            onClick={onMobileClose}
            aria-hidden="true"
          ></div>
          <aside
            className="absolute left-0 top-0 bottom-0 w-[86vw] max-w-[300px] bg-[#0D111A] border-r border-[#1E293B] flex flex-col justify-between select-none shadow-2xl"
            style={{ paddingTop: 'env(safe-area-inset-top)', paddingBottom: 0 }}
          >
            {sidebarBody}
          </aside>
        </div>
      )}
    </>
  );
}
