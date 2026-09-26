import React, { useState, useEffect } from 'react';
import { fetchSettings, updateSettings } from '../api';

export default function SettingsModal({ isOpen, onClose }) {
  const [settings, setSettings] = useState({
    llmProvider: 'Not configured',
    apiKeySet: false,
    sandboxMode: 'Process Sandbox (Subprocess isolation)',
    dockerAvailable: false,
    maxExperiments: 5,
    timeBudgetMins: 60
  });

  const [apiKeyInput, setApiKeyInput] = useState('');
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState('');

  useEffect(() => {
    if (!isOpen) return;
    const load = async () => {
      const data = await fetchSettings();
      setSettings(data);
    };
    load();
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSave = async (e) => {
    e.preventDefault();
    setSaving(true);
    setMsg('');

    try {
      const payload = {
        ...settings,
        apiKeySet: apiKeyInput.trim().length > 0 ? true : settings.apiKeySet
      };
      const res = await updateSettings(payload);
      if (res.settings) {
        setSettings(res.settings);
        setMsg('Settings updated successfully.');
      }
    } catch (err) {
      setMsg('Error saving settings: ' + err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-0 sm:p-4 select-none">
      {/* Desktop: centered dialog. Mobile: near-full-screen sheet (fits any
          viewport — no fixed 800px dialog) with internal scrolling. */}
      <div className="bg-[#131824] border border-[#232D3F] sm:rounded-2xl rounded-none w-full max-w-lg h-full sm:h-auto max-h-full sm:max-h-[90vh] overflow-y-auto overscroll-contain p-4 sm:p-6 shadow-2xl space-y-6 min-w-0"
        role="dialog"
        aria-modal="true"
        aria-label="Settings"
        style={{ paddingBottom: 'max(1.5rem, env(safe-area-inset-bottom))' }}>
        
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[#212B3B] pb-4">
          <div className="flex items-center gap-2 min-w-0">
            <svg className="w-5 h-5 text-cyan-400 shrink-0" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.38a2 2 0 0 0-.73-2.73l-.15-.09a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
              <circle cx="12" cy="12" r="3" />
            </svg>
            <h3 className="text-base font-bold text-slate-100 truncate">AutoML Scientist Settings</h3>
          </div>
          <button
            onClick={onClose}
            aria-label="Close settings"
            className="w-10 h-10 -mr-2 shrink-0 flex items-center justify-center rounded-lg text-slate-400 hover:text-slate-200 hover:bg-[#161B26] transition-colors"
          >
            ✕
          </button>
        </div>

        <form onSubmit={handleSave} className="space-y-4 text-xs font-sans">
          
          {/* LLM Engine Provider */}
          <div className="space-y-1.5">
            <label className="text-slate-300 font-medium">LLM Engine Provider</label>
            <select
              value={settings.llmProvider}
              onChange={(e) => setSettings({ ...settings, llmProvider: e.target.value })}
              className="w-full bg-[#0D111A] border border-[#212B3B] text-slate-200 rounded-lg p-2.5 font-mono focus:outline-none focus:border-cyan-500/50"
            >
              <option value="Heuristic / Rule-based">Rule-Based Synthesizer (Default)</option>
              <option value="OpenAI GPT-4o">OpenAI GPT-4o / GPT-4o-mini</option>
              <option value="Anthropic Claude 3.5">Anthropic Claude 3.5 Sonnet</option>
              <option value="Ollama Local">Local Ollama LLM Endpoint</option>
            </select>
          </div>

          {/* OpenAI API Key */}
          <div className="space-y-1.5">
            <label className="text-slate-300 font-medium flex justify-between">
              <span>OpenAI API Key</span>
              <span className="font-mono text-[10px] text-slate-500">
                {settings.apiKeySet ? '✓ Key Configured' : 'Not Configured'}
              </span>
            </label>
            <input
              type="password"
              value={apiKeyInput}
              onChange={(e) => setApiKeyInput(e.target.value)}
              placeholder={settings.apiKeySet ? '••••••••••••••••' : 'sk-...'}
              className="w-full bg-[#0D111A] border border-[#212B3B] text-slate-200 rounded-lg p-2.5 font-mono focus:outline-none focus:border-cyan-500/50"
            />
          </div>

          {/* Docker & Sandbox Info */}
          <div className="p-3 bg-[#0D111A] rounded-lg border border-[#212B3B] space-y-1.5 font-mono text-[11px] min-w-0">
            <div className="flex flex-wrap justify-between items-center gap-x-2 text-slate-300">
              <span>Sandboxed Execution Mode:</span>
              <span className="text-cyan-400 font-bold break-all">{settings.sandboxMode}</span>
            </div>
            <div className="flex justify-between items-center text-slate-400 text-[10px]">
              <span>Docker Daemon Availability:</span>
              <span className={settings.dockerAvailable ? 'text-emerald-400 font-bold' : 'text-amber-400'}>
                {settings.dockerAvailable ? 'Available (Docker Isolated)' : 'Unavailable (Process Sandbox Fallback)'}
              </span>
            </div>
          </div>

          {msg && (
            <div className="p-2.5 rounded bg-cyan-950/40 border border-cyan-500/30 text-cyan-300 text-xs font-mono">
              {msg}
            </div>
          )}

          <div className="pt-3 border-t border-[#212B3B] flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-lg bg-[#1C2536] hover:bg-[#253147] text-slate-300 font-medium transition-all"
            >
              Close
            </button>
            <button
              type="submit"
              disabled={saving}
              className="px-4 py-2 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold shadow-lg shadow-cyan-500/20 transition-all cursor-pointer"
            >
              {saving ? 'Saving...' : 'Save Settings'}
            </button>
          </div>

        </form>

      </div>
    </div>
  );
}
