import React, { useState } from 'react';
import Header from './components/Header';
import Sidebar from './components/Sidebar';
import DashboardView from './views/DashboardView';
import NewResearchView from './views/NewResearchView';
import WorkspaceView from './views/WorkspaceView';
import ExperimentTreeView from './views/ExperimentTreeView';
import ExperimentsView from './views/ExperimentsView';
import DatasetAnalysisView from './views/DatasetAnalysisView';
import ModelsView from './views/ModelsView';
import ResultsView from './views/ResultsView';
import ErrorAnalysisView from './views/ErrorAnalysisView';
import LiteratureView from './views/LiteratureView';
import ReportView from './views/ReportView';
import SettingsView from './views/SettingsView';
import { INITIAL_PROJECTS } from './mockData';

export default function App() {
  const [currentView, setCurrentView] = useState('dashboard');
  const [projects, setProjects] = useState(INITIAL_PROJECTS);
  const [activeProject, setActiveProject] = useState(INITIAL_PROJECTS[0]);
  const [activeProvider, setActiveProvider] = useState('OpenAI (gpt-4o)');

  const handleStartResearch = (newResearch) => {
    const created = {
      id: `proj-${Date.now()}`,
      name: newResearch.goal,
      objective: newResearch.constraints || newResearch.goal,
      datasetName: newResearch.datasetName,
      status: 'IN_PROGRESS',
      createdAt: new Date().toISOString(),
      experimentsCount: 1,
      bestMetric: 'Profiling...',
      bestModel: newResearch.framework,
      llmProvider: newResearch.llmProvider,
      computeUsed: '0m / ' + newResearch.computeBudget + 'm'
    };

    setProjects([created, ...projects]);
    setActiveProject(created);
    setActiveProvider(newResearch.llmProvider);
    setCurrentView('workspace');
  };

  return (
    <div className="min-h-screen bg-[#0B0F19] text-slate-100 flex flex-col font-sans">
      <Header 
        currentView={currentView} 
        activeProject={activeProject} 
        activeProvider={activeProvider} 
      />

      <div className="flex flex-1">
        <Sidebar 
          currentView={currentView} 
          setCurrentView={setCurrentView} 
        />

        <main className="flex-1 overflow-y-auto bg-gradient-to-b from-[#0B0F19] via-[#0F172A]/40 to-[#0B0F19] min-h-[calc(100vh-4rem)] pb-16">
          {currentView === 'dashboard' && (
            <DashboardView 
              setCurrentView={setCurrentView} 
              projects={projects} 
              activeProject={activeProject} 
            />
          )}

          {currentView === 'new_research' && (
            <NewResearchView 
              onStartResearch={handleStartResearch} 
            />
          )}

          {currentView === 'workspace' && (
            <WorkspaceView 
              activeProject={activeProject} 
              setCurrentView={setCurrentView} 
            />
          )}

          {currentView === 'tree' && <ExperimentTreeView />}

          {currentView === 'experiments' && <ExperimentsView />}

          {currentView === 'dataset_analysis' && <DatasetAnalysisView />}

          {currentView === 'models' && <ModelsView />}

          {currentView === 'results' && <ResultsView />}

          {currentView === 'error_analysis' && <ErrorAnalysisView />}

          {currentView === 'literature' && <LiteratureView />}

          {currentView === 'report' && <ReportView />}

          {currentView === 'settings' && (
            <SettingsView 
              activeProvider={activeProvider} 
              setActiveProvider={setActiveProvider} 
            />
          )}
        </main>
      </div>
    </div>
  );
}
