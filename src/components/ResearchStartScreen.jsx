import React, { useState, useRef } from 'react';

export default function ResearchStartScreen({ onSendChatMessage, isLaunching, onOpenMenu }) {
  const [objective, setObjective] = useState('');
  const [selectedFile, setSelectedFile] = useState(null);
  const [datasetMode, setDatasetMode] = useState('auto'); // 'auto' | 'upload'
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [budget, setBudget] = useState(10);
  const [maxExperiments, setMaxExperiments] = useState(20);
  const [researchMode, setResearchMode] = useState('Autonomous');
  const fileInputRef = useRef(null);

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
      setDatasetMode('upload');
    }
  };

  const handleSubmit = (e) => {
    if (e) e.preventDefault();
    if (!objective.trim()) return;
    onSendChatMessage(objective.trim());
    setObjective('');
  };

  return (
    <div className="flex-1 flex flex-col items-center justify-center p-4 sm:p-6 min-h-screen bg-[#0B0F17] select-none">
      {/* Mobile menu button — only visible below lg where the drawer replaces
          the sidebar; positioned in-flow at the top-left of the screen. */}
      {onOpenMenu && (
        <div className="lg:hidden fixed top-0 left-0 right-0 z-40 flex items-center px-3 pt-3 pointer-events-none"
          style={{ paddingTop: 'max(0.75rem, env(safe-area-inset-top))' }}>
          <button
            type="button"
            onClick={onOpenMenu}
            aria-label="Open menu"
            aria-expanded="false"
            className="pointer-events-auto w-11 h-11 flex items-center justify-center rounded-xl bg-[#131822]/90 border border-[#212B3B] text-slate-300 hover:text-slate-100 transition-colors shadow-lg"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
        </div>
      )}
      <div className="w-full max-w-2xl flex flex-col items-center space-y-8">
        
        {/* Brand Symbol & Title */}
        <div className="flex flex-col items-center space-y-3 text-center">
          <div className="relative group">
            <div className="absolute -inset-1.5 bg-gradient-to-r from-cyan-500 to-blue-600 rounded-2xl blur-md opacity-30 group-hover:opacity-50 transition duration-500 animate-pulse-slow"></div>
            <div className="relative w-14 h-14 rounded-2xl bg-[#121824] border border-cyan-500/40 flex items-center justify-center text-cyan-400 shadow-2xl">
              <svg className="w-8 h-8 text-cyan-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="3" className="fill-cyan-400/20" />
                <path d="M12 3a9 9 0 0 1 9 9" />
                <path d="M3 12a9 9 0 0 1 9-9" />
                <path d="M12 21a9 9 0 0 1-9-9" />
              </svg>
            </div>
          </div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-100 font-sans">
            AI Scientist
          </h1>
          <p className="text-sm text-slate-400 max-w-md">
            Your autonomous machine learning research assistant
          </p>
        </div>

        {/* ChatGPT / Claude Style Chat Composer Card */}
        <form onSubmit={handleSubmit} className="w-full bg-[#131824] border border-[#232D3F] rounded-2xl p-4 shadow-2xl space-y-4">
          
          {/* Main Input Textarea */}
          <div className="relative">
            <textarea
              value={objective}
              onChange={(e) => setObjective(e.target.value)}
              placeholder="What would you like to investigate? (e.g. 'Improve credit-card fraud detection')"
              rows={3}
              className="w-full bg-[#0B0F17] border border-[#212B3B] focus:border-cyan-500/70 rounded-xl p-4 text-sm text-slate-100 placeholder-slate-500 resize-none focus:outline-none font-sans leading-relaxed"
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSubmit(e);
                }
              }}
            />
          </div>

          {/* Action Row */}
          <div className="flex flex-wrap items-center justify-between gap-3 pt-1 border-t border-[#1C2536]">
            
            {/* Dataset Attachment Controls */}
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-all flex items-center gap-1.5 cursor-pointer ${
                  selectedFile
                    ? 'bg-cyan-500/10 text-cyan-400 border-cyan-500/40'
                    : 'bg-[#0B0F17] text-slate-400 border-[#212B3B] hover:text-slate-200 hover:bg-[#161D2B]'
                }`}
              >
                <span>📎</span>
                <span className="truncate max-w-[160px]">
                  {selectedFile ? selectedFile.name : 'Upload dataset (optional)'}
                </span>
              </button>
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileChange}
                accept=".csv,.parquet"
                className="hidden"
              />

              {!selectedFile && (
                <span className="text-[11px] text-slate-500">
                  (or default auto benchmark)
                </span>
              )}
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={!objective.trim() || isLaunching}
              className={`px-5 py-2 rounded-xl text-xs font-semibold transition-all shadow-md flex items-center gap-2 ${
                objective.trim() && !isLaunching
                  ? 'bg-cyan-500 hover:bg-cyan-400 text-slate-950 cursor-pointer shadow-cyan-500/20'
                  : 'bg-[#1C2536] text-slate-500 cursor-not-allowed'
              }`}
            >
              {isLaunching ? (
                <>
                  <span className="w-3.5 h-3.5 border-2 border-slate-950 border-t-transparent rounded-full animate-spin"></span>
                  <span>Starting...</span>
                </>
              ) : (
                <span>Start Research →</span>
              )}
            </button>

          </div>

          {/* Collapsible Advanced Technical Drawer Toggle */}
          <div className="pt-2 text-right">
            <button
              type="button"
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="text-[11px] text-slate-500 hover:text-slate-300 transition-colors inline-flex items-center gap-1"
            >
              <span>⚙ {showAdvanced ? 'Hide research parameters' : 'Research parameters'}</span>
            </button>
          </div>

          {/* Advanced Parameters Drawer — 1 col phones / 2 col tablet / 3 col desktop */}
          {showAdvanced && (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 p-3 bg-[#0B0F17] border border-[#212B3B] rounded-xl text-xs">
              <div>
                <label className="text-[10px] text-slate-500 uppercase block mb-1 font-semibold">Budget</label>
                <select
                  value={budget}
                  onChange={(e) => setBudget(Number(e.target.value))}
                  className="w-full bg-[#131824] border border-[#212B3B] text-slate-200 text-xs rounded-lg px-2 py-1.5 focus:outline-none"
                >
                  <option value={10}>Standard ($10)</option>
                  <option value={25}>Extended ($25)</option>
                  <option value={50}>Deep ($50)</option>
                </select>
              </div>

              <div>
                <label className="text-[10px] text-slate-500 uppercase block mb-1 font-semibold">Max Experiments</label>
                <select
                  value={maxExperiments}
                  onChange={(e) => setMaxExperiments(Number(e.target.value))}
                  className="w-full bg-[#131824] border border-[#212B3B] text-slate-200 text-xs rounded-lg px-2 py-1.5 focus:outline-none"
                >
                  <option value={5}>5 Experiments</option>
                  <option value={10}>10 Experiments</option>
                  <option value={20}>20 Experiments</option>
                </select>
              </div>

              <div>
                <label className="text-[10px] text-slate-500 uppercase block mb-1 font-semibold">Mode</label>
                <select
                  value={researchMode}
                  onChange={(e) => setResearchMode(e.target.value)}
                  className="w-full bg-[#131824] border border-[#212B3B] text-slate-200 text-xs rounded-lg px-2 py-1.5 focus:outline-none"
                >
                  <option value="Autonomous">Autonomous</option>
                  <option value="Semi-Autonomous">Semi-Autonomous</option>
                  <option value="Manual">Manual</option>
                </select>
              </div>
            </div>
          )}

        </form>



      </div>
    </div>
  );
}

