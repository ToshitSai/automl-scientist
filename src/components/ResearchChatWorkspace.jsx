import React, { useState, useEffect } from 'react';
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
  const [activeTab, setActiveTab] = useState('feed'); // 'feed' | 'dataset' | 'baselines' | 'tree' | 'error_analysis' | 'literature' | 'report'
  const [datasetReport, setDatasetReport] = useState(null);
  const [baselines, setBaselines] = useState([]);
  const [treeNodes, setTreeNodes] = useState([]);
  const [errorAnalysis, setErrorAnalysis] = useState(null);
  const [literature, setLiterature] = useState([]);
  const [reportMd, setReportMd] = useState(null);
  const [showTechnicalDetails, setShowTechnicalDetails] = useState(false);
  const [selectedExpStdout, setSelectedExpStdout] = useState(null);

  const projectId = activeProject?.id;
  const isRunning = activeProject?.status === 'IN_PROGRESS' || activeProject?.status === 'QUEUED';
  const isPaused = activeProject?.status === 'PAUSED';
  const isStopped = activeProject?.status === 'STOPPED';
  const isCompleted = activeProject?.status === 'COMPLETED';
  const isFailed = activeProject?.status === 'FAILED';

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

  if (!activeProject) {
    return null;
  }

  const handleControl = async (signal) => {
    try {
      await sendControlSignal(projectId, signal);
    } catch (err) {
      alert("Control Signal Notice: " + err.message);
    }
  };

  const stageStates = activeProject.stageStates || {};

  return (
    <div className="flex-1 flex flex-col h-screen bg-[#0B0F17] overflow-hidden select-none">
      
      {/* Top Navigation & Status Bar */}
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
              <span className="truncate max-w-xs">{activeProject.name.replace(/^Research:\s*/, '')}</span>
              <span className={`text-[10px] font-mono px-2.5 py-0.5 rounded-full border font-semibold ${
                isCompleted 
                  ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                  : isPaused
                  ? 'bg-amber-500/10 text-amber-400 border-amber-500/30'
                  : isStopped || isFailed
                  ? 'bg-rose-500/10 text-rose-400 border-rose-500/30'
                  : 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30 animate-pulse'
              }`}>
                {isCompleted ? '✓ Research Complete' : isPaused ? '❚❚ Paused' : isStopped ? '■ Stopped' : isFailed ? '✕ Failed' : '● Researching'}
              </span>
            </h2>

            {/* Controls */}
            {(isRunning || isPaused) && (
              <div className="flex items-center gap-1.5 ml-2 font-mono text-[10px]">
                {isRunning && (
                  <button
                    onClick={() => handleControl('PAUSE')}
                    className="px-2.5 py-1 rounded bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/30 text-amber-400 transition-all font-sans"
                  >
                    Pause
                  </button>
                )}
                {isPaused && (
                  <button
                    onClick={() => handleControl('RUN')}
                    className="px-2.5 py-1 rounded bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/30 text-emerald-400 transition-all font-sans"
                  >
                    Resume
                  </button>
                )}
                <button
                  onClick={() => handleControl('STOP')}
                  className="px-2.5 py-1 rounded bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/30 text-rose-400 transition-all font-sans"
                >
                  Stop
                </button>
              </div>
            )}
          </div>
        </div>

        {/* View Switcher Tabs */}
        <div className="flex items-center gap-1 bg-[#131822] p-1 rounded-lg border border-[#212B3B] text-xs font-medium">
          {[
            { id: 'feed', label: 'AI Research Assistant' },
            { id: 'dataset', label: `EDA ${datasetReport ? `(${datasetReport.rowCount} rows)` : ''}` },
            { id: 'baselines', label: `Baselines (${baselines.length})` },
            { id: 'tree', label: `Tree Search (${treeNodes.length})` },
            { id: 'error_analysis', label: 'Error Analysis' },
            { id: 'literature', label: `Literature (${literature.length})` },
            { id: 'report', label: 'Report' }
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-3 py-1 rounded-md transition-all ${
                activeTab === tab.id
                  ? 'bg-[#1E293B] text-cyan-400 font-semibold shadow-sm'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-[#1A2232]'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </header>

      {/* Main Workspace Feed */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6 max-w-4xl mx-auto w-full">

        {/* ================= VIEW: FEED (Conversational AI Assistant Narrative) ================= */}
        {activeTab === 'feed' && (
          <div className="space-y-6">

            {/* USER REQUEST BUBBLE */}
            <div className="flex justify-end">
              <div className="max-w-2xl bg-[#161D2A] border border-[#263347] rounded-2xl p-4 shadow-lg space-y-2">
                <div className="text-[11px] font-mono text-cyan-400 uppercase tracking-wider font-semibold">
                  RESEARCH REQUEST
                </div>
                <p className="text-sm text-slate-100 leading-relaxed font-sans">
                  {activeProject.objective}
                </p>
                {activeProject.datasetName && (
                  <div className="flex items-center gap-2 pt-1 font-mono text-[11px] text-slate-400">
                    <span className="px-2 py-0.5 rounded bg-[#0F141F] border border-[#212B3B] text-slate-300">
                      📄 Dataset: {activeProject.datasetName}
                    </span>
                    <span className="px-2 py-0.5 rounded bg-[#0F141F] border border-[#212B3B] text-slate-300">
                      ⚙ Engine: {activeProject.llmProvider}
                    </span>
                  </div>
                )}
              </div>
            </div>

            {/* AUTOML SCIENTIST CONVERSATIONAL NARRATIVE STREAM */}
            <div className="flex justify-start">
              <div className="w-full bg-[#121722] border border-[#1E293B] rounded-2xl p-6 shadow-2xl space-y-6">
                
                {/* AI Assistant Avatar & Header */}
                <div className="flex items-center justify-between border-b border-[#1E293B] pb-4">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-xl bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400 shadow-md shadow-cyan-500/10">
                      <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <circle cx="12" cy="12" r="3" />
                        <path d="M12 3a9 9 0 0 1 9 9" />
                        <path d="M12 21a9 9 0 0 1-9-9" />
                      </svg>
                    </div>
                    <div>
                      <h3 className="text-sm font-bold text-slate-100">AutoML Scientist</h3>
                      <p className="text-xs text-slate-400">Autonomous Machine Learning Research Assistant</p>
                    </div>
                  </div>

                  <button
                    onClick={() => setShowTechnicalDetails(!showTechnicalDetails)}
                    className="text-xs font-mono px-3 py-1.5 rounded-lg bg-[#1A2232] border border-[#2B364A] text-slate-300 hover:text-cyan-400 transition-all flex items-center gap-1.5"
                  >
                    <span>{showTechnicalDetails ? '▼ Hide Technical Details' : '▶ View Technical Details'}</span>
                  </button>
                </div>

                {/* Collapsible Technical Details Panel */}
                {showTechnicalDetails && (
                  <div className="bg-[#090D14] border border-[#1E293B] rounded-xl p-4 font-mono text-xs text-slate-300 space-y-3">
                    <div className="text-[10px] text-slate-500 uppercase tracking-wider border-b border-[#1E293B] pb-1 font-bold">
                      Internal Engine Telemetry & Pipeline States
                    </div>
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px]">
                      {Object.entries(stageStates).map(([stageKey, status]) => (
                        <div key={stageKey} className="p-2 rounded bg-[#0D111A] border border-[#1E293B] truncate">
                          <span className="text-slate-500 block text-[9px] uppercase">{stageKey}</span>
                          <span className={status === 'COMPLETED' ? 'text-emerald-400 font-bold' : status === 'RUNNING' ? 'text-cyan-400 font-bold' : 'text-slate-400'}>
                            {status}
                          </span>
                        </div>
                      ))}
                    </div>
                    <div className="max-h-40 overflow-y-auto space-y-1 pt-2 border-t border-[#1E293B] text-[11px]">
                      <div className="text-[10px] text-slate-500 uppercase">Live Agent Log Stream</div>
                      {(activeProject.agentLogs || []).map((log, idx) => (
                        <div key={idx} className="flex items-start gap-2">
                          <span className="text-slate-600 shrink-0 text-[10px]">[{new Date(log.timestamp).toLocaleTimeString()}]</span>
                          <span className="text-cyan-400 shrink-0 font-bold">{log.agent}:</span>
                          <span className="text-slate-300">{log.message}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* NARRATIVE SECTION 1: RESEARCH INTENT & PLAN */}
                <div className="space-y-3 text-sm text-slate-200 leading-relaxed font-sans border-b border-[#1E293B]/60 pb-5">
                  <p className="font-medium text-slate-100 text-base">
                    Got it. I'll investigate how to {activeProject.name.replace(/^Research:\s*/, '').toLowerCase()}.
                  </p>
                  <p className="text-slate-300 text-sm">
                    Here is my research plan:
                  </p>
                  <ol className="list-decimal list-inside space-y-1.5 text-xs text-slate-300 bg-[#0F1420] p-3.5 rounded-xl border border-[#1C2536]">
                    <li>Analyze dataset structure, distributions, missing values, and class balance.</li>
                    <li>Review academic research for domain-specific feature engineering & models.</li>
                    <li>Train baseline benchmark models to set a starting performance reference.</li>
                    <li>Synthesize testable scientific hypotheses and execute sandboxed code.</li>
                    <li>Analyze error patterns (false positives & false negatives) to drive subsequent experiments.</li>
                    <li>Compile a final scientific research report with findings and recommendations.</li>
                  </ol>
                </div>

                {/* NARRATIVE SECTION 2: DATASET INSPECTION */}
                {datasetReport ? (
                  <div className="space-y-3 border-b border-[#1E293B]/60 pb-5">
                    <div className="flex items-center gap-2 text-xs font-mono text-cyan-400 uppercase tracking-wider font-semibold">
                      <span>✓ DATASET ANALYSIS COMPLETE</span>
                    </div>
                    <p className="text-sm text-slate-200 leading-relaxed">
                      I've finished analyzing your dataset (<span className="font-semibold text-slate-100">{datasetReport.filename}</span>). It contains <span className="font-bold text-slate-100">{datasetReport.rowCount.toLocaleString()}</span> rows and <span className="font-bold text-slate-100">{datasetReport.columnCount}</span> feature columns with primary target variable <span className="font-bold text-cyan-400">{datasetReport.targetCandidate}</span>.
                    </p>

                    {datasetReport.detectedIssues && datasetReport.detectedIssues.length > 0 && (
                      <div className="bg-[#17140B] border border-amber-500/30 rounded-xl p-3.5 text-xs text-amber-200 space-y-1.5">
                        <div className="font-bold text-amber-400 flex items-center gap-1.5">
                          <span>⚠️ Key Dataset Finding</span>
                        </div>
                        {datasetReport.detectedIssues.map((issue, idx) => (
                          <p key={idx} className="leading-relaxed text-amber-200/90">
                            • <span className="font-semibold">{issue.title}:</span> {issue.desc}
                          </p>
                        ))}
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="flex items-center gap-2 text-xs font-mono text-cyan-400 animate-pulse border-b border-[#1E293B]/60 pb-5">
                    <span>● Analyzing dataset structure & distributions...</span>
                  </div>
                )}

                {/* NARRATIVE SECTION 3: BASELINE MODELS */}
                {baselines.length > 0 ? (
                  <div className="space-y-3 border-b border-[#1E293B]/60 pb-5">
                    <div className="flex items-center gap-2 text-xs font-mono text-emerald-400 uppercase tracking-wider font-semibold">
                      <span>✓ BASELINE BENCHMARK COMPLETE</span>
                    </div>
                    <p className="text-sm text-slate-200 leading-relaxed">
                      I've trained <span className="font-bold text-slate-100">{baselines.length}</span> baseline models to establish our reference performance benchmarks.
                    </p>
                    <div className="bg-[#0F1420] border border-[#1C2536] rounded-xl p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                      <div>
                        <div className="text-[10px] font-mono text-slate-400 uppercase">Top Performing Baseline</div>
                        <div className="text-sm font-bold text-slate-100">{activeProject.bestModel}</div>
                      </div>
                      <div className="text-right">
                        <div className="text-[10px] font-mono text-slate-400 uppercase">Benchmark Metric</div>
                        <div className="text-sm font-bold text-emerald-400 font-mono">{activeProject.bestMetric}</div>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-center gap-2 text-xs font-mono text-slate-400 border-b border-[#1E293B]/60 pb-5">
                    <span>{stageStates.baseline_training === 'RUNNING' ? '● Training baseline benchmark models...' : 'Waiting for baseline training stage...'}</span>
                  </div>
                )}

                {/* NARRATIVE SECTION 4: AUTONOMOUS EXPERIMENT ITERATIONS */}
                {treeNodes.length > 1 && (
                  <div className="space-y-4 border-b border-[#1E293B]/60 pb-5">
                    <div className="text-xs font-mono text-cyan-400 uppercase tracking-wider font-semibold">
                      🧪 AUTONOMOUS EXPERIMENTS & ITERATIONS
                    </div>

                    {treeNodes.filter(n => n.parentId !== null).map((node, idx) => (
                      <div key={node.id} className="bg-[#0F1420] border border-[#1C2536] rounded-xl p-4 space-y-3">
                        <div className="flex items-center justify-between border-b border-[#1C2536] pb-2">
                          <h4 className="text-xs font-bold text-slate-100">
                            Experiment #{idx + 1}: {node.title}
                          </h4>
                          <span className={`text-[10px] font-mono px-2 py-0.5 rounded font-bold ${
                            node.status === 'IMPROVED' ? 'bg-emerald-950 text-emerald-400 border border-emerald-500/30' :
                            node.status === 'PLATEAUED' ? 'bg-amber-950 text-amber-400 border border-amber-500/30' :
                            'bg-rose-950 text-rose-400 border border-rose-500/30'
                          }`}>
                            {node.status === 'IMPROVED' ? '✓ Improved Metric' : node.status === 'PLATEAUED' ? '❚ Plateaued' : '✕ Failed'}
                          </span>
                        </div>

                        <div className="space-y-1.5 text-xs text-slate-300 font-sans">
                          <p><span className="font-semibold text-slate-200">What I tested:</span> "{node.hypothesis}"</p>
                          <p><span className="font-semibold text-slate-200">Result:</span> Achieved <span className="font-mono font-bold text-cyan-400">{node.metricName} = {node.metricValue}</span> in <span className="font-mono text-slate-400">{node.executionTime}</span>.</p>
                        </div>

                        {/* Collapsible Sandboxed Output */}
                        {(node.stdout || node.stderr) && (
                          <div className="pt-1">
                            <button
                              onClick={() => setSelectedExpStdout(selectedExpStdout === node.id ? null : node.id)}
                              className="text-[11px] font-mono text-cyan-400 hover:underline flex items-center gap-1"
                            >
                              <span>{selectedExpStdout === node.id ? '▼ Hide Console Logs' : '▶ View Sandboxed Console Logs'}</span>
                            </button>

                            {selectedExpStdout === node.id && (
                              <div className="mt-2 bg-[#080B12] p-3 rounded-lg border border-[#1E293B] font-mono text-[11px] text-slate-300 max-h-40 overflow-y-auto">
                                {node.stdout && <div><span className="text-emerald-400">[STDOUT]</span> {node.stdout}</div>}
                                {node.stderr && <div className="text-rose-400 mt-1"><span className="text-rose-500">[STDERR]</span> {node.stderr}</div>}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}

                {/* NARRATIVE SECTION 5: FINAL RESEARCH REPORT SUMMARY */}
                {isCompleted && reportMd && (
                  <div className="bg-[#0D1520] border border-cyan-500/30 rounded-xl p-5 space-y-4">
                    <div className="flex items-center justify-between border-b border-[#1E293B] pb-3">
                      <div className="flex items-center gap-2">
                        <span className="text-xl">📄</span>
                        <div>
                          <h4 className="text-sm font-bold text-slate-100">Research Complete & Report Compiled</h4>
                          <p className="text-xs text-slate-400">All autonomous hypothesis generation and experiments finished</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <a
                          href={`/api/projects/${projectId}/report/download?fmt=md`}
                          download={`Research_Report_${projectId}.md`}
                          className="px-3 py-1.5 rounded bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 text-xs font-mono font-medium transition-all"
                        >
                          Download Markdown (.md)
                        </a>
                        <a
                          href={`/api/projects/${projectId}/report/download?fmt=json`}
                          download={`Research_Report_${projectId}.json`}
                          className="px-3 py-1.5 rounded bg-[#1C2536] hover:bg-[#253147] text-slate-300 border border-[#2B364A] text-xs font-mono font-medium transition-all"
                        >
                          Download JSON
                        </a>
                      </div>
                    </div>

                    <div className="prose prose-invert max-w-none text-xs text-slate-300 font-sans leading-relaxed bg-[#080C14] p-4 rounded-xl border border-[#1E293B] max-h-96 overflow-y-auto whitespace-pre-wrap">
                      {reportMd}
                    </div>
                  </div>
                )}

              </div>
            </div>

          </div>
        )}

        {/* ================= VIEW: DATASET EDA ================= */}
        {activeTab === 'dataset' && (
          <div className="bg-[#131824] border border-[#212B3B] rounded-xl p-6 space-y-6">
            <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
              <span>📊</span> Dataset Exploratory Data Analysis & Quality Inspection
            </h3>

            {datasetReport ? (
              <div className="space-y-6 font-mono text-xs">
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                  <div className="bg-[#0D111A] p-4 rounded-xl border border-[#1E293B]">
                    <div className="text-slate-500 text-[10px]">FILENAME</div>
                    <div className="text-sm font-bold text-cyan-400">{datasetReport.filename}</div>
                  </div>
                  <div className="bg-[#0D111A] p-4 rounded-xl border border-[#1E293B]">
                    <div className="text-slate-500 text-[10px]">ROW COUNT</div>
                    <div className="text-sm font-bold text-slate-100">{datasetReport.rowCount.toLocaleString()}</div>
                  </div>
                  <div className="bg-[#0D111A] p-4 rounded-xl border border-[#1E293B]">
                    <div className="text-slate-500 text-[10px]">COLUMN COUNT</div>
                    <div className="text-sm font-bold text-slate-100">{datasetReport.columnCount}</div>
                  </div>
                  <div className="bg-[#0D111A] p-4 rounded-xl border border-[#1E293B]">
                    <div className="text-slate-500 text-[10px]">TARGET COLUMN</div>
                    <div className="text-sm font-bold text-cyan-400 truncate">{datasetReport.targetCandidate}</div>
                  </div>
                </div>

                {/* Detected Issues */}
                {datasetReport.detectedIssues && datasetReport.detectedIssues.length > 0 && (
                  <div className="space-y-2">
                    <h4 className="text-xs font-bold text-slate-200">Data Quality & Imbalance Diagnostics</h4>
                    {datasetReport.detectedIssues.map((issue, idx) => (
                      <div key={idx} className="p-3 rounded-lg bg-amber-950/20 border border-amber-500/30 text-amber-300 text-xs flex items-start gap-2.5">
                        <span className="font-bold text-[10px] uppercase px-2 py-0.5 rounded bg-amber-900/50">
                          {issue.severity}
                        </span>
                        <div>
                          <div className="font-semibold text-slate-100">{issue.title}</div>
                          <div className="text-amber-200/90 text-[11px] mt-0.5">{issue.desc}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <div className="text-slate-500 italic text-sm">No dataset report available for this project yet.</div>
            )}
          </div>
        )}

        {/* ================= VIEW: BASELINES ================= */}
        {activeTab === 'baselines' && (
          <div className="bg-[#131824] border border-[#212B3B] rounded-xl p-6 space-y-4">
            <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
              <span>🤖</span> Baseline Benchmark Models
            </h3>

            {baselines.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-mono">
                  <thead>
                    <tr className="text-[10px] text-slate-500 border-b border-[#212B3B] uppercase">
                      <th className="py-2.5 px-3">Model</th>
                      <th className="py-2.5 px-3">Type</th>
                      <th className="py-2.5 px-3">Metrics</th>
                      <th className="py-2.5 px-3">Runtime</th>
                      <th className="py-2.5 px-3">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#212B3B]/50">
                    {baselines.map((b) => (
                      <tr key={b.id} className="hover:bg-[#1D2433]">
                        <td className="py-3 px-3 font-semibold text-slate-200">{b.name}</td>
                        <td className="py-3 px-3 text-slate-400">{b.type}</td>
                        <td className="py-3 px-3 text-cyan-400">
                          {Object.entries(b.metrics || {}).map(([k, v]) => `${k.toUpperCase()}: ${v}`).join(' | ')}
                        </td>
                        <td className="py-3 px-3 text-slate-400">{b.trainingTime}</td>
                        <td className="py-3 px-3">
                          <span className={`px-2 py-0.5 rounded text-[10px] ${b.status === 'COMPLETED' ? 'bg-emerald-950 text-emerald-400 border border-emerald-500/30' : 'bg-rose-950 text-rose-400'}`}>
                            {b.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="text-slate-500 italic text-sm">No baseline models trained yet.</div>
            )}
          </div>
        )}

        {/* ================= VIEW: EXPERIMENT TREE ================= */}
        {activeTab === 'tree' && (
          <div className="bg-[#131824] border border-[#212B3B] rounded-xl p-6 space-y-4">
            <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
              <span>🌱</span> Autonomous Research Experiment Tree
            </h3>

            {treeNodes.length > 0 ? (
              <div className="space-y-3 font-mono text-xs">
                {treeNodes.map((node) => (
                  <div key={node.id} className="bg-[#0D111A] p-4 rounded-xl border border-[#1E293B] space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="font-bold text-slate-200">{node.title}</div>
                      <span className="text-[10px] px-2 py-0.5 rounded bg-[#161D2A] text-cyan-400 border border-[#263347]">
                        {node.status}
                      </span>
                    </div>
                    <div className="text-slate-400 text-[11px]">Hypothesis: "{node.hypothesis}"</div>
                    <div className="text-cyan-400 text-xs">Metric: {node.metricName} = {node.metricValue}</div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-slate-500 italic text-sm">No experiment tree nodes created yet.</div>
            )}
          </div>
        )}

        {/* ================= VIEW: ERROR ANALYSIS ================= */}
        {activeTab === 'error_analysis' && (
          <div className="bg-[#131824] border border-[#212B3B] rounded-xl p-6 space-y-4">
            <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
              <span>🔍</span> Error Diagnostics & Failure Slice Analysis
            </h3>

            {errorAnalysis ? (
              <div className="space-y-4 font-mono text-xs">
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-[#0D111A] p-4 rounded-xl border border-[#1E293B]">
                    <div className="text-slate-500 text-[10px]">FALSE POSITIVES (FALSE ALARMS)</div>
                    <div className="text-lg font-bold text-amber-400">{errorAnalysis.falsePositives}</div>
                  </div>
                  <div className="bg-[#0D111A] p-4 rounded-xl border border-[#1E293B]">
                    <div className="text-slate-500 text-[10px]">FALSE NEGATIVES (MISSED CASES)</div>
                    <div className="text-lg font-bold text-rose-400">{errorAnalysis.falseNegatives}</div>
                  </div>
                </div>
                <div className="bg-[#0D111A] p-4 rounded-xl border border-[#1E293B] space-y-2">
                  <div className="font-bold text-slate-200">Failure Diagnostics & Insights</div>
                  <p className="text-slate-300 font-sans text-xs leading-relaxed">{errorAnalysis.failureDiagnosis}</p>
                </div>
              </div>
            ) : (
              <div className="text-slate-500 italic text-sm">No error diagnostics performed yet.</div>
            )}
          </div>
        )}

        {/* ================= VIEW: LITERATURE ================= */}
        {activeTab === 'literature' && (
          <div className="bg-[#131824] border border-[#212B3B] rounded-xl p-6 space-y-4">
            <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
              <span>📚</span> Academic Literature Search
            </h3>

            {literature.length > 0 ? (
              <div className="space-y-3 font-sans text-xs">
                {literature.map((paper, idx) => (
                  <div key={idx} className="bg-[#0D111A] p-4 rounded-xl border border-[#1E293B] space-y-2">
                    <a href={paper.url} target="_blank" rel="noopener noreferrer" className="font-bold text-cyan-400 hover:underline text-sm block">
                      {paper.title}
                    </a>
                    <div className="text-slate-400 text-[11px] font-mono">Authors: {paper.authors} ({paper.year})</div>
                    <p className="text-slate-300 leading-relaxed">{paper.abstract}</p>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-slate-500 italic text-sm">No literature search papers found or API is unconfigured.</div>
            )}
          </div>
        )}

        {/* ================= VIEW: REPORT ================= */}
        {activeTab === 'report' && (
          <div className="bg-[#131824] border border-[#212B3B] rounded-xl p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-[#212B3B] pb-3">
              <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
                <span>📄</span> Scientific Research Paper
              </h3>
              {reportMd && (
                <div className="flex items-center gap-2">
                  <a
                    href={`/api/projects/${projectId}/report/download?fmt=md`}
                    download={`Research_Report_${projectId}.md`}
                    className="px-3 py-1 rounded bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 text-xs font-mono font-medium transition-all"
                  >
                    Download Markdown
                  </a>
                  <a
                    href={`/api/projects/${projectId}/report/download?fmt=json`}
                    download={`Research_Report_${projectId}.json`}
                    className="px-3 py-1 rounded bg-[#1C2536] hover:bg-[#253147] text-slate-300 border border-[#2B364A] text-xs font-mono font-medium transition-all"
                  >
                    Download JSON
                  </a>
                </div>
              )}
            </div>

            {reportMd ? (
              <div className="prose prose-invert max-w-none text-xs text-slate-300 font-sans leading-relaxed bg-[#080C14] p-5 rounded-xl border border-[#1E293B] whitespace-pre-wrap">
                {reportMd}
              </div>
            ) : (
              <div className="text-slate-500 italic text-sm">Report compilation in progress...</div>
            )}
          </div>
        )}

      </div>
    </div>
  );
}
