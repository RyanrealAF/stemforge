import React from 'react';
import { cn } from '../lib/utils';

interface VerticalSliderProps {
  label: string;
  value: number;
  onChange: (value: number) => void;
  min?: number;
  max?: number;
  color?: string;
  className?: string;
}

export const VerticalSlider: React.FC<VerticalSliderProps> = ({
  label,
  value,
  onChange,
  min = 0,
  max = 100,
  color = "bg-orange-500",
  className,
}) => {
  return (
    <div className={cn("flex flex-col items-center gap-3 h-64", className)}>
      <div className="relative h-full w-8 bg-zinc-900 rounded-full border border-zinc-800 overflow-hidden group">
        {/* Track Fill */}
        <div 
          className={cn("absolute bottom-0 w-full transition-all duration-100", color)}
          style={{ height: `${((value - min) / (max - min)) * 100}%` }}
        />
        
        {/* Invisible Input for better UX */}
        <input
          type="range"
          min={min}
          max={max}
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer [writing-mode:bt-lr] appearance-none"
          style={{ transform: 'rotate(-90deg)', width: '256px', height: '32px', left: '-112px', top: '112px' }}
        />

        {/* Handle Visual */}
        <div 
          className="absolute left-0 w-full h-2 bg-white shadow-lg pointer-events-none"
          style={{ bottom: `calc(${((value - min) / (max - min)) * 100}% - 4px)` }}
        />
      </div>
      
      <div className="text-center">
        <span className="text-[10px] uppercase font-bold text-zinc-500 tracking-widest block">{label}</span>
        <span className="text-xs font-mono text-zinc-300">{value}%</span>
      </div>
    </div>
  );
};
