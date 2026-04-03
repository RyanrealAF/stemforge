import React, { useState, useEffect, useRef } from 'react';
import { cn } from '../lib/utils';

interface KnobProps {
  label: string;
  value: number;
  onChange: (value: number) => void;
  min?: number;
  max?: number;
  step?: number;
  unit?: string;
  mode: 'gain' | 'threshold';
  onToggleMode: () => void;
  className?: string;
}

export const Knob: React.FC<KnobProps> = ({
  label,
  value,
  onChange,
  min = 0,
  max = 100,
  step = 1,
  unit = '',
  mode,
  onToggleMode,
  className,
}) => {
  const [isDragging, setIsDragging] = useState(false);
  const startY = useRef(0);
  const startValue = useRef(0);

  const handleMouseDown = (e: React.MouseEvent) => {
    setIsDragging(true);
    startY.current = e.clientY;
    startValue.current = value;
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  };

  const handleMouseMove = (e: MouseEvent) => {
    const deltaY = startY.current - e.clientY;
    const range = max - min;
    const sensitivity = 0.5;
    const newValue = Math.min(max, Math.max(min, startValue.current + (deltaY * sensitivity * (range / 100))));
    onChange(Math.round(newValue / step) * step);
  };

  const handleMouseUp = () => {
    setIsDragging(false);
    document.removeEventListener('mousemove', handleMouseMove);
    document.removeEventListener('mouseup', handleMouseUp);
  };

  const rotation = ((value - min) / (max - min)) * 270 - 135;

  return (
    <div className={cn("flex flex-col items-center gap-2", className)}>
      <div className="relative group">
        {/* Outer Ring */}
        <div 
          className={cn(
            "w-20 h-20 rounded-full border-4 flex items-center justify-center cursor-ns-resize transition-colors",
            mode === 'gain' ? "border-orange-500/30" : "border-blue-500/30",
            isDragging && "scale-105"
          )}
          onMouseDown={handleMouseDown}
          onClick={(e) => {
            if (!isDragging && e.detail === 1) {
               // Handle tap to toggle mode if not dragging
            }
          }}
        >
          {/* Knob Body */}
          <div 
            className="w-14 h-14 rounded-full bg-zinc-800 shadow-xl border border-zinc-700 relative flex items-center justify-center"
            style={{ transform: `rotate(${rotation}deg)` }}
          >
            {/* Indicator Dot */}
            <div className="absolute top-1 w-1.5 h-1.5 rounded-full bg-white shadow-[0_0_8px_rgba(255,255,255,0.8)]" />
          </div>
        </div>

        {/* Mode Toggle Button */}
        <button
          onClick={onToggleMode}
          className={cn(
            "absolute -top-2 -right-2 px-1.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-tighter transition-colors shadow-lg",
            mode === 'gain' ? "bg-orange-500 text-black" : "bg-blue-500 text-white"
          )}
        >
          {mode}
        </button>
      </div>

      <div className="text-center">
        <span className="text-[10px] uppercase font-bold text-zinc-500 tracking-widest block">{label}</span>
        <span className="text-xs font-mono text-zinc-300">{value}{unit}</span>
      </div>
    </div>
  );
};
