import React, { useState, useRef } from 'react';
import AutoMLScientistLogo from './AutoMLScientistLogo';

export default function ResearchStartScreen({ onStartResearch, isLaunching }) {
  const [objective, setObjective] = useState('');
  const [selectedFile, setSelectedFile] = useState(null);
  const [provider, setProvider] = useState('Heuristic / Rule-based');
  const [budget, setBudget] = useState(60);
  const [maxExperiments, setMaxExperiments] = useState(5);
  const fileInputRef = useRef(null);

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!objective.trim()) return;

    const formData = new FormData();
    formData.append('objective', objective.trim());
    formData.append('budget', budget);
    formData.append('llm_provider', provider);
    formData.append('max_experiments', maxExperiments);
    if (selectedFile) {
      formData.append('file', selectedFile);
    }

    onStartResearch(formData);
  };

  return (
    <div className="flex-1 flex flex-col items-center justify-center p-6 min-h-screen bg-[#0B0F17] select-none">
      <div className="w-full max-w-2xl flex flex-col items-center text-center space-y-6">
        
        {/* Animated Brand Symbol */}
        <div className="relative group">
          <div className="absolute -inset-1 bg-gradient-to-r from-cyan-500 to-blue-600 rounded-2xl blur-lg opacity-25 group-hover:opacity-40 transition duration-500 animate-pulse-slow"></div>
          <div className="relative w-16 h-16 rounded-2xl bg-[#121824] border border-cyan-500/30 flex items-center justify-center text-cyan-400 shadow-2xl">
            <svg className="w-10 h-10 text-cyan-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
              <circle cx="12" cy="12" r="3" className="fill-cyan-400/20" />
              <path d="M12 3a9 9 0 0 1 9 9" />
              <path d="M3 12a9 9 0 0 1 9-9" />
              <path d="M12 21a9 9 0 0 1-9-9" />
              <circle cx="12" cy="3" r="1.5" className="fill-cyan-400" />
              <circle cx="21" cy="12" r="1.5" className="fill-cyan-400" />
              <circle cx="12" cy="21" r="1.5" className="fill-cyan-400" />
              <circle cx="3" cy="12" r="1.5" className="fill-cyan-400" />
            </svg>
          </div>
        </div>

        {/* Title & Subtitle */}
        <div className="space-y-2">
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-100 font-sans">
            How can I help you research?
          </h1>
          <p className="text-xs sm:text-sm text-slate-400 max-w-lg mx-auto leading-relaxed">
            Autonomous machine learning research engine. Submit a dataset and objective to start end-to-end hypothesis generation, baseline training, and sandboxed code execution.
          </p>
        </div>

        {/* Sakana Chat Style Command Input Box */}
        <form onSubmit={handleSubmit} className="w-full text-left">
          <div className="relative bg-[#131824] border border-[#232D3F] focus-within:border-cyan-500/60 rounded-2xl p-4 shadow-2xl transition-all">
            
            {/* Multiline Input Textarea */}
            <textarea
              value={objective}
              onChange={(e) => setObjective(e.target.value)}
              placeholder="Describe an ML problem you want to investigate (e.g. 'Improve fraud detection under severe class imbalance')..."
              rows={3}
              className="w-full bg-transparent text-sm text-slate-100 placeholder-slate-500 resize-none focus:outline-none font-sans leading-relaxed"
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSubmit(e);
                }
              }}
            />

            {/* Attached Dataset Badge */}
            {selectedFile && (
              <div className="mt-2 inline-flex items-center gap-2 px-3 py-1 rounded-lg bg-cyan-950/60 border border-cyan-500/30 text-cyan-300 text-xs font-mono">
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                </svg>
                <span className="truncate max-w-[200px]">{selectedFile.name}</span>
                <span className="text-[10px] opacity-70">({(selectedFile.size / 1024).toFixed(0)} KB)</span>
                <button
                  type="button"
                  onClick={() => setSelectedFile(null)}
                  className="hover:text-rose-400 ml-1 text-slate-400 transition-colors"
                >
                  ✕
                </button>
              </div>
            )}

            {/* Action Bar Inside Input */}
            <div className="mt-4 pt-3 border-t border-[#1C2536] flex flex-wrap items-center justify-between gap-3">
              
              <div className="flex items-center flex-wrap gap-2 text-xs">
                
                {/* File Upload Attachment Button */}
                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={handleFileChange}
                  accept=".csv,.parquet"
                  className="hidden"
                />
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="px-2.5 py-1.5 rounded-lg bg-[#1A2232] hover:bg-[#222C3E] text-slate-300 border border-[#2B364A] flex items-center gap-1.5 transition-all text-xs font-medium cursor-pointer"
                >
                  <svg className="w-3.5 h-3.5 text-cyan-400" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                    <path d="M12 5v14M5 12h14" />
                  </svg>
                  {selectedFile ? 'Change Dataset' : 'Attach Dataset'}
                </button>

                {/* Model Selector */}
                <select
                  value={provider}
                  onChange={(e) => setProvider(e.target.value)}
                  className="bg-[#1A2232] border border-[#2B364A] text-slate-300 text-xs rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-cyan-500/50 cursor-pointer font-mono"
                >
                  <option value="Heuristic / Rule-based">Engine: Rule Synthesis</option>
                  <option value="OpenAI GPT-4o">Model: OpenAI GPT-4o</option>
                  <option value="Anthropic Claude 3.5">Model: Claude 3.5 Sonnet</option>
                  <option value="Ollama Local">Model: Ollama Local</option>
                </select>

                {/* Budget Selector */}
                <select
                  value={budget}
                  onChange={(e) => setBudget(Number(e.target.value))}
                  className="bg-[#1A2232] border border-[#2B364A] text-slate-300 text-xs rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-cyan-500/50 cursor-pointer font-mono"
                >
                  <option value={15}>Budget: 15 mins</option>
                  <option value={30}>Budget: 30 mins</option>
                  <option value={60}>Budget: 60 mins</option>
                </select>
              </div>

              {/* Submit / Send Button */}
              <button
                type="submit"
                disabled={!objective.trim() || isLaunching}
                className={`p-2.5 rounded-xl font-medium text-xs flex items-center justify-center transition-all ${
                  objective.trim() && !isLaunching
                    ? 'bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-semibold shadow-lg shadow-cyan-500/20 cursor-pointer'
                    : 'bg-[#1C2536] text-slate-600 cursor-not-allowed'
                }`}
              >
                {isLaunching ? (
                  <span className="w-4 h-4 border-2 border-slate-950 border-t-transparent rounded-full animate-spin"></span>
                ) : (
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                    <line x1="12" y1="19" x2="12" y2="5" />
                    <polyline points="5 12 12 5 19 12" />
                  </svg>
                )}
              </button>
            </div>
          </div>
        </form>

        {/* Quick Suggestion Chips */}
        <div className="flex flex-wrap items-center justify-center gap-2 pt-2 text-xs">
          <span className="text-slate-500 text-[11px]">Example research prompts:</span>
          {[
            "Improve fraud detection under extreme class imbalance",
            "Optimize customer churn classification with LightGBM",
            "Predict housing prices using regularized feature selection"
          ].map((prompt, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => setObjective(prompt)}
              className="px-2.5 py-1 rounded-full bg-[#121722] hover:bg-[#1A2232] border border-[#212B3B] text-slate-400 hover:text-slate-200 transition-all text-[11px] cursor-pointer"
            >
              {prompt}
            </button>
          ))}
        </div>

      </div>
    </div>
  );
}
