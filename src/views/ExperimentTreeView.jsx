import React, { useState } from 'react';
import { GitFork, CheckCircle2, AlertCircle, Sparkles, Terminal, Clock, Cpu } from 'lucide-react';
import { INITIAL_TREE_NODES } from '../mockData';

export default function ExperimentTreeView() {
  const [selectedNodeId, setSelectedNodeId] = useState('node-exp-1-1');

  const selectedNode = INITIAL_TREE_NODES.find((n) => n.id === selectedNodeId) || INITIAL_TREE_NODES[1];

  return (
    <div className="p-8 space-y-8 max-w-7xl mx-auto">
      <div className="space-y-2">
        <div className="inline-flex items-center space-x-2 bg-purple-500/10 border border-purple-500/30 px-3 py-1 rounded-full text-xs font-mono text-purple-300">
          <GitFork className="w-3.5 h-3.5" />
          <span>Directed Experiment Tree Visualization</span>
        </div>
        <h2 className="text-2xl font-extrabold text-white tracking-tight">
          Autonomous Research Hypothesis Tree
        </h2>
        <p className="text-slate-400 text-sm">
          Click any node in the directed experiment tree to inspect its hypothesis formulation, code changes, hyperparameters, stdout logs, metrics, and error conclusions.
        </p>
      </div>

      {/* Visual Tree Layout */}
      <div className="glass-panel p-8 rounded-xl space-y-8 border-purple-500/20 bg-slate-900/90 overflow-x-auto">
        {/* Root Node */}
        <div className="flex flex-col items-center">
          <div
            onClick={() => setSelectedNodeId('node-root')}
            className={`p-4 rounded-xl border cursor-pointer transition-all w-80 text-center space-y-2 ${
              selectedNodeId === 'node-root'
                ? 'bg-purple-950/60 border-purple-400 text-white shadow-lg shadow-purple-500/20 ring-2 ring-purple-500/40'
                : 'bg-slate-900 border-slate-700 text-slate-300 hover:border-slate-500'
            }`}
          >
            <div className="flex items-center justify-between text-xs">
              <span className="font-mono font-bold text-slate-400">Node #00 (Root)</span>
              <span className="bg-slate-800 text-emerald-400 px-2 py-0.5 rounded text-[10px] font-mono">
                PR-AUC: 0.841
              </span>
            </div>
            <h4 className="font-bold text-sm text-slate-100">XGBoost Raw Baseline</h4>
            <p className="text-[11px] text-slate-400 line-clamp-1">Establish raw dataset benchmark</p>
          </div>

          <div className="h-8 w-[2px] bg-purple-500/40 my-1"></div>

          {/* Level 1 Nodes */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 w-full max-w-4xl">
            {/* Exp 1 */}
            <div className="flex flex-col items-center">
              <div
                onClick={() => setSelectedNodeId('node-exp-1')}
                className={`p-4 rounded-xl border cursor-pointer transition-all w-full text-center space-y-2 ${
                  selectedNodeId === 'node-exp-1'
                    ? 'bg-purple-950/60 border-purple-400 text-white shadow-lg shadow-purple-500/20 ring-2 ring-purple-500/40'
                    : 'bg-slate-900 border-slate-700 text-slate-300 hover:border-slate-500'
                }`}
              >
                <div className="flex items-center justify-between text-xs">
                  <span className="font-mono font-bold text-slate-400">Node #01</span>
                  <span className="bg-slate-800 text-emerald-400 px-2 py-0.5 rounded text-[10px] font-mono">
                    PR-AUC: 0.862
                  </span>
                </div>
                <h4 className="font-bold text-sm text-slate-100">Class Weighting</h4>
                <p className="text-[11px] text-slate-400 line-clamp-1">scale_pos_weight = 577.8</p>
              </div>

              <div className="h-6 w-[2px] bg-purple-500/40 my-1"></div>

              {/* Exp 1.1 */}
              <div
                onClick={() => setSelectedNodeId('node-exp-1-1')}
                className={`p-4 rounded-xl border cursor-pointer transition-all w-full text-center space-y-2 ${
                  selectedNodeId === 'node-exp-1-1'
                    ? 'bg-cyan-950/80 border-cyan-400 text-white shadow-lg shadow-cyan-500/30 ring-2 ring-cyan-500/60'
                    : 'bg-slate-900 border-emerald-500/50 text-slate-300 hover:border-cyan-400'
                }`}
              >
                <div className="flex items-center justify-between text-xs">
                  <span className="font-mono font-bold text-cyan-300">Node #01.1 (BEST)</span>
                  <span className="bg-emerald-950 text-emerald-300 px-2 py-0.5 rounded text-[10px] font-mono font-bold border border-emerald-800">
                    PR-AUC: 0.884
                  </span>
                </div>
                <h4 className="font-bold text-sm text-cyan-100">Threshold Optimization</h4>
                <p className="text-[11px] text-slate-300 line-clamp-1">Pos Weight + Thresh 0.34</p>
              </div>
            </div>

            {/* Exp 2 */}
            <div className="flex flex-col items-center">
              <div
                onClick={() => setSelectedNodeId('node-exp-2')}
                className={`p-4 rounded-xl border cursor-pointer transition-all w-full text-center space-y-2 ${
                  selectedNodeId === 'node-exp-2'
                    ? 'bg-purple-950/60 border-purple-400 text-white shadow-lg shadow-purple-500/20 ring-2 ring-purple-500/40'
                    : 'bg-slate-900 border-slate-700 text-slate-300 hover:border-slate-500'
                }`}
              >
                <div className="flex items-center justify-between text-xs">
                  <span className="font-mono font-bold text-slate-400">Node #02</span>
                  <span className="bg-slate-800 text-slate-300 px-2 py-0.5 rounded text-[10px] font-mono">
                    PR-AUC: 0.849
                  </span>
                </div>
                <h4 className="font-bold text-sm text-slate-100">SMOTE Oversampling</h4>
                <p className="text-[11px] text-slate-400 line-clamp-1">k_neighbors=5 synth generation</p>
              </div>
            </div>

            {/* Exp 3 */}
            <div className="flex flex-col items-center">
              <div
                onClick={() => setSelectedNodeId('node-exp-3')}
                className={`p-4 rounded-xl border cursor-pointer transition-all w-full text-center space-y-2 ${
                  selectedNodeId === 'node-exp-3'
                    ? 'bg-purple-950/60 border-purple-400 text-white shadow-lg shadow-purple-500/20 ring-2 ring-purple-500/40'
                    : 'bg-slate-900 border-slate-700 text-slate-300 hover:border-slate-500'
                }`}
              >
                <div className="flex items-center justify-between text-xs">
                  <span className="font-mono font-bold text-slate-400">Node #03</span>
                  <span className="bg-slate-800 text-emerald-400 px-2 py-0.5 rounded text-[10px] font-mono">
                    PR-AUC: 0.858
                  </span>
                </div>
                <h4 className="font-bold text-sm text-slate-100">Isolation Forest Meta</h4>
                <p className="text-[11px] text-slate-400 line-clamp-1">Anomaly score feature insertion</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Selected Node Detailed Inspector */}
      {selectedNode && (
        <div className="glass-panel p-6 rounded-xl border border-cyan-500/40 space-y-4 bg-slate-900/95">
          <div className="flex items-center justify-between border-b border-slate-800 pb-4">
            <div className="flex items-center space-x-3">
              <span className="px-3 py-1 bg-cyan-950 text-cyan-300 text-xs font-mono font-bold rounded-lg border border-cyan-800">
                {selectedNode.id}
              </span>
              <h3 className="text-lg font-bold text-white">{selectedNode.title}</h3>
            </div>
            <div className="flex items-center space-x-4 text-xs font-mono">
              <span className="text-slate-400 flex items-center space-x-1">
                <Clock className="w-3.5 h-3.5" />
                <span>Runtime: {selectedNode.executionTime}</span>
              </span>
              <span className="text-emerald-400 font-bold bg-slate-950 px-3 py-1 rounded border border-slate-800">
                {selectedNode.metricName}: {selectedNode.metricValue}
              </span>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-3">
              <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider font-mono">
                Testable ML Hypothesis
              </h4>
              <p className="text-xs text-slate-200 bg-slate-950 p-3 rounded-lg border border-slate-800 font-mono leading-relaxed">
                &quot;{selectedNode.hypothesis}&quot;
              </p>

              <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider font-mono pt-2">
                Hyperparameters & Configuration
              </h4>
              <p className="text-xs text-cyan-300 bg-slate-950 p-3 rounded-lg border border-slate-800 font-mono">
                {selectedNode.hyperparams}
              </p>
            </div>

            <div className="space-y-3">
              <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider font-mono">
                Docker Sandbox Execution Output
              </h4>
              <pre className="text-[11px] text-slate-300 bg-slate-950 p-3 rounded-lg border border-slate-800 font-mono h-32 overflow-y-auto">
{`[INFO] Spawning Docker sandbox container...
[EXEC] python run_experiment.py --scale_pos_weight=577.8 --threshold=0.34
[TRAIN] XGBoost fit complete. Epochs: 250.
[METRICS] Validation F1: 0.842 | PR-AUC: 0.884 | ROC-AUC: 0.978
[STATUS] Node evaluated successfully. Saved model artifact: exp_01_1.json`}
              </pre>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
