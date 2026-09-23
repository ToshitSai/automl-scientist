import React, { useState, useEffect, useRef } from 'react';
import { 
  fetchProjectDataset, 
  fetchProjectBaselines, 
  fetchProjectTree, 
  fetchProjectErrorAnalysis, 
  fetchProjectLiterature, 
  fetchProjectReport,
  sendControlSignal,
  sendChatMessage
} from '../api';

export default function ResearchChatWorkspace({ 
  activeProject, 
  setActiveProject, 
  onNewResearch, 
  onOpenSettings,
  chatMessages,
  setChatMessages,
  onApproveDataset,
  isApproving,
  conversationId: propsConversationId
}) {
  const [activeTab, setActiveTab] = useState('research'); // 'research' | 'report'
  const [datasetReport, setDatasetReport] = useState(null);
  const [baselines, setBaselines] = useState([]);
  const [treeNodes, setTreeNodes] = useState([]);
  const [errorAnalysis, setErrorAnalysis] = useState(null);
  const [literature, setLiterature] = useState([]);
  const [reportMd, setReportMd] = useState(null);
  const [showTechnicalDetails, setShowTechnicalDetails] = useState(false);
  const [chatInput, setChatInput] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [pendingAction, setPendingAction] = useState(null);
  const [lastTopic, setLastTopic] = useState(null);
  const [localConversationId] = useState(() => 'conv-' + Math.random().toString(36).substring(2, 9));
  // Prefer the app-level conversation (shared with the first message) so the
  // whole chat shares one server-side memory.
  const conversationId = propsConversationId || localConversationId;
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
        console.error("Error loading workspace details:", err);
      }
    };

    loadData();
    const interval = setInterval(loadData, 2000);
    return () => clearInterval(interval);
  }, [projectId]);

  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [activeProject, treeNodes, chatMessages, activeTab]);

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!chatInput.trim() || isProcessing) return;

    const userText = chatInput.trim();
    setChatInput('');
    setIsProcessing(true);

    // 1. Add User message bubble immediately
    const userMsg = { id: Date.now(), role: 'user', content: userText };
    setChatMessages(prev => [...prev, userMsg]);

    try {
      // 2. Call backend Intent Router endpoint
      const res = await sendChatMessage(userText, projectId, conversationId, pendingAction, lastTopic);
      
      if (res.pendingAction !== undefined) {
        setPendingAction(res.pendingAction);
      }
      if (res.lastTopic) {
        setLastTopic(res.lastTopic);
      }
      
      const assistantMsg = {
        id: Date.now() + 1,
        role: 'assistant',
        content: res.response,
        intent: res.intent,
        action: res.action,
        datasets: res.candidates || null,
        recommendation: res.recommendation || null,
        researchQuery: res.researchQuery || null
      };

      setChatMessages(prev => [...prev, assistantMsg]);

      // 3. Handle actions returned by Intent Router
      if (res.action === 'START_RESEARCH' && res.project) {
        setActiveProject(res.project);
      } else if (res.action === 'STOP_RESEARCH' && projectId) {
        await sendControlSignal(projectId, 'STOP');
      } else if (res.action === 'RESUME_RESEARCH' && projectId) {
        await sendControlSignal(projectId, 'RUN');
      } else if (res.action === 'SHOW_REPORT') {
        setActiveTab('report');
      } else if (res.action === 'SHOW_TECHNICAL') {
        setShowTechnicalDetails(true);
      }
    } catch (err) {
      setChatMessages(prev => [
        ...prev,
        { id: Date.now() + 1, role: 'assistant', content: `Sorry, I ran into an error: ${err.message}` }
      ]);
    } finally {
      setIsProcessing(false);
    }
  };

  const stageStates = activeProject?.stageStates || {};

  // Pick the real best baseline (highest PR-AUC, the right metric under imbalance).
  const completedBaselines = (baselines || []).filter(b => b.status === 'COMPLETED');
  const bestBaseline = completedBaselines.length
    ? completedBaselines.reduce((a, b) => {
        const av = (a.metrics && (a.metrics.pr_auc ?? a.metrics.f1)) || 0;
        const bv = (b.metrics && (b.metrics.pr_auc ?? b.metrics.f1)) || 0;
        return bv > av ? b : a;
      })
    : null;
  const bm = bestBaseline?.metrics || {};
  const pct = (v) => (typeof v === 'number' ? `${(v * 100).toFixed(1)}%` : '—');
  const isFraudTask = bestBaseline && (bm.pr_auc != null || bm.recall != null);

  // Honest completion summary built ONLY from real stored results: compare the
  // best follow-up experiment against the baseline instead of claiming a win.
  const expNodes = treeNodes.filter(n => n.parentId !== null && n.metricValue != null);
  const metricName = (treeNodes[0] && treeNodes[0].metricName) || (expNodes[0] && expNodes[0].metricName) || 'metric';
  let completionSummary = "I've prepared the research report for you.";
  if (expNodes.length > 0) {
    const bestExp = expNodes.reduce((a, b) => ((b.metricValue ?? 0) > (a.metricValue ?? 0) ? b : a));
    const baseVal = (treeNodes.find(n => n.parentId === null) || {}).metricValue;
    const fmt = (v) => (typeof v === 'number' ? v.toFixed(4) : v);
    if (typeof baseVal === 'number' && bestExp.metricValue > baseVal) {
      completionSummary = `The best approach (${bestExp.title}) reached ${metricName} ${fmt(bestExp.metricValue)}, improving on the baseline's ${fmt(baseVal)}.`;
    } else if (typeof baseVal === 'number') {
      completionSummary = `None of the ${expNodes.length} additional approach${expNodes.length > 1 ? 'es' : ''} beat the baseline (${metricName} ${fmt(baseVal)}), so the baseline stands as the strongest model.`;
    } else {
      completionSummary = `The best approach reached ${metricName} ${fmt(bestExp.metricValue)}.`;
    }
  }

  const progressItems = [
    { key: 'literature_search', label: 'Looking at existing research', state: stageStates.literature_search },
    { key: 'dataset_eda', label: 'Understanding the data', state: stageStates.dataset_eda },
    { key: 'baseline_training', label: 'Building the first model', state: stageStates.baseline_training },
    { key: 'hypothesis_generation', label: 'Trying different research ideas', state: stageStates.hypothesis_generation },
    { key: 'error_diagnostics', label: 'Finding where models make mistakes', state: stageStates.error_diagnostics },
    { key: 'research_report', label: 'Preparing final findings', state: stageStates.research_report }
  ];

  return (
    <div className="flex-1 flex flex-col h-screen bg-[#0B0F17] overflow-hidden select-none">
      
      {/* Top Header */}
      <header className="h-14 border-b border-[#1E293B] bg-[#0D111A] px-6 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <button 
            onClick={onNewResearch}
            className="text-slate-400 hover:text-slate-200 transition-colors p-1.5 rounded-lg hover:bg-[#161B26]"
            title="New Research Chat"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path d="M19 12H5M12 19l-7-7 7-7" />
            </svg>
          </button>

          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold text-slate-100 flex items-center gap-2 font-sans">
              <span>AI Scientist</span>
              {activeProject && (
                <span className={`text-[11px] font-medium px-2.5 py-0.5 rounded-full border ${
                  isCompleted 
                    ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                    : 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30 animate-pulse'
                }`}>
                  {isCompleted ? '✓ Research Complete' : '● Active Study'}
                </span>
              )}
            </h2>
          </div>
        </div>

        {/* Header Actions */}
        <div className="flex items-center gap-3">
          {activeProject && (
            <div className="flex items-center gap-1 bg-[#131822] p-1 rounded-xl border border-[#212B3B] text-xs font-medium">
              <button
                onClick={() => setActiveTab('research')}
                className={`px-3 py-1 rounded-lg transition-all ${
                  activeTab === 'research'
                    ? 'bg-[#1E293B] text-cyan-400 font-semibold shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Conversation
              </button>
              <button
                onClick={() => setActiveTab('report')}
                className={`px-3 py-1 rounded-lg transition-all ${
                  activeTab === 'report'
                    ? 'bg-[#1E293B] text-cyan-400 font-semibold shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Research Report {reportMd ? '📄' : ''}
              </button>
            </div>
          )}

          <button
            onClick={() => setShowTechnicalDetails(!showTechnicalDetails)}
            className="text-xs font-medium px-3 py-1.5 rounded-xl bg-[#131822] border border-[#212B3B] text-slate-300 hover:text-cyan-400 transition-all flex items-center gap-1.5 cursor-pointer"
          >
            <span>{showTechnicalDetails ? '⚙ Hide Details' : '⚙ View Details'}</span>
          </button>
        </div>
      </header>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        
        {/* COLLAPSIBLE TECHNICAL DETAILS PANEL */}
        {showTechnicalDetails && (
          <div className="bg-[#090D14] border-b border-[#1E293B] p-4 max-h-72 overflow-y-auto space-y-4 font-mono text-xs text-slate-300">
            <div className="flex items-center justify-between border-b border-[#1E293B] pb-2">
              <span className="font-bold text-cyan-400 uppercase text-[11px]">Telemetry & Technical Telemetry</span>
              <span className="text-slate-500 text-[10px]">Project ID: {projectId || 'None'}</span>
            </div>

            {activeProject ? (
              <>
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

                {baselines.length > 0 && (
                  <div className="space-y-1">
                    <div className="text-[10px] text-slate-400 font-semibold uppercase">Evaluated Model Architectures</div>
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
              </>
            ) : (
              <div className="text-slate-500 italic text-center py-2">
                No active project telemetry to display.
              </div>
            )}
          </div>
        )}

        {/* CONVERSATIONAL CHAT FEED */}
        {activeTab === 'research' && (
          <div className="flex-1 overflow-y-auto p-6 space-y-6 max-w-3xl mx-auto w-full font-sans">
            
            {/* INITIAL WELCOME MESSAGE IF BRAND NEW CHAT */}
            {chatMessages.length === 0 && !activeProject && (
              <div className="flex justify-start">
                <div className="w-full bg-[#121722] border border-[#1E293B] rounded-2xl p-6 shadow-xl space-y-4">
                  <div className="flex items-center gap-3 border-b border-[#1E293B]/70 pb-3">
                    <div className="w-8 h-8 rounded-xl bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400">
                      <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <circle cx="12" cy="12" r="3" />
                        <path d="M12 3a9 9 0 0 1 9 9" />
                        <path d="M12 21a9 9 0 0 1-9-9" />
                      </svg>
                    </div>
                    <div>
                      <h3 className="text-sm font-bold text-slate-100">AI Scientist</h3>
                      <p className="text-xs text-slate-400">Autonomous Machine Learning Assistant</p>
                    </div>
                  </div>
                  <p className="text-sm text-slate-200 leading-relaxed">
                    Hi! 👋 I'm AI Scientist, your autonomous research assistant.
                    What machine learning problem or dataset would you like me to investigate?
                  </p>
                </div>
              </div>
            )}

            {/* RENDER DYNAMIC CHAT MESSAGES */}
            {chatMessages.map((msg) => (
              <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                {msg.role === 'user' ? (
                  <div className="max-w-xl bg-[#161D2A] border border-[#263347] rounded-2xl p-4 shadow-md space-y-1">
                    <div className="text-[10px] font-semibold text-cyan-400 uppercase tracking-wider">You</div>
                    <p className="text-sm text-slate-100 font-sans leading-relaxed">{msg.content}</p>
                  </div>
                ) : (
                  <div className="w-full bg-[#121722] border border-[#1E293B] rounded-2xl p-5 shadow-xl space-y-4">
                    <div className="flex items-center gap-3 border-b border-[#1E293B]/70 pb-3">
                      <div className="w-7 h-7 rounded-xl bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400">
                        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <circle cx="12" cy="12" r="3" />
                          <path d="M12 3a9 9 0 0 1 9 9" />
                        </svg>
                      </div>
                      <h4 className="text-xs font-bold text-slate-100">AI Scientist</h4>
                    </div>

                    <div className="text-sm text-slate-200 leading-relaxed whitespace-pre-wrap">
                      {msg.content}
                    </div>

                    {msg.datasets && msg.datasets.length > 0 && (
                      <DatasetCards
                        datasets={msg.datasets}
                        recommendation={msg.recommendation}
                        researchQuery={msg.researchQuery}
                        onApprove={onApproveDataset}
                        isApproving={isApproving}
                      />
                    )}
                  </div>
                )}
              </div>
            ))}

            {/* ACTIVE RESEARCH PROGRESS BLOCK IF PROJECT IS RUNNING */}
            {activeProject && (
              <div className="w-full bg-[#121722] border border-[#1E293B] rounded-2xl p-5 shadow-xl space-y-4">
                
                {/* INLINE CONVERSATIONAL PROGRESS TRACKER */}
                <div className="bg-[#0B0F17] border border-[#1E293B] rounded-xl p-4 space-y-3">
                  <div className="flex items-center justify-between text-xs font-semibold text-slate-200 border-b border-[#1E293B] pb-2">
                    <span className="flex items-center gap-2">
                      <span>🔬</span>
                      <span>{isCompleted ? 'Research Completed' : 'Researching...'}</span>
                    </span>
                    {isRunning && <span className="text-cyan-400 animate-pulse text-[11px]">Executing...</span>}
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

                {/* STEP 1: DATASET ANALYSIS DISCOVERY */}
                {datasetReport && (
                  <div className="space-y-2 border-b border-[#1E293B]/60 pb-4 text-xs text-slate-300 leading-relaxed">
                    <p>
                      I've loaded the dataset{' '}
                      <span className="font-semibold text-slate-100">{datasetReport.repoId || datasetReport.filename}</span>.
                      It contains about{' '}
                      <span className="font-semibold text-slate-100">{(datasetReport.rowCount || 0).toLocaleString()}</span> records
                      with <span className="font-semibold text-slate-100">{(datasetReport.columnCount || 0) - 1}</span> features.
                    </p>
                    {datasetReport.targetCandidate && (
                      <p>
                        The thing I'm predicting is{' '}
                        <span className="font-semibold text-slate-100">{datasetReport.targetCandidate}</span>.
                        {datasetReport.minorityClassPct != null && (
                          <> The positive class makes up only{' '}
                            <span className="font-semibold text-amber-300">{datasetReport.minorityClassPct}%</span> of the data.</>
                        )}
                      </p>
                    )}
                    {datasetReport.isImbalanced && (
                      <p className="text-slate-400">
                        That's highly imbalanced, so plain accuracy would be misleading — I'll judge the models on
                        recall and PR-AUC instead.
                      </p>
                    )}
                    {(datasetReport.license || datasetReport.sourceUrl) && (
                      <p className="text-[11px] text-slate-500">
                        Source: {datasetReport.source || 'dataset'}
                        {datasetReport.license && <> · License: {datasetReport.license}</>}
                        {datasetReport.revision && <> · Version: {String(datasetReport.revision).slice(0, 8)}</>}
                      </p>
                    )}
                  </div>
                )}

                {/* STEP 2: BASELINE RESULTS CARD */}
                {bestBaseline && (
                  <div className="space-y-3 border-b border-[#1E293B]/60 pb-4">
                    <p className="text-xs text-slate-300">
                      I've tested the first models. The strongest starting point was{' '}
                      <span className="font-semibold text-slate-100">{bestBaseline.name}</span>.
                    </p>

                    <div className="bg-[#0B0F17] border border-[#1E293B] rounded-xl p-4 space-y-3">
                      <div className="text-xs font-semibold text-slate-300">First model results</div>
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center text-xs">
                        <MetricTile label="Precision" value={pct(bm.precision)} />
                        <MetricTile label="Recall" value={pct(bm.recall)} highlight />
                        <MetricTile label="F1 Score" value={pct(bm.f1)} />
                        <MetricTile label="PR-AUC" value={pct(bm.pr_auc)} />
                      </div>
                      {isFraudTask && (
                        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-center text-xs">
                          <MetricTile label="ROC-AUC" value={pct(bm.roc_auc)} />
                          <MetricTile label="False Positive Rate" value={pct(bm.fpr)} />
                          <MetricTile label="False Negative Rate" value={pct(bm.fnr)} />
                        </div>
                      )}
                      <div className="text-[11px] text-slate-400 pt-1 italic space-y-1">
                        <p>💡 <span className="font-medium text-slate-300">Recall</span> = how many of the actual fraud cases the model caught. <span className="font-medium text-slate-300">Precision</span> = how many of its fraud alerts were real.</p>
                        <p>Because fraud is rare here, plain accuracy would look deceptively high — so I focus on PR-AUC and recall instead.</p>
                      </div>
                    </div>
                  </div>
                )}

                {/* STEP 3: EXPERIMENTS */}
                {treeNodes.length > 1 && (
                  <div className="space-y-2 border-b border-[#1E293B]/60 pb-4 text-xs text-slate-300">
                    <p className="font-semibold text-slate-200">
                      I've tested {treeNodes.length - 1} additional research approaches:
                    </p>
                    <div className="space-y-1.5">
                      {treeNodes.filter(n => n.parentId !== null).map((node, idx) => (
                        <div key={node.id} className="p-3 rounded-xl bg-[#0B0F17] border border-[#1E293B] flex items-center justify-between">
                          <span>Approach #{idx + 1}: {node.title}</span>
                          <span className="text-emerald-400 font-semibold">{node.metricName} = {node.metricValue}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* FINAL COMPLETION SUMMARY */}
                {isCompleted && (
                  <div className="bg-[#0D1520] border border-cyan-500/30 rounded-xl p-4 space-y-3">
                    <p className="text-xs text-slate-200 leading-relaxed">
                      Research complete. {completionSummary} I've prepared the complete research report for you.
                    </p>
                    <div className="flex flex-wrap items-center gap-2 pt-1">
                      <button
                        onClick={() => setShowTechnicalDetails(true)}
                        className="px-3.5 py-1.5 rounded-xl bg-[#1A2232] hover:bg-[#253147] text-slate-200 border border-[#2B364A] font-semibold text-xs transition-all cursor-pointer"
                      >
                        🔍 View findings
                      </button>
                      <button
                        onClick={() => setActiveTab('report')}
                        className="px-3.5 py-1.5 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold text-xs shadow-md transition-all cursor-pointer"
                      >
                        📄 View report
                      </button>
                      <button
                        onClick={() => {
                          const input = document.querySelector('input[placeholder*="Ask AI Scientist"]');
                          if (input) input.focus();
                        }}
                        className="px-3.5 py-1.5 rounded-xl bg-[#131822] hover:bg-[#1C2536] text-slate-300 border border-[#212B3B] text-xs transition-all cursor-pointer"
                      >
                        💬 Ask a follow-up
                      </button>
                    </div>
                  </div>
                )}

              </div>
            )}

            <div ref={chatBottomRef} />
          </div>
        )}

        {/* TAB 2: REPORT VIEW */}
        {activeTab === 'report' && (
          <div className="flex-1 overflow-y-auto p-6 max-w-3xl mx-auto w-full">
            <div className="bg-[#131824] border border-[#212B3B] rounded-2xl p-6 space-y-4 shadow-xl">
              <div className="flex items-center justify-between border-b border-[#212B3B] pb-3">
                <h3 className="text-base font-bold text-slate-100 flex items-center gap-2 font-sans">
                  <span>📄</span> Scientific Research Report
                </h3>
                {reportMd && (
                  <a
                    href={`/api/projects/${projectId}/report/download?fmt=md`}
                    download={`Research_Report_${projectId}.md`}
                    className="px-3 py-1.5 rounded-lg bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 text-xs font-medium transition-all"
                  >
                    Download Markdown (.md)
                  </a>
                )}
              </div>

              {reportMd ? (
                <div className="prose prose-invert max-w-none text-xs text-slate-300 font-sans leading-relaxed bg-[#080C14] p-5 rounded-xl border border-[#1E293B] whitespace-pre-wrap">
                  {reportMd}
                </div>
              ) : (
                <div className="text-slate-500 italic text-xs py-8 text-center">
                  Compiling research report...
                </div>
              )}
            </div>
          </div>
        )}

        {/* BOTTOM CHAT INPUT BAR */}
        {activeTab === 'research' && (
          <div className="p-4 border-t border-[#1E293B] bg-[#0D111A] shrink-0">
            <form onSubmit={handleSendMessage} className="max-w-3xl mx-auto flex items-center gap-2">
              <input
                type="text"
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                placeholder="Ask AI Scientist anything (e.g. 'Hi', 'What is recall?', 'Improve credit-card fraud detection')"
                className="flex-1 bg-[#131822] border border-[#212B3B] focus:border-cyan-500/50 rounded-xl px-4 py-2.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none font-sans"
              />
              <button
                type="submit"
                disabled={!chatInput.trim() || isProcessing}
                className={`px-4 py-2.5 rounded-xl text-xs font-semibold transition-all ${
                  chatInput.trim() && !isProcessing
                    ? 'bg-cyan-500 text-slate-950 hover:bg-cyan-400 cursor-pointer'
                    : 'bg-[#1C2536] text-slate-600 cursor-not-allowed'
                }`}
              >
                {isProcessing ? 'Sending...' : 'Send'}
              </button>
            </form>
          </div>
        )}

      </div>
    </div>
  );
}

function DatasetCards({ datasets, recommendation, researchQuery, onApprove, isApproving }) {
  const recId = recommendation?.repoId;
  const fmtRows = (n) => (typeof n === 'number' ? n.toLocaleString() : null);

  return (
    <div className="space-y-3 pt-1">
      {datasets.map((d) => {
        const isRec = d.repoId === recId;
        const rows = fmtRows(d.rowCountPreview);
        return (
          <div
            key={d.repoId}
            className={`rounded-xl border p-4 space-y-2.5 transition-all ${
              isRec
                ? 'bg-[#0D1A20] border-cyan-500/40 shadow-md'
                : 'bg-[#0B0F17] border-[#1E293B]'
            }`}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-semibold text-slate-100 truncate">{d.repoId}</span>
                  {isRec && (
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-cyan-500/15 text-cyan-400 border border-cyan-500/30">
                      ★ Recommended
                    </span>
                  )}
                  {d.userSelected && (
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                      You linked this
                    </span>
                  )}
                </div>
                {d.description && (
                  <p className="text-[11px] text-slate-400 mt-1 line-clamp-2">{d.description}</p>
                )}
              </div>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-[11px]">
              <Meta label="Rows" value={rows || d.sizeCategory || '—'} />
              <Meta label="Features" value={d.featureCount != null ? d.featureCount : '—'} />
              <Meta label="Target" value={d.targetColumn || '—'} />
              <Meta label="License" value={d.license || 'unspecified'} />
              <Meta label="Format" value={d.format || '—'} />
              <Meta label="Splits" value={(d.splits && d.splits.length) ? d.splits.join(', ') : '—'} />
            </div>

            {d.minorityClassPct != null && (
              <div className="text-[11px] text-amber-300/90">
                Imbalanced: the positive class is only {d.minorityClassPct}% of records.
              </div>
            )}

            {d.reasons && d.reasons.length > 0 && (
              <ul className="space-y-0.5">
                {d.reasons.slice(0, 4).map((r, i) => (
                  <li key={i} className="text-[11px] text-slate-400 flex gap-1.5">
                    <span className="text-cyan-500">•</span>
                    <span>{r}</span>
                  </li>
                ))}
              </ul>
            )}

            <div className="flex items-center justify-between pt-1">
              <span className="text-[10px] text-slate-500">
                {(d.downloads != null) && `${d.downloads.toLocaleString()} downloads`}
                {(d.likes != null && d.likes > 0) && ` · ${d.likes} likes`}
              </span>
              <button
                onClick={() => onApprove && onApprove(d.repoId, researchQuery)}
                disabled={isApproving}
                className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                  isApproving
                    ? 'bg-[#1C2536] text-slate-500 cursor-not-allowed'
                    : isRec
                      ? 'bg-cyan-500 hover:bg-cyan-400 text-slate-950 cursor-pointer shadow-md'
                      : 'bg-[#1A2232] hover:bg-[#253147] text-slate-200 border border-[#2B364A] cursor-pointer'
                }`}
              >
                {isApproving ? 'Loading…' : 'Use this dataset'}
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function Meta({ label, value }) {
  return (
    <div className="p-2 rounded-lg bg-[#121722] border border-[#212B3B]">
      <div className="text-slate-500 text-[9px] uppercase tracking-wide">{label}</div>
      <div className="text-slate-200 font-medium truncate" title={String(value)}>{value}</div>
    </div>
  );
}

function MetricTile({ label, value, highlight }) {
  return (
    <div className="p-2.5 rounded-lg bg-[#121722] border border-[#212B3B]">
      <div className="text-slate-400 text-[10px]">{label}</div>
      <div className={`text-sm font-bold ${highlight ? 'text-cyan-400' : 'text-slate-100'}`}>{value}</div>
    </div>
  );
}
