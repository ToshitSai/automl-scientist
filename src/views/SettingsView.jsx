import React, { useState } from 'react';
import { Settings, ShieldCheck, Key, Database, Cpu, Save, CheckCircle2 } from 'lucide-react';

export default function SettingsView({ activeProvider, setActiveProvider }) {
  const [openaiKey, setOpenaiKey] = useState('sk-proj-••••••••••••••••••••••••');
  const [anthropicKey, setAnthropicKey] = useState('sk-ant-••••••••••••••••••••••••');
  const [geminiKey, setGeminiKey] = useState('AIzaSy••••••••••••••••••••••••');
  const [s2Key, setS2Key] = useState('s2-api-••••••••••••••••••••••••');
  const [dbUrl, setDbUrl] = useState('postgresql://automl_user:*****@localhost:5432/automl_scientist');
  const [dockerEnabled, setDockerEnabled] = useState(true);
  const [saved, setSaved] = useState(false);

  const handleSave = (e) => {
    e.preventDefault();
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  };

  return (
    <div className="p-8 space-y-8 max-w-4xl mx-auto">
      <div className="space-y-2">
        <div className="inline-flex items-center space-x-2 bg-cyan-500/10 border border-cyan-500/30 px-3 py-1 rounded-full text-xs font-mono text-cyan-300">
          <Settings className="w-3.5 h-3.5" />
          <span>System & Engine Settings</span>
        </div>
        <h2 className="text-2xl font-extrabold text-white tracking-tight">
          AutoML Scientist Configuration
        </h2>
        <p className="text-slate-400 text-sm">
          Manage LLM API providers, Docker container execution quotas, database connections, and Semantic Scholar literature keys.
        </p>
      </div>

      <form onSubmit={handleSave} className="space-y-6">
        {/* LLM Providers */}
        <div className="glass-panel p-6 rounded-xl space-y-4">
          <div className="flex items-center space-x-2 text-cyan-400">
            <Key className="w-5 h-5" />
            <h3 className="font-bold text-base text-white">LLM Provider API Credentials</h3>
          </div>

          <div className="space-y-4 text-xs">
            <div className="space-y-1">
              <label className="text-slate-300 font-medium block">OpenAI API Key (OPENAI_API_KEY)</label>
              <input
                type="password"
                value={openaiKey}
                onChange={(e) => setOpenaiKey(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2.5 text-slate-200 font-mono focus:outline-none focus:border-cyan-500"
              />
            </div>

            <div className="space-y-1">
              <label className="text-slate-300 font-medium block">Anthropic API Key (ANTHROPIC_API_KEY)</label>
              <input
                type="password"
                value={anthropicKey}
                onChange={(e) => setAnthropicKey(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2.5 text-slate-200 font-mono focus:outline-none focus:border-cyan-500"
              />
            </div>

            <div className="space-y-1">
              <label className="text-slate-300 font-medium block">Google Gemini API Key (GEMINI_API_KEY)</label>
              <input
                type="password"
                value={geminiKey}
                onChange={(e) => setGeminiKey(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2.5 text-slate-200 font-mono focus:outline-none focus:border-cyan-500"
              />
            </div>
          </div>
        </div>

        {/* Literature Key */}
        <div className="glass-panel p-6 rounded-xl space-y-4">
          <div className="flex items-center space-x-2 text-cyan-400">
            <Cpu className="w-5 h-5" />
            <h3 className="font-bold text-base text-white">Literature Search Credentials</h3>
          </div>
          <div className="space-y-1 text-xs">
            <label className="text-slate-300 font-medium block">Semantic Scholar API Key (S2_API_KEY)</label>
            <input
              type="password"
              value={s2Key}
              onChange={(e) => setS2Key(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2.5 text-slate-200 font-mono focus:outline-none focus:border-cyan-500"
            />
          </div>
        </div>

        {/* Sandbox & Database */}
        <div className="glass-panel p-6 rounded-xl space-y-4">
          <div className="flex items-center space-x-2 text-cyan-400">
            <ShieldCheck className="w-5 h-5 text-emerald-400" />
            <h3 className="font-bold text-base text-white">Docker Sandbox Security & Database</h3>
          </div>

          <div className="space-y-4 text-xs">
            <div className="flex items-center justify-between p-3 rounded-lg bg-slate-900 border border-slate-800">
              <div>
                <span className="font-bold text-slate-200 block">Docker Container Isolation</span>
                <span className="text-[11px] text-slate-400">Execute LLM-generated experiment code inside isolated Docker containers.</span>
              </div>
              <input
                type="checkbox"
                checked={dockerEnabled}
                onChange={(e) => setDockerEnabled(e.target.checked)}
                className="w-5 h-5 accent-cyan-500 cursor-pointer"
              />
            </div>

            <div className="space-y-1">
              <label className="text-slate-300 font-medium block">PostgreSQL Database Connection (DATABASE_URL)</label>
              <input
                type="text"
                value={dbUrl}
                onChange={(e) => setDbUrl(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2.5 text-slate-200 font-mono focus:outline-none focus:border-cyan-500"
              />
            </div>
          </div>
        </div>

        <button
          type="submit"
          className="w-full py-3.5 bg-cyan-600 hover:bg-cyan-500 text-white font-bold text-sm rounded-xl shadow-lg shadow-cyan-500/20 flex items-center justify-center space-x-2 transition-all"
        >
          {saved ? (
            <>
              <CheckCircle2 className="w-4 h-4 text-emerald-300" />
              <span>Settings Saved Successfully!</span>
            </>
          ) : (
            <>
              <Save className="w-4 h-4" />
              <span>Save System Settings</span>
            </>
          )}
        </button>
      </form>
    </div>
  );
}
