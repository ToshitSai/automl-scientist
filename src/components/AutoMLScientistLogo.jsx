import React from 'react';

export default function AutoMLScientistLogo({ size = "md" }) {
  const dimensions = size === "lg" ? "w-10 h-10" : size === "sm" ? "w-5 h-5" : "w-7 h-7";
  
  return (
    <div className="flex items-center gap-3 select-none">
      <div className={`relative ${dimensions} flex items-center justify-center rounded-lg bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 shrink-0`}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-4/5 h-4/5 text-cyan-400">
          <circle cx="12" cy="12" r="3" className="fill-cyan-400/20" />
          <path d="M12 3a9 9 0 0 1 9 9" className="stroke-cyan-400" />
          <path d="M3 12a9 9 0 0 1 9-9" className="stroke-cyan-500/50" />
          <path d="M12 21a9 9 0 0 1-9-9" className="stroke-cyan-400" />
          <circle cx="12" cy="3" r="1.5" className="fill-cyan-400" />
          <circle cx="21" cy="12" r="1.5" className="fill-cyan-400" />
          <circle cx="12" cy="21" r="1.5" className="fill-cyan-400" />
          <circle cx="3" cy="12" r="1.5" className="fill-cyan-400" />
        </svg>
      </div>
      <div>
        <div className="font-semibold text-slate-100 tracking-tight text-sm leading-none flex items-center gap-1.5">
          AutoML Scientist
        </div>
        <div className="text-[10px] font-mono tracking-wider text-cyan-400/80 font-medium uppercase mt-0.5">
          Autonomous ML Research
        </div>
      </div>
    </div>
  );
}
