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
  const [showLogs, setShowLogs] = useState(false);
  const [selectedExpStdout, setSelectedExpStdout] = useState(null);

  const projectId = activeProject?.id;
  const isRunning = activeProject?.status === 'IN_PROGRESS' || activeProject?.status === 'QUEUED';
  const isPaused = activeProject?.status === 'PAUSED';
  const isStopped = activeProject?.status === 'STOPPED';

  useEffect(() => {
    if (!projectId) return;

    const loadData = async () => {
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
      alert("Error sending control signal: " + err.message);
    }
  };

  const getProgressSteps = () => {
    const stageStates = activeProject.stageStates || {};
    const getStageStatus = (key) => stageStates[key] || 'NOT_STARTED';

    return [
      { key: "research_question", label: "Research Question", state: getStageStatus("research_question") },
      { key: "literature_search", label: "Literature Search", state: getStageStatus("literature_search") },
      { key: "dataset_eda", label: "Dataset EDA", state: getStageStatus("dataset_eda") },
      { key: "baseline_training", label: "Baseline Training", state: getStageStatus("baseline_training") },
      { key: "hypothesis_generation", label: "Hypothesis & Coding", state: getStageStatus("hypothesis_generation") },
      { key: "sandboxed_execution", label: "Sandboxed Execution", state: getStageStatus("sandboxed_execution") },
      { key: "error_diagnostics", label: "Error Diagnostics", state: getStageStatus("error_diagnostics") },
      { key: "research_report", label: "Research Report", state: getStageStatus("research_report") }
    ];
  };

  const steps = getProgressSteps();

  return (
    <div className="flex-1 flex flex-col h-screen bg-[#0B0F17] overflow-hidden select-none">
      
      {/* Top Header Bar */}
      <header className="h-14 border-b border-[#1E293B] bg-[#0D111A] px-6 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <button 
            onClick={onNewResearch}
            className="text-slate-400 hover:text-slate-200 transition-colors p-1 rounded-md hover:bg-[#161B26]"
            title="Start New Research"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path d="M19 12H5M12 19l-7-7 7-7" />
            </svg>
          </button>

          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
              <span className="truncate max-w-xs">{activeProject.name.replace(/^Research:\s*/, '')}</span>
              <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full border ${
                activeProject.status === 'COMPLETED' 
                  ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                  : activeProject.status === 'PAUSED'
                  ? 'bg-amber-500/10 text-amber-400 border-amber-500/30'
                  : activeProject.status === 'STOPPED' || activeProject.status === 'FAILED'
                  ? 'bg-rose-500/10 text-rose-400 border-rose-500/30'
                  : 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30 animate-pulse'
              }`}>
                {activeProject.status === 'COMPLETED' ? '✓ COMPLETED' : activeProject.status === 'PAUSED' ? '❚❚ PAUSED' : activeProject.status === 'STOPPED' ? '■ STOPPED' : activeProject.status === 'FAILED' ? '✕ FAILED' : '● RUNNING'}
              </span>
            </h2>

            {/* Interactive Stop / Pause / Resume Controls */}
            {(isRunning || isPaused) && (
              <div className="flex items-center gap-1.5 ml-2 font-mono text-[10px]">
                {isRunning && (
                  <button
                    onClick={() => handleControl('PAUSE')}
                    className="px-2 py-0.5 rounded bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/30 text-amber-400 transition-all"
                  >
                    Pause
                  </button>
                )}
                {isPaused && (
                  <button
                    onClick={() => handleControl('RUN')}
                    className="px-2 py-0.5 rounded bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/30 text-emerald-400 transition-all"
                  >
                    Resume
                  </button>
                )}
                <button
                  onClick={() => handleControl('STOP')}
                  className="px-2 py-0.5 rounded bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/30 text-rose-400 transition-all"
                >
                  Stop
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Secondary View Tab Selectors */}
        <div className="flex items-center gap-1 bg-[#131822] p-1 rounded-lg border border-[#212B3B] text-xs font-medium">
          {[
            { id: 'feed', label: 'Research Workspace' },
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

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6 max-w-5xl mx-auto w-full">

        {/* ================= VIEW: FEED (Sakana Chat Workspace Stream) ================= */}
        {activeTab === 'feed' && (
          <div className="space-y-6">

            {/* USER MESSAGE BUBBLE */}
            <div className="flex justify-end">
              <div className="max-w-2xl bg-[#161D2A] border border-[#263347] rounded-2xl p-4 shadow-lg space-y-2">
                <div className="text-xs font-mono text-cyan-400 uppercase tracking-wider font-semibold">
                  USER RESEARCH OBJECTIVE
                </div>
                <p className="text-sm text-slate-100 font-sans leading-relaxed">
                  {activeProject.objective}
                </p>

                <div className="flex flex-wrap items-center gap-2 pt-1 font-mono text-[11px] text-slate-400">
                  <span className="px-2 py-0.5 rounded bg-[#0F141F] border border-[#212B3B] text-slate-300">
                    📊 Dataset: {activeProject.datasetName}
                  </span>
                  <span className="px-2 py-0.5 rounded bg-[#0F141F] border border-[#212B3B] text-slate-300">
                    ⚙ Engine: {activeProject.llmProvider}
                  </span>
                  <span className="px-2 py-0.5 rounded bg-[#0F141F] border border-[#212B3B] text-slate-300">
                    ⏱ Budget: {activeProject.computeUsed}
                  </span>
                  <span className="px-2 py-0.5 rounded bg-[#0F141F] border border-[#212B3B] text-slate-300">
                    🧪 Max Exps: {activeProject.maxExperiments || 5}
                  </span>
                </div>
              </div>
            </div>

            {/* AUTOML SCIENTIST RESPONSE STREAM */}
            <div className="flex justify-start">
              <div className="w-full bg-[#121722] border border-[#1E293B] rounded-2xl p-5 shadow-2xl space-y-6">
                
                {/* Agent Header */}
                <div className="flex items-center justify-between border-b border-[#1E293B] pb-3">
                  <div className="flex items-center gap-2.5">
                    <div className="w-7 h-7 rounded-lg bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400">
                      <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <circle cx="12" cy="12" r="3" />
                        <path d="M12 3a9 9 0 0 1 9 9" />
                        <path d="M12 21a9 9 0 0 1-9-9" />
                      </svg>
                    </div>
                    <div>
                      <h3 className="text-xs font-bold text-slate-100">AutoML Scientist Engine</h3>
                      <p className="text-[10px] font-mono text-slate-500">Autonomous Multi-Step Iterative Loop</p>
                    </div>
                  </div>

                  <button
                    onClick={() => setShowLogs(!showLogs)}
                    className="text-xs font-mono px-2.5 py-1 rounded bg-[#1A2232] border border-[#2B364A] text-slate-300 hover:text-cyan-400 transition-all flex items-center gap-1.5"
                  >
                    <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping"></span>
                    {showLogs ? 'Hide Live Logs' : 'View Live Logs'}
                  </button>
                </div>

                {/* Live Activity Log Drawer */}
                {showLogs && (
                  <div className="bg-[#090D14] border border-[#1E293B] rounded-xl p-3 font-mono text-xs text-slate-300 max-h-48 overflow-y-auto space-y-1">
                    <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-2 border-b border-[#1E293B] pb-1">
                      Live Telemetry & Agent Stream
                    </div>
                    {(activeProject.agentLogs || []).map((log, idx) => (
                      <div key={idx} className="flex items-start gap-2">
                        <span className="text-slate-600 shrink-0 text-[10px]">[{new Date(log.timestamp).toLocaleTimeString()}]</span>
                        <span className="text-cyan-400 shrink-0 font-bold">{log.agent}:</span>
                        <span className="text-slate-300">{log.message}</span>
                      </div>
                    ))}
                  </div>
                )}

                {/* Compact Inline Research Progress Indicator */}
                <div className="bg-[#0B0F17] border border-[#1C2536] rounded-xl p-4">
                  <div className="text-[11px] font-mono uppercase tracking-wider text-slate-400 mb-3 font-semibold">
                    Autonomous Pipeline Execution Status
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                    {steps.map((step) => {
                      const isDone = step.state === 'COMPLETED';
                      const isRunning = step.state === 'RUNNING';
                      const isNotConfigured = step.state === 'NOT_CONFIGURED';
                      const isFailed = step.state === 'FAILED';

                      return (
                        <div 
                          key={step.key} 
                          className={`p-2 rounded-lg border text-xs font-mono flex items-center gap-2 ${
                            isDone
                              ? 'bg-emerald-950/20 border-emerald-500/30 text-emerald-400'
                              : isRunning
                              ? 'bg-cyan-950/30 border-cyan-500/40 text-cyan-400 animate-pulse'
                              : isNotConfigured
                              ? 'bg-slate-900/50 border-slate-700/50 text-slate-400'
                              : isFailed
                              ? 'bg-rose-950/20 border-rose-500/30 text-rose-400'
                              : 'bg-[#121722] border-[#1E293B] text-slate-600'
                          }`}
                        >
                          <span className="font-bold text-[11px]">
                            {isDone ? '✓' : isRunning ? '●' : isNotConfigured ? '⊘' : isFailed ? '✕' : '○'}
                          </span>
                          <div className="truncate">
                            <span className="block">{step.label}</span>
                            {isNotConfigured && <span className="block text-[9px] opacity-75">(Unconfigured)</span>}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* DATASET ANALYSIS CARD */}
                {datasetReport && (
                  <div className="bg-[#161B26] border border-[#212B3B] rounded-xl p-4 space-y-3">
                    <div className="flex items-center justify-between border-b border-[#212B3B] pb-2">
                      <div className="flex items-center gap-2">
                        <span className="text-lg">📊</span>
                        <h4 className="text-xs font-bold text-slate-200">Dataset Inspection & Analysis</h4>
                      </div>
                      <span className="text-[10px] font-mono bg-cyan-950 text-cyan-300 px-2 py-0.5 rounded border border-cyan-800">
                        {datasetReport.taskType.toUpperCase()}
                      </span>
                    </div>

                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs font-mono">
                      <div className="bg-[#0D111A] p-2.5 rounded-lg border border-[#1E293B]">
                        <div className="text-[10px] text-slate-500">Rows</div>
                        <div className="text-sm font-bold text-slate-100">{datasetReport.rowCount.toLocaleString()}</div>
                      </div>
                      <div className="bg-[#0D111A] p-2.5 rounded-lg border border-[#1E293B]">
                        <div className="text-[10px] text-slate-500">Columns</div>
                        <div className="text-sm font-bold text-slate-100">{datasetReport.columnCount}</div>
                      </div>
                      <div className="bg-[#0D111A] p-2.5 rounded-lg border border-[#1E293B]">
                        <div className="text-[10px] text-slate-500">Target Feature</div>
                        <div className="text-sm font-bold text-cyan-400 truncate">{datasetReport.targetCandidate}</div>
                      </div>
                      <div className="bg-[#0D111A] p-2.5 rounded-lg border border-[#1E293B]">
                        <div className="text-[10px] text-slate-500">Missing / Duplicates</div>
                        <div className="text-sm font-bold text-slate-100">{datasetReport.missingValuesTotal} / {datasetReport.duplicateRows}</div>
                      </div>
                    </div>

                    {/* Detected Data Issues */}
                    {datasetReport.detectedIssues && datasetReport.detectedIssues.length > 0 && (
                      <div className="space-y-1.5 pt-1">
                        {datasetReport.detectedIssues.map((issue, idx) => (
                          <div key={idx} className="p-2 rounded bg-amber-950/20 border border-amber-500/30 text-amber-300 text-xs flex items-start gap-2">
                            <span className="font-bold text-[10px] uppercase px-1.5 py-0.5 rounded bg-amber-900/50">
                              {issue.severity}
                            </span>
                            <div>
                              <span className="font-semibold">{issue.title}: </span>
                              <span className="opacity-90">{issue.desc}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* BASELINE MODELS CARD */}
                {baselines.length > 0 && (
                  <div className="bg-[#161B26] border border-[#212B3B] rounded-xl p-4 space-y-3">
                    <div className="flex items-center justify-between border-b border-[#212B3B] pb-2">
                      <div className="flex items-center gap-2">
                        <span className="text-lg">🤖</span>
                        <h4 className="text-xs font-bold text-slate-200">Baseline Benchmark Training</h4>
                      </div>
                      <span className="text-xs font-mono text-emerald-400 font-semibold">
                        Best: {activeProject.bestModel} ({activeProject.bestMetric})
                      </span>
                    </div>

                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs font-mono">
                        <thead>
                          <tr className="text-[10px] text-slate-500 border-b border-[#212B3B] uppercase">
                            <th className="py-2">Model</th>
                            <th className="py-2">Type</th>
                            <th className="py-2">Metrics</th>
                            <th className="py-2">Runtime</th>
                            <th className="py-2">Status</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-[#212B3B]/50">
                          {baselines.map((b) => (
                            <tr key={b.id} className="hover:bg-[#1D2433]">
                              <td className="py-2 font-semibold text-slate-200">{b.name}</td>
                              <td className="py-2 text-slate-400">{b.type}</td>
                              <td className="py-2 text-cyan-400">
                                {Object.entries(b.metrics || {}).map(([k, v]) => `${k.toUpperCase()}: ${v}`).join(' | ')}
                              </td>
                              <td className="py-2 text-slate-400">{b.trainingTime}</td>
                              <td className="py-2">
                                <span className={`px-2 py-0.5 rounded text-[10px] ${b.status === 'COMPLETED' ? 'bg-emerald-950 text-emerald-400' : 'bg-rose-950 text-rose-400'}`}>
                                  {b.status}
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {/* EXPERIMENTS LIST CARDS */}
                {treeNodes.length > 1 && (
                  <div className="space-y-3">
                    <div className="text-xs font-bold text-slate-200 flex items-center gap-2">
                      <span>🧪</span> Autonomous Experiments & Sandboxed Executions
                    </div>

                    {treeNodes.filter(n => n.parentId !== null).map((node) => (
                      <div key={node.id} className="bg-[#161B26] border border-[#212B3B] rounded-xl p-4 space-y-3">
                        <div className="flex items-center justify-between border-b border-[#212B3B] pb-2">
                          <div>
                            <h5 className="text-xs font-bold text-slate-100">{node.title}</h5>
                            <p className="text-[11px] text-slate-400 italic mt-0.5">"{node.hypothesis}"</p>
                          </div>
                          <span className={`text-[10px] font-mono px-2 py-0.5 rounded font-bold ${
                            node.status === 'IMPROVED' ? 'bg-emerald-950 text-emerald-400 border border-emerald-500/30' :
                            node.status === 'PLATEAUED' ? 'bg-amber-950 text-amber-400 border border-amber-500/30' :
                            'bg-rose-950 text-rose-400 border border-rose-500/30'
                          }`}>
                            {node.status}
                          </span>
                        </div>

                        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs font-mono">
                          <div className="bg-[#0D111A] p-2.5 rounded-lg border border-[#1E293B]">
                            <div className="text-[10px] text-slate-500">Metric Result</div>
                            <div className="text-sm font-bold text-cyan-400">{node.metricName}: {node.metricValue}</div>
                          </div>
                          <div className="bg-[#0D111A] p-2.5 rounded-lg border border-[#1E293B]">
                            <div className="text-[10px] text-slate-500">Hyperparameters</div>
                            <div className="text-xs text-slate-300 truncate">{node.hyperparams}</div>
                          </div>
                          <div className="bg-[#0D111A] p-2.5 rounded-lg border border-[#1E293B]">
                            <div className="text-[10px] text-slate-500">Execution Runtime</div>
                            <div className="text-xs text-slate-300">{node.executionTime}</div>
                          </div>
                        </div>

                        {/* Stdout / Stderr Logs Toggle */}
                        {(node.stdout || node.stderr) && (
                          <div>
                            <button
                              onClick={() => setSelectedExpStdout(selectedExpStdout === node.id ? null : node.id)}
                              className="text-[11px] font-mono text-cyan-400 hover:underline flex items-center gap-1"
                            >
                              <span>{selectedExpStdout === node.id ? '▼ Hide Execution Output' : '▶ View Sandboxed Console Logs'}</span>
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

                {/* FINAL REPORT CARD */}
                {reportMd && activeProject.status === 'COMPLETED' && (
                  <div className="bg-[#161B26] border border-cyan-500/30 rounded-xl p-5 space-y-4">
                    <div className="flex items-center justify-between border-b border-[#212B3B] pb-3">
                      <div className="flex items-center gap-2">
                        <span className="text-xl">📄</span>
                        <h4 className="text-sm font-bold text-slate-100">Final Machine-Generated Research Report</h4>
                      </div>
                      <div className="flex items-center gap-2">
                        <a
                          href={`/api/projects/${projectId}/report/download?fmt=md`}
                          download={`Research_Report_${projectId}.md`}
                          className="px-3 py-1 rounded bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 text-xs font-mono font-medium transition-all"
                        >
                          Download Markdown (.md)
                        </a>
                        <a
                          href={`/api/projects/${projectId}/report/download?fmt=json`}
                          download={`Research_Report_${projectId}.json`}
                          className="px-3 py-1 rounded bg-[#1C2536] hover:bg-[#253147] text-slate-300 border border-[#2B364A] text-xs font-mono font-medium transition-all"
                        >
                          Download JSON
                        </a>
                      </div>
                    </div>

                    <div className="prose prose-invert max-w-none text-xs text-slate-300 font-sans leading-relaxed bg-[#0D111A] p-4 rounded-xl border border-[#1E293B] max-h-96 overflow-y-auto whitespace-pre-wrap">
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
                    <div className="text-slate-500 text-[10px]">RECORD COUNT</div>
                    <div className="text-sm font-bold text-slate-100">{datasetReport.rowCount.toLocaleString()}</div>
                  </div>
                  <div className="bg-[#0D111A] p-4 rounded-xl border border-[#1E293B]">
                    <div className="text-slate-500 text-[10px]">FEATURE COUNT</div>
                    <div className="text-sm font-bold text-slate-100">{datasetReport.columnCount}</div>
                  </div>
                  <div className="bg-[#0D111A] p-4 rounded-xl border border-[#1E293B]">
                    <div className="text-slate-500 text-[10px]">FILE SIZE</div>
                    <div className="text-sm font-bold text-slate-100">{datasetReport.fileSize}</div>
                  </div>
                </div>

                {/* Target Distribution Breakdown */}
                {datasetReport.classDistribution && (
                  <div className="bg-[#0D111A] p-4 rounded-xl border border-[#1E293B] space-y-3">
                    <div className="text-xs font-bold text-slate-200">Target Class Distribution (`{datasetReport.targetCandidate}`)</div>
                    <div className="space-y-2">
                      {datasetReport.classDistribution.map((item, idx) => (
                        <div key={idx} className="space-y-1">
                          <div className="flex justify-between text-slate-300 text-[11px]">
                            <span>Class Label `{item.label}`</span>
                            <span>{item.count} samples ({item.percentage}%)</span>
                          </div>
                          <div className="w-full bg-[#182030] h-2 rounded-full overflow-hidden">
                            <div 
                              className="bg-cyan-500 h-full transition-all" 
                              style={{ width: `${item.percentage}%` }}
                            ></div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-slate-500 italic text-center py-12 text-xs">Dataset analysis not executed yet.</div>
            )}
          </div>
        )}

        {/* ================= VIEW: BASELINES ================= */}
        {activeTab === 'baselines' && (
          <div className="bg-[#131824] border border-[#212B3B] rounded-xl p-6 space-y-6">
            <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
              <span>🤖</span> Baseline Models Evaluation & Benchmark Performance
            </h3>

            {baselines.length > 0 ? (
              <div className="space-y-4 font-mono text-xs">
                {baselines.map(b => (
                  <div key={b.id} className="bg-[#0D111A] p-4 rounded-xl border border-[#1E293B] space-y-2">
                    <div className="flex justify-between items-center">
                      <div className="font-bold text-sm text-slate-100">{b.name} <span className="text-slate-500 font-normal text-xs">({b.type})</span></div>
                      <span className="text-slate-400">Runtime: {b.trainingTime}</span>
                    </div>
                    <div className="text-cyan-400 text-xs">
                      {Object.entries(b.metrics || {}).map(([k, v]) => `${k.toUpperCase()}: ${v}`).join('  |  ')}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-slate-500 italic text-center py-12 text-xs">No baseline models trained yet.</div>
            )}
          </div>
        )}

        {/* ================= VIEW: EXPERIMENT TREE ================= */}
        {activeTab === 'tree' && (
          <div className="bg-[#131824] border border-[#212B3B] rounded-xl p-6 space-y-6">
            <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
              <span>🌳</span> Agentic Experimentation Tree Search
            </h3>

            <div className="space-y-4 font-mono text-xs">
              {treeNodes.map((node) => (
                <div key={node.id} className={`p-4 rounded-xl border ${node.parentId === null ? 'bg-[#182132] border-cyan-500/40' : 'bg-[#0D111A] border-[#1E293B] ml-6'}`}>
                  <div className="flex items-center justify-between">
                    <div className="font-bold text-sm text-slate-100">{node.title}</div>
                    <span className="px-2 py-0.5 rounded text-[10px] bg-cyan-950 text-cyan-300">{node.status}</span>
                  </div>
                  <p className="text-slate-400 italic text-xs mt-1">"{node.hypothesis}"</p>
                  <div className="mt-2 text-cyan-400">Metric: {node.metricName} = {node.metricValue}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ================= VIEW: ERROR ANALYSIS ================= */}
        {activeTab === 'error_analysis' && (
          <div className="bg-[#131824] border border-[#212B3B] rounded-xl p-6 space-y-6">
            <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
              <span>🔍</span> Statistical Prediction Error Diagnostics
            </h3>

            {errorAnalysis ? (
              <div className="space-y-4 font-mono text-xs">
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-[#0D111A] p-4 rounded-xl border border-[#1E293B]">
                    <div className="text-slate-500">False Positives</div>
                    <div className="text-lg font-bold text-rose-400">{errorAnalysis.falsePositivesCount}</div>
                  </div>
                  <div className="bg-[#0D111A] p-4 rounded-xl border border-[#1E293B]">
                    <div className="text-slate-500">False Negatives</div>
                    <div className="text-lg font-bold text-rose-400">{errorAnalysis.falseNegativesCount}</div>
                  </div>
                </div>

                <div className="bg-[#0D111A] p-4 rounded-xl border border-[#1E293B]">
                  <div className="text-xs font-bold text-slate-200 mb-2">Failure Diagnosis</div>
                  <p className="text-slate-300 leading-relaxed font-sans">{errorAnalysis.failureDiagnosis}</p>
                </div>
              </div>
            ) : (
              <div className="text-slate-500 italic text-center py-12 text-xs">Error diagnostics not performed yet.</div>
            )}
          </div>
        )}

        {/* ================= VIEW: LITERATURE ================= */}
        {activeTab === 'literature' && (
          <div className="bg-[#131824] border border-[#212B3B] rounded-xl p-6 space-y-6">
            <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
              <span>📚</span> Semantic Scholar Literature Search
            </h3>

            {literature.length > 0 ? (
              <div className="space-y-4 text-xs font-sans">
                {literature.map((paper, idx) => (
                  <div key={idx} className="bg-[#0D111A] p-4 rounded-xl border border-[#1E293B] space-y-2">
                    <a href={paper.url} target="_blank" rel="noopener noreferrer" className="font-bold text-sm text-cyan-400 hover:underline">
                      {paper.title} ({paper.year})
                    </a>
                    <div className="text-slate-400 font-mono text-[11px]">Authors: {paper.authors}</div>
                    <p className="text-slate-300 text-xs leading-relaxed">{paper.abstract}</p>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-slate-500 italic text-center py-12 text-xs">No literature papers fetched yet.</div>
            )}
          </div>
        )}

        {/* ================= VIEW: REPORT ================= */}
        {activeTab === 'report' && (
          <div className="bg-[#131824] border border-[#212B3B] rounded-xl p-6 space-y-6">
            <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
              <span>📄</span> Autonomous Research Paper & Scientific Report
            </h3>

            {reportMd ? (
              <div className="bg-[#0D111A] p-5 rounded-xl border border-[#1E293B] text-xs text-slate-300 whitespace-pre-wrap font-mono leading-relaxed max-h-[600px] overflow-y-auto">
                {reportMd}
              </div>
            ) : (
              <div className="text-slate-500 italic text-center py-12 text-xs">Research report not generated yet.</div>
            )}
          </div>
        )}

      </div>
    </div>
  );
}
