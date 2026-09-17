import React from 'react';
import { BookOpen, ExternalLink, Sparkles, CheckCircle2 } from 'lucide-react';
import { INITIAL_LITERATURE } from '../mockData';

export default function LiteratureView() {
  return (
    <div className="p-8 space-y-8 max-w-7xl mx-auto">
      <div className="space-y-2">
        <div className="inline-flex items-center space-x-2 bg-cyan-500/10 border border-cyan-500/30 px-3 py-1 rounded-full text-xs font-mono text-cyan-300">
          <BookOpen className="w-3.5 h-3.5" />
          <span>Semantic Scholar Literature Integration</span>
        </div>
        <h2 className="text-2xl font-extrabold text-white tracking-tight">
          Automated Academic Literature & Citations
        </h2>
        <p className="text-slate-400 text-sm">
          AutoML Scientist searches Semantic Scholar to ingest related methodologies, prevent redundant work, and ground generated hypotheses in verified ML literature.
        </p>
      </div>

      {/* Paper Cards */}
      <div className="space-y-4">
        {INITIAL_LITERATURE.map((paper) => (
          <div key={paper.paperId} className="glass-panel p-6 rounded-xl border-slate-800 space-y-3">
            <div className="flex items-start justify-between gap-4">
              <div>
                <span className="text-[10px] font-mono text-cyan-400 uppercase tracking-wider block">
                  Semantic Scholar Paper ID: {paper.paperId} • Published {paper.year}
                </span>
                <h3 className="font-bold text-base text-white mt-1">{paper.title}</h3>
                <p className="text-xs text-slate-400 mt-0.5">Authors: {paper.authors}</p>
              </div>
              <a
                href={paper.url}
                target="_blank"
                rel="noreferrer"
                className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-medium text-cyan-300 border border-slate-700 flex items-center space-x-1 shrink-0"
              >
                <span>View Paper</span>
                <ExternalLink className="w-3.5 h-3.5" />
              </a>
            </div>

            <p className="text-xs text-slate-300 bg-slate-900/60 p-3 rounded-lg border border-slate-800 font-sans leading-relaxed">
              Abstract: &quot;{paper.abstract}&quot;
            </p>

            <div className="flex items-center space-x-2 text-xs text-emerald-400 font-mono">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Relevance to Current Problem: {paper.relevance}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
