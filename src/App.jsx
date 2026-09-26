import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import ResearchStartScreen from './components/ResearchStartScreen';
import ResearchChatWorkspace from './components/ResearchChatWorkspace';
import SettingsModal from './components/SettingsModal';
import { fetchProjects, fetchProjectDetails, sendChatMessage, fetchSettings, approveDataset, fetchConversationMessages } from './api';

// One conversation per project so the FIRST message (sent from the start
// screen) and every workspace follow-up share the same server-side memory.
function getConversationId(projectId) {
  if (!projectId) return null;
  const key = 'ai-scientist-conv-' + projectId;
  let conv = null;
  try { conv = localStorage.getItem(key); } catch (e) { /* private mode */ }
  if (!conv) {
    conv = 'conv-' + projectId + '-' + Math.random().toString(36).substring(2, 9);
    try { localStorage.setItem(key, conv); } catch (e) { /* ignore */ }
  }
  return conv;
}

export default function App() {
  const [projects, setProjects] = useState([]);
  const [activeProject, setActiveProject] = useState(null);
  const [chatMessages, setChatMessages] = useState([]);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isLaunching, setIsLaunching] = useState(false);
  const [isApproving, setIsApproving] = useState(false);
  const [dockerReady, setDockerReady] = useState(false);
  const [llmConfigured, setLlmConfigured] = useState(false);
  const [isInChatWorkspace, setIsInChatWorkspace] = useState(false);
  const [conversationId, setConversationId] = useState(null);
  // Mobile sidebar drawer (<1024px): overlays the chat instead of squeezing it.
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  // Escape closes the drawer (and the settings modal keeps its own handling).
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') setIsSidebarOpen(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  // Resizing up to the desktop breakpoint closes the drawer so the state never
  // goes stale (the drawer is CSS-hidden on desktop anyway).
  useEffect(() => {
    const mq = window.matchMedia('(min-width: 1024px)');
    const onChange = (e) => { if (e.matches) setIsSidebarOpen(false); };
    if (mq.addEventListener) mq.addEventListener('change', onChange);
    else mq.addListener(onChange);
    return () => {
      if (mq.removeEventListener) mq.removeEventListener('change', onChange);
      else mq.removeListener(onChange);
    };
  }, []);

  const loadProjects = async () => {
    const list = await fetchProjects();
    setProjects(list);
  };

  const loadSysSettings = async () => {
    const s = await fetchSettings();
    setDockerReady(s.dockerAvailable || false);
    setLlmConfigured(s.apiKeySet || false);
  };

  useEffect(() => {
    loadProjects();
    loadSysSettings();
    const interval = setInterval(loadProjects, 3000);
    return () => clearInterval(interval);
  }, []);

  // Sync active project state
  useEffect(() => {
    if (!activeProject?.id) return;
    const interval = setInterval(async () => {
      const updated = await fetchProjectDetails(activeProject.id);
      if (updated) {
        setActiveProject(updated);
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [activeProject?.id]);

  const handleSendInitialChatMessage = async (userText) => {
    if (!userText.trim()) return;
    setIsLaunching(true);

    const userMsg = { id: Date.now(), role: 'user', content: userText };
    setChatMessages([userMsg]);
    setIsInChatWorkspace(true);

    // A fresh chat without an active project still gets its own conversation
    // id so follow-ups keep the same memory.
    const convId = conversationId || getConversationId(activeProject?.id || 'general-' + Date.now().toString(36));
    setConversationId(convId);

    try {
      const res = await sendChatMessage(userText, activeProject?.id, convId, null, null);
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

      if (res.action === 'START_RESEARCH' && res.project) {
        setActiveProject(res.project);
        await loadProjects();
      }
    } catch (err) {
      setChatMessages(prev => [
        ...prev,
        { id: Date.now() + 1, role: 'assistant', content: `Error: ${err.message}` }
      ]);
    } finally {
      setIsLaunching(false);
    }
  };

  const handleApproveDataset = async (repoId, researchQuery) => {
    if (!repoId || isApproving) return;
    setIsApproving(true);
    setIsInChatWorkspace(true);
    try {
      const res = await approveDataset(repoId, researchQuery || `Improve modeling on ${repoId}`);
      setChatMessages(prev => [
        ...prev,
        { id: Date.now() + 2, role: 'assistant', content: res.response || `Loading ${repoId}...` }
      ]);
      if (res.project) {
        const projId = res.project.id;
        setActiveProject(res.project);
        // Rebind the conversation to the new project so follow-ups about the
        // study share the pre-approval chat context.
        setConversationId(getConversationId(projId));
        await loadProjects();
      }
    } catch (err) {
      setChatMessages(prev => [
        ...prev,
        { id: Date.now() + 2, role: 'assistant', content: `Sorry, I couldn't load that dataset: ${err.message}` }
      ]);
    } finally {
      setIsApproving(false);
    }
  };

  // Clicking a project in the sidebar: load its conversation history so the
  // chat survives page refreshes and switching between studies.
  const handleSelectProject = async (proj) => {
    setActiveProject(proj);
    setIsInChatWorkspace(true);
    const convId = getConversationId(proj.id);
    setConversationId(convId);
    setChatMessages([]);
    try {
      const msgs = await fetchConversationMessages(convId);
      const mapped = (msgs || []).map(m => ({
        id: m.id,
        role: m.role,
        content: m.content,
        intent: m.intent,
        datasets: null,
        recommendation: null,
        researchQuery: null
      }));
      setChatMessages(mapped);
    } catch (e) {
      setChatMessages([]);
    }
  };

  const handleNewResearchClick = () => {
    setActiveProject(null);
    setChatMessages([]);
    setIsInChatWorkspace(false);
    setConversationId(null);
  };

  return (
    <div className="flex h-screen bg-[#0B0F17] text-slate-100 font-sans overflow-hidden">

      {/* Sakana Chat Style Left Sidebar — desktop rail / mobile drawer */}
      <Sidebar
        projects={projects}
        activeProject={activeProject}
        setActiveProject={handleSelectProject}
        onNewResearch={handleNewResearchClick}
        onOpenSettings={() => setIsSettingsOpen(true)}
        dockerReady={dockerReady}
        llmConfigured={llmConfigured}
        isMobileOpen={isSidebarOpen}
        onMobileClose={() => setIsSidebarOpen(false)}
      />

      {/* Main Screen: Research Start Composer or Conversational Workspace.
          min-w-0 is essential: without it the flex child cannot shrink below
          its content width and the page overflows horizontally on phones. */}
      <main className="flex-1 min-w-0 flex flex-col h-screen overflow-hidden bg-[#0B0F17]">
        {!isInChatWorkspace && !activeProject ? (
          <ResearchStartScreen
            onSendChatMessage={handleSendInitialChatMessage}
            isLaunching={isLaunching}
            onOpenMenu={() => setIsSidebarOpen(true)}
          />
        ) : (
          <ResearchChatWorkspace
            activeProject={activeProject}
            setActiveProject={setActiveProject}
            onNewResearch={handleNewResearchClick}
            onOpenSettings={() => setIsSettingsOpen(true)}
            chatMessages={chatMessages}
            setChatMessages={setChatMessages}
            onApproveDataset={handleApproveDataset}
            isApproving={isApproving}
            conversationId={conversationId || getConversationId(activeProject?.id || 'general')}
            onOpenMenu={() => setIsSidebarOpen(true)}
          />
        )}
      </main>

      {/* Settings Modal */}
      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
      />

    </div>
  );
}
