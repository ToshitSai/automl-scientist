import React, { useState } from 'react';
import { 
  Upload, 
  Zap, 
  CheckCircle2, 
  Play, 
  Sparkles,
  FileSpreadsheet
} from 'lucide-react';

export default function NewResearchView({ onStartResearch }) {
  const [goal, setGoal] = useState('Improve fraud detection under extreme class imbalance');
  const [selectedDataset, setSelectedDataset] = useState('sample_dataset.csv');
  const [file, setFile] = useState(null);
  const [maxExperiments, setMaxExperiments] = useState(10);
  const [computeBudget, setComputeBudget] = useState(60);
  const [framework, setFramework] = useState('PyTorch + XGBoost/LightGBM');
  const [llmProvider, setLlmProvider] = useState('Heuristic / Rule-based');
  const [customConstraints, setCustomConstraints] = useState('Strictly penalize false negatives; optimize for PR-AUC rather than standard accuracy.');

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setSelectedDataset(e.target.files[0].name);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();

    const formData = new FormData();
    formData.append("objective", goal);
    formData.append("dataset_name", selectedDataset);
    formData.append("budget", computeBudget);
    formData.append("llm_provider", llmProvider);
    if (file) {
      formData.append("file", file);
    }

    onStartResearch(formData);
  };

  return (
    <div className="p-8 space-y-8 max-w-4xl mx-auto">
      <div className="space-y-2">
        <div className="inline-flex items-center space-x-2 bg-cyan-500/10 border border-cyan-500/30 px-3 py-1 rounded-full text-xs font-mono text-cyan-300">
          <Sparkles className="w-3.5 h-3.5" />
          <span>New Research Objective Setup</span>
        </div>
        <h2 className="text-2xl font-extrabold text-white tracking-tight">
          Configure Autonomous ML Research Goal
        </h2>
        <p className="text-slate-400 text-sm">
          Specify your research objective, select or upload a dataset, and set compute bounds. AutoML Scientist will execute the autonomous research loop inside a safe sandbox.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Step 1: Research Goal */}
        <div className="glass-panel p-6 rounded-xl space-y-4">
          <div className="flex items-center space-x-2 text-cyan-400">
            <Sparkles className="w-5 h-5" />
            <h3 className="font-bold text-base text-white">1. Core Research Goal / Objective</h3>
          </div>
          <div className="space-y-2">
            <label className="text-xs font-medium text-slate-300 block">
              Describe your ML problem objective:
            </label>
            <input
              type="text"
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              placeholder="e.g. Improve fraud detection"
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-3 text-sm text-slate-100 focus:outline-none focus:border-cyan-500 font-medium"
              required
            />
          </div>
        </div>

        {/* Step 2: Dataset Selection / Upload */}
        <div className="glass-panel p-6 rounded-xl space-y-4">
          <div className="flex items-center space-x-2 text-cyan-400">
            <FileSpreadsheet className="w-5 h-5" />
            <h3 className="font-bold text-base text-white">2. Dataset Selection / Upload</h3>
          </div>

          <div className="border border-dashed border-slate-700 rounded-xl p-6 text-center space-y-3 bg-slate-900/40">
            <Upload className="w-8 h-8 text-cyan-400 mx-auto" />
            <div className="space-y-1">
              <p className="text-xs text-slate-200 font-medium">
                {file ? `Selected File: ${file.name}` : "Upload your CSV / Parquet dataset"}
              </p>
              <p className="text-[11px] text-slate-400">Real statistical EDA will inspect all rows and columns</p>
            </div>
            <input
              type="file"
              accept=".csv,.parquet"
              onChange={handleFileChange}
              className="hidden"
              id="dataset-file-input"
            />
            <label
              htmlFor="dataset-file-input"
              className="inline-block px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-600 rounded-lg text-xs font-mono text-cyan-300 cursor-pointer transition-all"
            >
              Choose CSV File
            </label>
          </div>
        </div>

        {/* Step 3: Compute Budget & Parameters */}
        <div className="glass-panel p-6 rounded-xl space-y-5">
          <div className="flex items-center space-x-2 text-cyan-400">
            <Zap className="w-5 h-5" />
            <h3 className="font-bold text-base text-white">3. Research Budget & Engine Parameters</h3>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            <div className="space-y-2">
              <label className="text-xs font-medium text-slate-300 block">
                Maximum Experiments: <strong className="text-cyan-400 font-mono">{maxExperiments}</strong>
              </label>
              <input
                type="range"
                min="3"
                max="20"
                value={maxExperiments}
                onChange={(e) => setMaxExperiments(Number(e.target.value))}
                className="w-full accent-cyan-500 cursor-pointer"
              />
            </div>

            <div className="space-y-2">
              <label className="text-xs font-medium text-slate-300 block">
                Compute Time Limit (Minutes): <strong className="text-cyan-400 font-mono">{computeBudget} mins</strong>
              </label>
              <input
                type="range"
                min="15"
                max="180"
                step="15"
                value={computeBudget}
                onChange={(e) => setComputeBudget(Number(e.target.value))}
                className="w-full accent-cyan-500 cursor-pointer"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            <div className="space-y-2">
              <label className="text-xs font-medium text-slate-300 block">Preferred Framework</label>
              <select
                value={framework}
                onChange={(e) => setFramework(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2.5 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
              >
                <option value="PyTorch + XGBoost/LightGBM">PyTorch + XGBoost / LightGBM</option>
                <option value="Scikit-learn Pure Baseline">Scikit-learn Pure Baseline</option>
                <option value="Auto-detect Best Suite">Auto-detect Best Suite</option>
              </select>
            </div>

            <div className="space-y-2">
              <label className="text-xs font-medium text-slate-300 block">LLM Provider / Mode</label>
              <select
                value={llmProvider}
                onChange={(e) => setLlmProvider(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2.5 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
              >
                <option value="Heuristic / Rule-based">Heuristic / Rule-based (Built-in Engine)</option>
                <option value="OpenAI (gpt-4o)">OpenAI (gpt-4o)</option>
                <option value="Anthropic (claude-3-5-sonnet)">Anthropic (claude-3-5-sonnet)</option>
              </select>
            </div>
          </div>
        </div>

        {/* Submit Button */}
        <div className="pt-2">
          <button
            type="submit"
            className="w-full py-4 bg-gradient-to-r from-cyan-500 via-blue-600 to-indigo-600 hover:from-cyan-400 hover:to-indigo-500 text-white font-bold text-base rounded-xl shadow-xl shadow-cyan-500/20 flex items-center justify-center space-x-3 transition-all transform hover:-translate-y-0.5"
          >
            <Play className="w-5 h-5 fill-current" />
            <span>START REAL AUTONOMOUS RESEARCH</span>
          </button>
        </div>
      </form>
    </div>
  );
}
