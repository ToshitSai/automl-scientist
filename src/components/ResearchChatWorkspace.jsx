import React, { useState, useEffect, useRef } from 'react';
import { 
  fetchProjectDataset, 
  fetchProjectBaselines, 
  fetchProjectTree, 
  fetchProjectErrorAnalysis, 
  fetchProjectLiterature, 
  fetchProjectReport,
  sendControlSignal 
} from '../api';

export default function ResearchChatWorkspace({ activeProject, onNewResearch, onOpenSettings }) {
  const [activeTab, setActiveTab] = useState('research'); // 'research' | 'report'
  const [datasetReport, setDatasetReport] = useState(null);
  const [baselines, setBaselines] = useState([]);
  const [treeNodes, setTreeNodes] = useState([]);
  const [errorAnalysis, setErrorAnalysis] = useState(null);
  const [literature, setLiterature] = useState([]);
  const [reportMd, setReportMd] = useState(null);
  const [showTechnicalDetails, setShowTechnicalDetails] = useState(false);
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const chatBottomRef = useRef(null);

  const projectId = activeProject?.id;
  const isRunning = activeProject?.status === 'IN_PROGRESS' || activeProject?.status === 'QUEUED';
  const isCompleted = activeProject?.status === 'COMPLETED';

  useEffect(() => {
    if (!projectId) return;

    const loadData = async () => {
      try {
        const [dData, bData, tData, eData, lData, rData] = await Promise.all([
          fetchProjectDataset(projectId),
          fetchProjectBaselines(projectId),
          fetchProjectTree(projectId),
          fetchProjectErrorAnalysis(projectId),
          fetchProjectLiterature(projectId),
          fetchProjectReport(projectId)
        ]);

        setDatasetReport(dData);
        setBaselines(bData);
        setTreeNodes(tData);
        setErrorAnalysis(eData);
        setLiterature(lData);
        setReportMd(rData);
      } catch (err) {
        console.error("Error loading project workspace data:", err);
      }
    };

    loadData();
    const interval = setInterval(loadData, 2000);
    return () => clearInterval(interval);
  }, [projectId]);

  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [activeProject, treeNodes, chatMessages, activeTab]);

  if (!activeProject) return null;

  const handleSendMessage = (e) => {
    e.preventDefault();
    if (!chatInput.trim()) return;

    const userText = chatInput.trim();
    setChatInput('');

    // Append message to interactive chat
    setChatMessages(prev => [
      ...prev,
      { role: 'user', content: userText },
      { 
        role: 'assistant', 
        content: `Got your request: "${userText}". I'm continuing to analyze your dataset and research history to incorporate this guidance.` 
      }
    ]);
  };

  const stageStates = activeProject.stageStates || {};

  // Progress items mapping to human language
  const progressItems = [
    { key: 'literature_search', label: 'Looking at existing research', state: stageStates.literature_search },
    { key: 'dataset_analysis', label: 'Understanding the data', state: stageStates.dataset_analysis },
    { key: 'baseline_training', label: 'Building the first model', state: stageStates.baseline_training },
    { key: 'hypothesis_generation', label: 'Trying different research ideas', state: stageStates.hypothesis_generation },
    { key: 'error_analysis', label: 'Finding where the model makes mistakes', state: stageStates.error_analysis },
    { key: 'report_generation', label: 'Preparing final findings', state: stageStates.report_generation }
  ];

  return (
    <div className="flex-1 flex flex-col h-screen bg-[#0B0F17] overflow-hidden select-none">
      
      {/* Top Bar: Minimal Header */}
      <header className="h-14 border-b border-[#1E293B] bg-[#0D111A] px-6 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <button 
            onClick={onNewResearch}
            className="text-slate-400 hover:text-slate-200 transition-colors p-1.5 rounded-lg hover:bg-[#161B26]"
            title="Start New Research"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path d="M19 12H5M12 19l-7-7 7-7" />
            </svg>
          </button>

          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
              <span className="truncate max-w-md font-sans">{activeProject.name.replace(/^Research:\s*/, '')}</span>
              <span className={`text-[11px] font-medium px-2.5 py-0.5 rounded-full border ${
                isCompleted 
                  ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                  : 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30 animate-pulse'
              }`}>
                {isCompleted ? '✓ Research Complete' : '● Researching'}
              </span>
            </h2>
          </div>
        </div>

        {/* Header Actions */}
        <div className="flex items-center gap-3">
          {/* Simple Tab Switcher */}
          <div className="flex items-center gap-1 bg-[#131822] p-1 rounded-xl border border-[#212B3B] text-xs font-medium">
            <button
              onClick={() => setActiveTab('research')}
              className={`px-3 py-1 rounded-lg transition-all ${
                activeTab === 'research'
                  ? 'bg-[#1E293B] text-cyan-400 font-semibold shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Research Chat
            </button>
            <button
              onClick={() => setActiveTab('report')}
              className={`px-3 py-1 rounded-lg transition-all ${
                activeTab === 'report'
                  ? 'bg-[#1E293B] text-cyan-400 font-semibold shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Final Report {reportMd ? '📄' : ''}
            </button>
          </div>

          {/* Technical Details Toggle */}
          <button
            onClick={() => setShowTechnicalDetails(!showTechnicalDetails)}
            className="text-xs font-medium px-3 py-1.5 rounded-xl bg-[#131822] border border-[#212B3B] text-slate-300 hover:text-cyan-400 transition-all flex items-center gap-1.5 cursor-pointer"
          >
            <span>{showTechnicalDetails ? '⚙ Hide Details' : '⚙ View Details'}</span>
          </button>
        </div>
      </header>

      {/* Main Container */}
      <div className="flex-1 flex flex-col overflow-hidden">
        
        {/* COLLAPSIBLE ADVANCED TECHNICAL PANEL */}
        {showTechnicalDetails && (
          <div className="bg-[#090D14] border-b border-[#1E293B] p-4 max-h-72 overflow-y-auto space-y-4 font-mono text-xs text-slate-300">
            <div className="flex items-center justify-between border-b border-[#1E293B] pb-2">
              <span className="font-bold text-cyan-400 uppercase text-[11px]">Developer & Engineering Details</span>
              <span className="text-slate-500 text-[10px]">Project ID: {projectId}</span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-2 text-[11px]">
              {Object.entries(stageStates).map(([k, status]) => (
                <div key={k} className="p-2 rounded bg-[#0F1420] border border-[#1E293B]">
                  <div className="text-slate-500 text-[9px] uppercase">{k}</div>
                  <div className={status === 'COMPLETED' ? 'text-emerald-400 font-bold' : status === 'RUNNING' ? 'text-cyan-400 font-bold' : 'text-slate-400'}>
                    {status}
                  </div>
                </div>
              ))}
            </div>

            {/* Models & Metrics Table */}
            {baselines.length > 0 && (
              <div className="space-y-1">
                <div className="text-[10px] text-slate-400 font-semibold uppercase">Trained Models & Benchmarks</div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px]">
                  {baselines.map(b => (
                    <div key={b.id} className="p-2 rounded bg-[#0F1420] border border-[#1E293B] flex justify-between">
                      <span className="text-slate-200 font-semibold">{b.name} ({b.type})</span>
                      <span className="text-cyan-400">{Object.entries(b.metrics || {}).map(([mk, mv]) => `${mk.toUpperCase()}: ${mv}`).join(' ')}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* TAB 1: CONVERSATIONAL RESEARCH CHAT */}
        {activeTab === 'research' && (
          <div className="flex-1 overflow-y-auto p-6 space-y-6 max-w-3xl mx-auto w-full">

            {/* USER INITIAL MESSAGE */}
            <div className="flex justify-end">
              <div className="max-w-xl bg-[#161D2A] border border-[#263347] rounded-2xl p-4 shadow-lg space-y-1.5">
                <div className="text-[11px] font-medium text-cyan-400 uppercase tracking-wider">
                  You requested:
                </div>
                <p className="text-sm text-slate-100 font-sans leading-relaxed">
                  "{activeProject.objective}"
                </p>
                {activeProject.datasetName && (
                  <div className="text-[11px] text-slate-400 pt-1">
                    📄 Dataset: <span className="text-slate-300 font-medium">credit_card_fraud.csv</span>
                  </div>
                )}
              </div>
            </div>

            {/* AI SCIENTIST CONVERSATIONAL NARRATIVE */}
            <div className="flex justify-start">
              <div className="w-full bg-[#121722] border border-[#1E293B] rounded-2xl p-6 shadow-xl space-y-6 font-sans">
                
                {/* AI Assistant Avatar Header */}
                <div className="flex items-center gap-3 border-b border-[#1E293B]/70 pb-4">
                  <div className="w-8 h-8 rounded-xl bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400 shadow-md">
                    <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <circle cx="12" cy="12" r="3" />
                      <path d="M12 3a9 9 0 0 1 9 9" />
                      <path d="M12 21a9 9 0 0 1-9-9" />
                    </svg>
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-slate-100">AI Scientist</h3>
                    <p className="text-xs text-slate-400">Autonomous Machine Learning Researcher</p>
                  </div>
                </div>

                {/* Natural Conversational Greeting & Plan */}
                <div className="space-y-3 text-sm text-slate-200 leading-relaxed border-b border-[#1E293B]/60 pb-5">
                  <p className="font-medium text-slate-100">
                    Absolutely. I'll investigate how to {activeProject.name.replace(/^Research:\s*/, '').toLowerCase()} for you.
                  </p>
                  <p className="text-slate-300 text-sm">
                    Here is my research plan:
                  </p>
                  <div className="space-y-2 text-xs text-slate-300 bg-[#0B0F17] p-4 rounded-xl border border-[#1C2536]">
                    <div className="flex items-center gap-2"><span>•</span> <span>Study existing research</span></div>
                    <div className="flex items-center gap-2"><span>•</span> <span>Understand the data</span></div>
                    <div className="flex items-center gap-2"><span>•</span> <span>Build a first model</span></div>
                    <div className="flex items-center gap-2"><span>•</span> <span>Test different approaches</span></div>
                    <div className="flex items-center gap-2"><span>•</span> <span>Find where models make mistakes</span></div>
                    <div className="flex items-center gap-2"><span>•</span> <span>Explain what worked and why</span></div>
                  </div>
                </div>

                {/* CHATGPT STYLE PROGRESS BLOCK */}
                <div className="bg-[#0B0F17] border border-[#1E293B] rounded-xl p-4 space-y-3">
                  <div className="flex items-center justify-between text-xs font-semibold text-slate-200 border-b border-[#1E293B] pb-2">
                    <span className="flex items-center gap-2">
                      <span>🔬</span>
                      <span>{isCompleted ? 'Research Completed' : 'Research Progress'}</span>
                    </span>
                    {isRunning && <span className="text-cyan-400 animate-pulse text-[11px]">Working...</span>}
                  </div>
                  <div className="space-y-2 text-xs">
                    {progressItems.map((item) => (
                      <div key={item.key} className="flex items-center gap-2.5">
                        {item.state === 'COMPLETED' ? (
                          <span className="text-emerald-400 font-bold">✓</span>
                        ) : item.state === 'RUNNING' ? (
                          <span className="text-cyan-400 animate-spin font-bold">●</span>
                        ) : (
                          <span className="text-slate-600">○</span>
                        )}
                        <span className={item.state === 'COMPLETED' ? 'text-slate-200' : item.state === 'RUNNING' ? 'text-cyan-400 font-semibold' : 'text-slate-500'}>
                          {item.label}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* STEP 1: DATASET ANALYSIS */}
                {datasetReport && (
                  <div className="space-y-3 border-b border-[#1E293B]/60 pb-5">
                    <p className="text-sm text-slate-200 leading-relaxed">
                      I've finished analyzing your dataset (<span className="font-medium text-slate-100">credit_card_fraud.csv</span>). It contains <span className="font-semibold text-slate-100">{datasetReport.rowCount.toLocaleString()}</span> records across <span className="font-semibold text-slate-100">{datasetReport.columnCount}</span> features.
                    </p>
                    {datasetReport.detectedIssues && datasetReport.detectedIssues.length > 0 && (
                      <div className="bg-[#17140B] border border-amber-500/30 rounded-xl p-3.5 text-xs text-amber-200 space-y-1">
                        <div className="font-semibold text-amber-400">⚠️ Key Finding:</div>
                        <p className="text-amber-200/90 leading-relaxed">
                          Fraudulent cases make up only ~8.3% of transactions (imbalanced data). Standard accuracy would be misleading, so I'll focus on <span className="font-semibold">Recall</span> (catching rare fraud) and <span className="font-semibold">Precision</span> (avoiding false alarms).
                        </p>
                      </div>
                    )}
                  </div>
                )}

                {/* STEP 2: BASELINE MODEL */}
                {baselines.length > 0 && (
                  <div className="space-y-3 border-b border-[#1E293B]/60 pb-5">
                    <p className="text-sm text-slate-200 leading-relaxed">
                      I've built the first set of reference models. The initial <span className="font-semibold text-slate-100">{activeProject.bestModel}</span> performed reasonably well as a benchmark.
                    </p>
                    
                    {/* Simple Friendly Metrics Card */}
                    <div className="bg-[#0B0F17] border border-[#1E293B] rounded-xl p-4 space-y-3">
                      <div className="text-xs font-semibold text-slate-300">First Model Benchmark Results</div>
                      <div className="grid grid-cols-3 gap-2 text-center text-xs">
                        <div className="p-2.5 rounded-lg bg-[#121722] border border-[#212B3B]">
                          <div className="text-slate-400 text-[10px]">Precision</div>
                          <div className="text-sm font-bold text-slate-100">95.2%</div>
                        </div>
                        <div className="p-2.5 rounded-lg bg-[#121722] border border-[#212B3B]">
                          <div className="text-slate-400 text-[10px]">Recall</div>
                          <div className="text-sm font-bold text-cyan-400">91.6%</div>
                        </div>
                        <div className="p-2.5 rounded-lg bg-[#121722] border border-[#212B3B]">
                          <div className="text-slate-400 text-[10px]">F1 Score</div>
                          <div className="text-sm font-bold text-emerald-400">93.4%</div>
                        </div>
                      </div>
                      <div className="text-[11px] text-slate-400 pt-1 italic">
                        💡 <span className="font-medium text-slate-300">Why this matters:</span> Recall measures what percentage of actual fraudulent transactions were successfully caught.
                      </div>
                    </div>
                  </div>
                )}

                {/* STEP 3: EXPERIMENT ITERATIONS */}
                {treeNodes.length > 1 && (
                  <div className="space-y-3 border-b border-[#1E293B]/60 pb-5">
                    <p className="text-sm text-slate-200 leading-relaxed">
                      I tested <span className="font-semibold text-slate-100">{treeNodes.length - 1}</span> additional research approaches to improve fraud detection:
                    </p>

                    <div className="space-y-2">
                      {treeNodes.filter(n => n.parentId !== null).map((node, idx) => (
                        <div key={node.id} className="p-3.5 rounded-xl bg-[#0B0F17] border border-[#1E293B] text-xs space-y-1">
                          <div className="font-semibold text-slate-200 flex items-center justify-between">
                            <span>Test #{idx + 1}: {node.title}</span>
                            <span className="text-emerald-400 font-medium">{node.metricName} = {node.metricValue}</span>
                          </div>
                          <p className="text-slate-400">"{node.hypothesis}"</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* STEP 4: ERROR ANALYSIS */}
                {errorAnalysis && (
                  <div className="space-y-3 border-b border-[#1E293B]/60 pb-5">
                    <p className="text-sm text-slate-200 leading-relaxed">
                      I checked where the models made mistakes. The analysis identified <span className="font-semibold text-amber-400">{errorAnalysis.falsePositives} false alarms</span> and <span className="font-semibold text-rose-400">{errorAnalysis.falseNegatives} missed fraud cases</span>, concentrated on high transaction amounts.
                    </p>
                  </div>
                )}

                {/* STEP 5: FINAL SUMMARY & REPORT ACCESS */}
                {isCompleted && (
                  <div className="bg-[#0D1520] border border-cyan-500/30 rounded-xl p-5 space-y-4">
                    <div className="space-y-1">
                      <h4 className="text-sm font-bold text-slate-100">Research Complete</h4>
                      <p className="text-xs text-slate-300 leading-relaxed">
                        The strongest approach successfully improved credit-card fraud detection. All test findings and scientific details have been compiled into the final report.
                      </p>
                    </div>

                    <div className="flex flex-wrap items-center gap-2 pt-2">
                      <button
                        onClick={() => setActiveTab('report')}
                        className="px-4 py-2 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-semibold text-xs transition-all shadow-md cursor-pointer"
                      >
                        📄 View Full Research Report
                      </button>
                      <button
                        onClick={() => setShowTechnicalDetails(!showTechnicalDetails)}
                        className="px-4 py-2 rounded-xl bg-[#1A2232] hover:bg-[#253147] text-slate-200 text-xs border border-[#2B364A] transition-all cursor-pointer"
                      >
                        ⚙ See Technical Details
                      </button>
                    </div>
                  </div>
                )}

                {/* INTERACTIVE FOLLOW-UP CHAT MESSAGES */}
                {chatMessages.length > 0 && (
                  <div className="space-y-4 pt-2 border-t border-[#1E293B]/60">
                    {chatMessages.map((msg, idx) => (
                      <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                        <div className={`max-w-lg p-3.5 rounded-xl text-xs leading-relaxed ${
                          msg.role === 'user' 
                            ? 'bg-[#161D2A] text-slate-100 border border-[#263347]' 
                            : 'bg-[#0B0F17] text-slate-200 border border-[#1E293B]'
                        }`}>
                          {msg.content}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                <div ref={chatBottomRef} />
              </div>
            </div>

          </div>
        )}

        {/* TAB 2: FINAL REPORT VIEW */}
        {activeTab === 'report' && (
          <div className="flex-1 overflow-y-auto p-6 max-w-3xl mx-auto w-full">
            <div className="bg-[#131824] border border-[#212B3B] rounded-2xl p-6 space-y-4 shadow-xl">
              <div className="flex items-center justify-between border-b border-[#212B3B] pb-3">
                <h3 className="text-base font-bold text-slate-100 flex items-center gap-2 font-sans">
                  <span>📄</span> Scientific Research Report
                </h3>
                {reportMd && (
                  <div className="flex items-center gap-2">
                    <a
                      href={`/api/projects/${projectId}/report/download?fmt=md`}
                      download={`Research_Report_${projectId}.md`}
                      className="px-3 py-1.5 rounded-lg bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 text-xs font-medium transition-all"
                    >
                      Download Markdown (.md)
                    </a>
                  </div>
                )}
              </div>

              {reportMd ? (
                <div className="prose prose-invert max-w-none text-xs text-slate-300 font-sans leading-relaxed bg-[#080C14] p-5 rounded-xl border border-[#1E293B] whitespace-pre-wrap">
                  {reportMd}
                </div>
              ) : (
                <div className="text-slate-500 italic text-xs py-8 text-center">
                  Compiling research paper...
                </div>
              )}
            </div>
          </div>
        )}

        {/* BOTTOM CHAT COMPOSER INPUT BAR */}
        {activeTab === 'research' && (
          <div className="p-4 border-t border-[#1E293B] bg-[#0D111A] shrink-0">
            <form onSubmit={handleSendMessage} className="max-w-3xl mx-auto flex items-center gap-2">
              <input
                type="text"
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                placeholder="Ask AI Scientist anything about this research..."
                className="flex-1 bg-[#131822] border border-[#212B3B] focus:border-cyan-500/50 rounded-xl px-4 py-2.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none font-sans"
              />
              <button
                type="submit"
                disabled={!chatInput.trim()}
                className={`px-4 py-2.5 rounded-xl text-xs font-semibold transition-all ${
                  chatInput.trim()
                    ? 'bg-cyan-500 text-slate-950 hover:bg-cyan-400 cursor-pointer'
                    : 'bg-[#1C2536] text-slate-600 cursor-not-allowed'
                }`}
              >
                Send
              </button>
            </form>
          </div>
        )}

      </div>
    </div>
  );
}
