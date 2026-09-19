import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import ResearchStartScreen from './components/ResearchStartScreen';
import ResearchChatWorkspace from './components/ResearchChatWorkspace';
import SettingsModal from './components/SettingsModal';
import { fetchProjects, fetchProjectDetails, createResearchProject, fetchSettings } from './api';

export default function App() {
  const [projects, setProjects] = useState([]);
  const [activeProject, setActiveProject] = useState(null);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isLaunching, setIsLaunching] = useState(false);
  const [dockerReady, setDockerReady] = useState(false);
  const [llmConfigured, setLlmConfigured] = useState(false);

  const loadProjects = async () => {
    const list = await fetchProjects();
    setProjects(list);
    if (!activeProject && list.length > 0) {
      setActiveProject(list[0]);
    }
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

  const handleStartResearch = async (formData) => {
    setIsLaunching(true);
    try {
      const res = await createResearchProject(formData);
      if (res.project) {
        setActiveProject(res.project);
        await loadProjects();
      }
    } catch (err) {
      alert("Error launching research: " + err.message);
    } finally {
      setIsLaunching(false);
    }
  };

  const handleNewResearchClick = () => {
    setActiveProject(null);
  };

  return (
    <div className="flex h-screen bg-[#0B0F17] text-slate-100 font-sans overflow-hidden">
      
      {/* Sakana Chat Style Left Sidebar */}
      <Sidebar
        projects={projects}
        activeProject={activeProject}
        setActiveProject={setActiveProject}
        onNewResearch={handleNewResearchClick}
        onOpenSettings={() => setIsSettingsOpen(true)}
        dockerReady={dockerReady}
        llmConfigured={llmConfigured}
      />

      {/* Main Screen: Research Start Screen or Active Workspace */}
      <main className="flex-1 flex flex-col h-screen overflow-hidden bg-[#0B0F17]">
        {!activeProject ? (
          <ResearchStartScreen
            onStartResearch={handleStartResearch}
            isLaunching={isLaunching}
          />
        ) : (
          <ResearchChatWorkspace
            activeProject={activeProject}
            onNewResearch={handleNewResearchClick}
            onOpenSettings={() => setIsSettingsOpen(true)}
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
