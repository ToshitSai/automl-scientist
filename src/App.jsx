import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import ResearchStartScreen from './components/ResearchStartScreen';
import ResearchChatWorkspace from './components/ResearchChatWorkspace';
import SettingsModal from './components/SettingsModal';
import { fetchProjects, fetchProjectDetails, sendChatMessage, fetchSettings } from './api';

export default function App() {
  const [projects, setProjects] = useState([]);
  const [activeProject, setActiveProject] = useState(null);
  const [chatMessages, setChatMessages] = useState([]);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isLaunching, setIsLaunching] = useState(false);
  const [dockerReady, setDockerReady] = useState(false);
  const [llmConfigured, setLlmConfigured] = useState(false);
  const [isInChatWorkspace, setIsInChatWorkspace] = useState(false);

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

    try {
      const res = await sendChatMessage(userText, activeProject?.id);
      const assistantMsg = {
        id: Date.now() + 1,
        role: 'assistant',
        content: res.response,
        intent: res.intent
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

  const handleNewResearchClick = () => {
    setActiveProject(null);
    setChatMessages([]);
    setIsInChatWorkspace(false);
  };

  return (
    <div className="flex h-screen bg-[#0B0F17] text-slate-100 font-sans overflow-hidden">
      
      {/* Sakana Chat Style Left Sidebar */}
      <Sidebar
        projects={projects}
        activeProject={activeProject}
        setActiveProject={(proj) => {
          setActiveProject(proj);
          setIsInChatWorkspace(true);
        }}
        onNewResearch={handleNewResearchClick}
        onOpenSettings={() => setIsSettingsOpen(true)}
        dockerReady={dockerReady}
        llmConfigured={llmConfigured}
      />

      {/* Main Screen: Research Start Composer or Conversational Workspace */}
      <main className="flex-1 flex flex-col h-screen overflow-hidden bg-[#0B0F17]">
        {!isInChatWorkspace && !activeProject ? (
          <ResearchStartScreen
            onSendChatMessage={handleSendInitialChatMessage}
            isLaunching={isLaunching}
          />
        ) : (
          <ResearchChatWorkspace
            activeProject={activeProject}
            setActiveProject={setActiveProject}
            onNewResearch={handleNewResearchClick}
            onOpenSettings={() => setIsSettingsOpen(true)}
            chatMessages={chatMessages}
            setChatMessages={setChatMessages}
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
