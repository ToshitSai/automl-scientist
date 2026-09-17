import React, { useState } from 'react';
import { 
  PlusCircle, 
  Upload, 
  Cpu, 
  Zap, 
  Layers, 
  CheckCircle2, 
  Play, 
  Sparkles,
  FileSpreadsheet
} from 'lucide-react';

export default function NewResearchView({ onStartResearch }) {
  const [goal, setGoal] = useState('Improve fraud detection under extreme class imbalance');
  const [selectedDataset, setSelectedDataset] = useState('credit_card_fraud.csv');
  const [maxExperiments, setMaxExperiments] = useState(10);
  const [computeBudget, setComputeBudget] = useState(60);
  const [framework, setFramework] = useState('PyTorch + XGBoost/LightGBM');
  const [llmProvider, setLlmProvider] = useState('OpenAI (gpt-4o)');
  const [customConstraints, setCustomConstraints] = useState('Strictly penalize false negatives; optimize for PR-AUC rather than standard accuracy.');

  const sampleDatasets = [
    { name: 'credit_card_fraud.csv', rows: '284,807', target: 'Class (0/1)', desc: 'Financial transaction fraud dataset' },
    { name: 'telecom_churn.csv', rows: '7,043', target: 'Churn (Yes/No)', desc: 'Customer retention dataset' },
    { name: 'house_prices.csv', rows: '1,460', target: 'SalePrice', desc: 'Regression valuation dataset' }
  ];

  const handleSubmit = (e) => {
    e.preventDefault();
    onStartResearch({
      goal,
      datasetName: selectedDataset,
      maxExperiments,
      computeBudget,
      framework,
      llmProvider,
      constraints: customConstraints
    });
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
          Specify your research objective, select or upload a dataset, and set compute bounds. AutoML Scientist will execute the autonomous research loop inside a safe Docker sandbox.
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

        {/* Step 2: Dataset Selection */}
        <div className="glass-panel p-6 rounded-xl space-y-4">
          <div className="flex items-center space-x-2 text-cyan-400">
            <FileSpreadsheet className="w-5 h-5" />
            <h3 className="font-bold text-base text-white">2. Dataset Selection</h3>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {sampleDatasets.map((ds) => (
              <div
                key={ds.name}
                onClick={() => setSelectedDataset(ds.name)}
                className={`p-4 rounded-xl border cursor-pointer transition-all ${
                  selectedDataset === ds.name
                    ? 'bg-cyan-950/40 border-cyan-500 text-white shadow-md shadow-cyan-500/10'
                    : 'bg-slate-900/60 border-slate-800 text-slate-400 hover:border-slate-700'
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="font-mono text-xs font-bold text-slate-200">{ds.name}</span>
                  {selectedDataset === ds.name && <CheckCircle2 className="w-4 h-4 text-cyan-400" />}
                </div>
                <p className="text-[11px] text-slate-400 mb-2">{ds.desc}</p>
                <div className="text-[10px] font-mono text-slate-400 flex items-center justify-between border-t border-slate-800/80 pt-2">
                  <span>Rows: {ds.rows}</span>
                  <span>Target: {ds.target}</span>
                </div>
              </div>
            ))}
          </div>

          <div className="border border-dashed border-slate-700 rounded-xl p-6 text-center space-y-2 bg-slate-900/40">
            <Upload className="w-6 h-6 text-slate-500 mx-auto" />
            <p className="text-xs text-slate-300 font-medium">
              Or drag & drop your custom CSV / Parquet dataset here
            </p>
            <p className="text-[11px] text-slate-400">Max file size: 500MB</p>
          </div>
        </div>

        {/* Step 3: Compute Budget & Constraints */}
        <div className="glass-panel p-6 rounded-xl space-y-5">
          <div className="flex items-center space-x-2 text-cyan-400">
            <Zap className="w-5 h-5" />
            <h3 className="font-bold text-base text-white">3. Research Budget & Engine Parameters</h3>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            <div className="space-y-2">
              <label className="text-xs font-medium text-slate-300 block">
                Maximum Experiments Tree Depth: <strong className="text-cyan-400 font-mono">{maxExperiments}</strong>
              </label>
              <input
                type="range"
                min="3"
                max="30"
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
              <label className="text-xs font-medium text-slate-300 block">LLM Orchestrator</label>
              <select
                value={llmProvider}
                onChange={(e) => setLlmProvider(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2.5 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
              >
                <option value="OpenAI (gpt-4o)">OpenAI (gpt-4o)</option>
                <option value="Anthropic (claude-3-5-sonnet)">Anthropic (claude-3-5-sonnet)</option>
                <option value="Google Gemini (gemini-2.0-flash)">Google Gemini (gemini-2.0-flash)</option>
              </select>
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-xs font-medium text-slate-300 block">Special Research Guidance / Constraints</label>
            <textarea
              rows={2}
              value={customConstraints}
              onChange={(e) => setCustomConstraints(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg p-3 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
            />
          </div>
        </div>

        {/* Submit Button */}
        <div className="pt-2">
          <button
            type="submit"
            className="w-full py-4 bg-gradient-to-r from-cyan-500 via-blue-600 to-indigo-600 hover:from-cyan-400 hover:to-indigo-500 text-white font-bold text-base rounded-xl shadow-xl shadow-cyan-500/20 flex items-center justify-center space-x-3 transition-all transform hover:-translate-y-0.5"
          >
            <Play className="w-5 h-5 fill-current" />
            <span>START AUTONOMOUS RESEARCH LOOP</span>
          </button>
        </div>
      </form>
    </div>
  );
}
