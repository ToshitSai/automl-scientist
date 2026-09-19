import React, { useState, useEffect } from 'react';
import { GitFork, Clock, Loader2 } from 'lucide-react';
import { fetchProjectTree } from '../api';

export default function ExperimentTreeView({ activeProject }) {
  const [nodes, setNodes] = useState([]);
  const [selectedNodeId, setSelectedNodeId] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!activeProject?.id) return;
    setLoading(true);
    fetchProjectTree(activeProject.id).then((data) => {
      setNodes(data);
      if (data.length > 0) {
        setSelectedNodeId(data[0].id);
      }
      setLoading(false);
    });
  }, [activeProject?.id]);

  const selectedNode = nodes.find((n) => n.id === selectedNodeId) || nodes[0];

  if (!activeProject) {
    return (
      <div className="p-8 max-w-7xl mx-auto">
        <div className="glass-panel p-12 rounded-xl text-center space-y-3 border-slate-800">
          <GitFork className="w-10 h-10 text-slate-600 mx-auto" />
          <h3 className="text-lg font-bold text-slate-200 font-mono">Not configured</h3>
          <p className="text-xs text-slate-400">Select or start a research project to view the experiment tree.</p>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="p-8 max-w-7xl mx-auto flex items-center justify-center min-h-[400px]">
        <div className="flex items-center space-x-3 text-purple-400 font-mono text-sm">
          <Loader2 className="w-6 h-6 animate-spin" />
          <span>Fetching experiment tree nodes...</span>
        </div>
      </div>
    );
  }

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
          Click any node in the directed experiment tree to inspect its hypothesis formulation, code changes, hyperparameters, stdout logs, and metrics.
        </p>
      </div>

      {/* Visual Tree Layout */}
      {nodes.length > 0 ? (
        <div className="glass-panel p-8 rounded-xl space-y-8 border-purple-500/20 bg-slate-900/90 overflow-x-auto">
          <div className="flex flex-wrap gap-4 items-center justify-center">
            {nodes.map((node) => (
              <div
                key={node.id}
                onClick={() => setSelectedNodeId(node.id)}
                className={`p-4 rounded-xl border cursor-pointer transition-all w-72 text-center space-y-2 ${
                  selectedNodeId === node.id
                    ? 'bg-purple-950/80 border-purple-400 text-white shadow-lg shadow-purple-500/20 ring-2 ring-purple-500/40'
                    : 'bg-slate-900 border-slate-700 text-slate-300 hover:border-slate-500'
                }`}
              >
                <div className="flex items-center justify-between text-xs font-mono">
                  <span className="font-bold text-slate-400">{node.id}</span>
                  <span className="bg-slate-800 text-emerald-400 px-2 py-0.5 rounded text-[10px]">
                    {node.metricName}: {node.metricValue}
                  </span>
                </div>
                <h4 className="font-bold text-sm text-slate-100 truncate">{node.title}</h4>
                <p className="text-[11px] text-slate-400 line-clamp-1">{node.status}</p>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="glass-panel p-8 rounded-xl text-center space-y-2">
          <p className="text-xs text-slate-400 font-mono">No experiment nodes logged yet.</p>
        </div>
      )}

      {/* Selected Node Detailed Inspector */}
      {selectedNode && (
        <div className="glass-panel p-6 rounded-xl border border-purple-500/40 space-y-4 bg-slate-900/95">
          <div className="flex items-center justify-between border-b border-slate-800 pb-4">
            <div className="flex items-center space-x-3">
              <span className="px-3 py-1 bg-purple-950 text-purple-300 text-xs font-mono font-bold rounded-lg border border-purple-800">
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
              <p className="text-xs text-purple-300 bg-slate-950 p-3 rounded-lg border border-slate-800 font-mono">
                {selectedNode.hyperparams}
              </p>
            </div>

            <div className="space-y-3">
              <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider font-mono">
                Sandboxed Execution Output / Stdout
              </h4>
              <pre className="text-[11px] text-slate-300 bg-slate-950 p-3 rounded-lg border border-slate-800 font-mono h-32 overflow-y-auto">
{selectedNode.stdout || `[INFO] Sandboxed execution finished in ${selectedNode.executionTime}. Exit code: 0.`}
              </pre>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
