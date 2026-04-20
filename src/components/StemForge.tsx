import React, { useEffect, useRef, useState } from 'react';
import WaveSurfer from 'wavesurfer.js';
import { Play, Pause, SkipBack, Upload, Activity, Layers, Settings, Info } from 'lucide-react';
import { Knob } from './Knob';
import { VerticalSlider } from './VerticalSlider';
import { cn } from '../lib/utils';
import { motion, AnimatePresence } from 'motion/react';

interface StemState {
  vocals: number;
  bass: number;
  other: number;
  drums: number;
  kick: { gain: number; threshold: number; mode: 'gain' | 'threshold' };
  snare: { gain: number; threshold: number; mode: 'gain' | 'threshold' };
  hihat: { gain: number; threshold: number; mode: 'gain' | 'threshold' };
  main: number;
}

interface StemUrls {
  vocals?: string;
  drums?: string;
}

export const StemForge: React.FC = () => {
  const waveformRef = useRef<HTMLDivElement>(null);
  const wavesurfer = useRef<WaveSurfer | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [isLoaded, setIsLoaded] = useState(false);
  const [hfUrl, setHfUrl] = useState('https://Ryanrealaf-stemforge.hf.space');
  const [showSettings, setShowSettings] = useState(false);
  const [stemUrls, setStemUrls] = useState<StemUrls>({});
  const [isSendingToRhythmForge, setIsSendingToRhythmForge] = useState(false);

  const [stems, setStems] = useState<StemState>({
    vocals: 80,
    bass: 70,
    other: 60,
    drums: 100,
    kick: { gain: 50, threshold: -12, mode: 'gain' },
    snare: { gain: 50, threshold: -12, mode: 'gain' },
    hihat: { gain: 50, threshold: -12, mode: 'gain' },
    main: 90,
  });

  useEffect(() => {
    if (waveformRef.current && !wavesurfer.current) {
      wavesurfer.current = WaveSurfer.create({
        container: waveformRef.current,
        waveColor: '#3f3f46',
        progressColor: '#f97316',
        cursorColor: '#f97316',
        barWidth: 2,
        barRadius: 3,
        height: 120,
        normalize: true,
      });

      wavesurfer.current.on('play', () => setIsPlaying(true));
      wavesurfer.current.on('pause', () => setIsPlaying(false));
      wavesurfer.current.on('finish', () => setIsPlaying(false));
    }

    return () => {
      wavesurfer.current?.destroy();
    };
  }, []);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsProcessing(true);
    setProgress(0);
    setIsLoaded(false);

    // If HF URL is set, use real backend
    if (hfUrl) {
      try {
        const formData = new FormData();
        formData.append('file', file);

        const uploadRes = await fetch(`${hfUrl}/upload`, {
          method: 'POST',
          body: formData,
        });

        if (!uploadRes.ok) throw new Error('Upload failed');
        const { job_id } = await uploadRes.json();

        // Poll for status
        const pollInterval = setInterval(async () => {
          try {
            const statusRes = await fetch(`${hfUrl}/status/${job_id}`);
            const statusData = await statusRes.json();

            if (statusData.status === 'complete') {
              clearInterval(pollInterval);
              setIsProcessing(false);
              setIsLoaded(true);
              setStemUrls(statusData.stems ?? {});
              wavesurfer.current?.load(URL.createObjectURL(file));
              // In a real app, we would load the stems here
            } else if (statusData.status === 'error') {
              clearInterval(pollInterval);
              setIsProcessing(false);
              alert('Error: ' + statusData.error);
            } else {
              setProgress(statusData.progress || 0);
            }
          } catch (err) {
            console.error('Polling error:', err);
          }
        }, 3000);
      } catch (err) {
        setIsProcessing(false);
        alert('Failed to connect to backend. Ensure HF URL is correct and Space is running.');
      }
    } else {
      // Simulation Mode
      const interval = setInterval(() => {
        setProgress(prev => {
          if (prev >= 100) {
            clearInterval(interval);
            setIsProcessing(false);
            setIsLoaded(true);
            wavesurfer.current?.load(URL.createObjectURL(file));
            return 100;
          }
          return prev + 2;
        });
      }, 100);
    }
  };

  const togglePlay = () => {
    wavesurfer.current?.playPause();
  };

  const handleStemChange = (key: keyof StemState, value: any) => {
    setStems(prev => ({ ...prev, [key]: value }));
  };

  const handleDrumKnobChange = (drum: 'kick' | 'snare' | 'hihat', field: 'gain' | 'threshold', value: number) => {
    setStems(prev => ({
      ...prev,
      [drum]: { ...prev[drum], [field]: value }
    }));
  };

  const toggleDrumMode = (drum: 'kick' | 'snare' | 'hihat') => {
    setStems(prev => ({
      ...prev,
      [drum]: { ...prev[drum], mode: prev[drum].mode === 'gain' ? 'threshold' : 'gain' }
    }));
  };

  const sendToRhythmForge = async () => {
    if (!stemUrls.vocals || !stemUrls.drums) return;

    const RHYTHMFORGE_URL = 'https://Ryanrealaf-rhythmforge.hf.space';
    setIsSendingToRhythmForge(true);

    try {
      const [vocalBlob, drumBlob] = await Promise.all([
        fetch(stemUrls.vocals).then((r) => r.blob()),
        fetch(stemUrls.drums).then((r) => r.blob())
      ]);

      const fd = new FormData();
      fd.append('vocal_file', vocalBlob, 'vocals.wav');
      fd.append('drum_file', drumBlob, 'drums.wav');

      const res = await fetch(`${RHYTHMFORGE_URL}/analyze/full`, {
        method: 'POST',
        body: fd
      });

      if (!res.ok) throw new Error(`RhythmForge HTTP ${res.status}`);

      const data = await res.json();
      const tab = window.open(RHYTHMFORGE_URL, '_blank');
      const push = setInterval(() => {
        try {
          tab?.postMessage({ type: 'RHYTHMFORGE_RESULT', data }, RHYTHMFORGE_URL);
        } catch {
          // no-op
        }
      }, 800);
      setTimeout(() => clearInterval(push), 12000);
    } catch (err) {
      alert('RhythmForge handoff failed: ' + (err instanceof Error ? err.message : String(err)));
    } finally {
      setIsSendingToRhythmForge(false);
    }
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 font-sans selection:bg-orange-500/30">
      {/* Header */}
      <header className="border-b border-zinc-800/50 bg-zinc-900/30 backdrop-blur-xl sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-orange-500 rounded-xl flex items-center justify-center shadow-[0_0_20px_rgba(249,115,22,0.3)]">
              <Activity className="text-black w-6 h-6" />
            </div>
            <div>
              <h1 className="text-xl font-black tracking-tighter uppercase italic">StemForge</h1>
              <p className="text-[10px] text-zinc-500 font-bold uppercase tracking-[0.2em]">AI Signal Processor v4.0</p>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <button 
              onClick={() => setShowSettings(!showSettings)}
              className="p-2 hover:bg-zinc-800 rounded-lg transition-colors text-zinc-400"
            >
              <Settings className="w-5 h-5" />
            </button>
            <div className="h-8 w-[1px] bg-zinc-800" />
            <label className="flex items-center gap-2 bg-zinc-100 text-black px-4 py-2 rounded-lg font-bold text-sm cursor-pointer hover:bg-orange-500 transition-all active:scale-95">
              <Upload className="w-4 h-4" />
              <span>LOAD TRACK</span>
              <input type="file" className="hidden" accept="audio/*" onChange={handleFileUpload} />
            </label>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8 space-y-8">
        {/* Waveform Section */}
        <section className="bg-zinc-900/50 border border-zinc-800 rounded-3xl p-8 relative overflow-hidden">
          <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-orange-500 via-blue-500 to-orange-500 opacity-20" />
          
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-4">
              <button 
                onClick={() => wavesurfer.current?.seekTo(0)}
                className="p-3 bg-zinc-800 hover:bg-zinc-700 rounded-full transition-colors"
              >
                <SkipBack className="w-5 h-5" />
              </button>
              <button 
                onClick={togglePlay}
                disabled={!isLoaded}
                className={cn(
                  "w-14 h-14 rounded-full flex items-center justify-center transition-all shadow-xl",
                  isLoaded ? "bg-orange-500 text-black hover:scale-105 active:scale-95" : "bg-zinc-800 text-zinc-600 cursor-not-allowed"
                )}
              >
                {isPlaying ? <Pause className="w-6 h-6 fill-current" /> : <Play className="w-6 h-6 fill-current ml-1" />}
              </button>
            </div>
            
            <div className="flex gap-8">
              <div className="text-right">
                <span className="text-[10px] text-zinc-500 font-bold uppercase tracking-widest block">Sample Rate</span>
                <span className="text-sm font-mono">44.1 kHz</span>
              </div>
              <div className="text-right">
                <span className="text-[10px] text-zinc-500 font-bold uppercase tracking-widest block">Bit Depth</span>
                <span className="text-sm font-mono">24-bit PCM</span>
              </div>
            </div>
          </div>

          <div ref={waveformRef} className="w-full mb-4" />
          
          {!isLoaded && !isProcessing && (
            <div className="absolute inset-0 flex items-center justify-center bg-zinc-900/80 backdrop-blur-sm">
              <div className="text-center space-y-4">
                <Layers className="w-12 h-12 text-zinc-700 mx-auto" />
                <p className="text-zinc-500 font-medium">No track loaded. Upload an audio file to begin separation.</p>
              </div>
            </div>
          )}

          <AnimatePresence>
            {isProcessing && (
              <motion.div 
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="absolute inset-0 flex items-center justify-center bg-zinc-900/90 backdrop-blur-md z-10"
              >
                <div className="w-full max-w-md px-8 text-center space-y-6">
                  <div className="relative">
                    <Activity className="w-16 h-16 text-orange-500 mx-auto animate-pulse" />
                    <div className="absolute inset-0 bg-orange-500/20 blur-2xl rounded-full" />
                  </div>
                  <div className="space-y-2">
                    <h3 className="text-xl font-bold tracking-tight">Processing Signal...</h3>
                    <p className="text-zinc-500 text-sm">Demucs v4 htdemucs_ft is isolating 7 stems</p>
                  </div>
                  <div className="h-2 w-full bg-zinc-800 rounded-full overflow-hidden">
                    <motion.div 
                      className="h-full bg-orange-500"
                      initial={{ width: 0 }}
                      animate={{ width: `${progress}%` }}
                    />
                  </div>
                  <p className="text-xs font-mono text-zinc-400">{progress}% COMPLETE</p>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </section>

        {/* Controls Section */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          {/* Drum Separation (Rotary Knobs) */}
          <section className="lg:col-span-5 bg-zinc-900/30 border border-zinc-800/50 rounded-3xl p-8">
            <div className="flex items-center justify-between mb-12">
              <h2 className="text-sm font-black uppercase tracking-[0.3em] text-zinc-500 italic">Drum Isolation</h2>
              <div className="px-2 py-1 bg-blue-500/10 text-blue-400 text-[10px] font-bold rounded border border-blue-500/20">DRUMSEP_V2</div>
            </div>

            <div className="relative h-64 flex items-center justify-center">
              {/* Kick (Center Top) */}
              <Knob 
                label="Kick"
                value={stems.kick.mode === 'gain' ? stems.kick.gain : stems.kick.threshold}
                onChange={(v) => handleDrumKnobChange('kick', stems.kick.mode, v)}
                mode={stems.kick.mode}
                onToggleMode={() => toggleDrumMode('kick')}
                min={stems.kick.mode === 'gain' ? 0 : -60}
                max={stems.kick.mode === 'gain' ? 100 : 0}
                unit={stems.kick.mode === 'gain' ? '%' : 'dB'}
                className="absolute top-0"
              />
              
              {/* Snare (Left) */}
              <Knob 
                label="Snare"
                value={stems.snare.mode === 'gain' ? stems.snare.gain : stems.snare.threshold}
                onChange={(v) => handleDrumKnobChange('snare', stems.snare.mode, v)}
                mode={stems.snare.mode}
                onToggleMode={() => toggleDrumMode('snare')}
                min={stems.snare.mode === 'gain' ? 0 : -60}
                max={stems.snare.mode === 'gain' ? 100 : 0}
                unit={stems.snare.mode === 'gain' ? '%' : 'dB'}
                className="absolute bottom-0 left-4"
              />

              {/* Hi-Hat (Right) */}
              <Knob 
                label="Hi-Hat"
                value={stems.hihat.mode === 'gain' ? stems.hihat.gain : stems.hihat.threshold}
                onChange={(v) => handleDrumKnobChange('hihat', stems.hihat.mode, v)}
                mode={stems.hihat.mode}
                onToggleMode={() => toggleDrumMode('hihat')}
                min={stems.hihat.mode === 'gain' ? 0 : -60}
                max={stems.hihat.mode === 'gain' ? 100 : 0}
                unit={stems.hihat.mode === 'gain' ? '%' : 'dB'}
                className="absolute bottom-0 right-4"
              />

              {/* Connection Lines (Visual only) */}
              <svg className="absolute inset-0 w-full h-full -z-10 opacity-10" viewBox="0 0 400 300">
                <path d="M200 80 L100 220 M200 80 L300 220 M100 220 L300 220" stroke="white" strokeWidth="1" fill="none" strokeDasharray="4 4" />
              </svg>
            </div>
          </section>

          {/* Main Stems (Vertical Sliders) */}
          <section className="lg:col-span-7 bg-zinc-900/30 border border-zinc-800/50 rounded-3xl p-8">
            <div className="flex items-center justify-between mb-12">
              <h2 className="text-sm font-black uppercase tracking-[0.3em] text-zinc-500 italic">Stem Mixer</h2>
              <div className="flex gap-2">
                <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                <span className="text-[10px] font-bold text-zinc-500 uppercase">Real-time Engine</span>
              </div>
            </div>

            <div className="grid grid-cols-4 gap-4">
              <VerticalSlider 
                label="Vocals"
                value={stems.vocals}
                onChange={(v) => handleStemChange('vocals', v)}
                color="bg-purple-500"
              />
              <VerticalSlider 
                label="Bass"
                value={stems.bass}
                onChange={(v) => handleStemChange('bass', v)}
                color="bg-blue-500"
              />
              <VerticalSlider 
                label="Other"
                value={stems.other}
                onChange={(v) => handleStemChange('other', v)}
                color="bg-zinc-500"
              />
              <VerticalSlider 
                label="Main"
                value={stems.main}
                onChange={(v) => handleStemChange('main', v)}
                color="bg-orange-500"
              />
            </div>
          </section>
        </div>

        {/* RhythmForge handoff bar */}
        <div
          className={cn(
            'mt-8 p-5 rounded-2xl border items-center justify-between gap-4 flex-wrap',
            stemUrls.vocals && stemUrls.drums
              ? 'flex bg-violet-500/5 border-violet-500/20'
              : 'hidden'
          )}
        >
          <div className="flex flex-col gap-[3px]">
            <span className="font-mono text-[0.6rem] uppercase tracking-[0.18em] text-violet-500">RhythmForge</span>
            <span className="text-xs text-zinc-500">Vocal + drum stems ready — send directly for analysis</span>
          </div>
          <button
            className={cn(
              'flex items-center gap-2 bg-violet-500 text-white border-none rounded-[10px] px-5 h-10 font-bold text-xs tracking-[0.08em] uppercase whitespace-nowrap transition-all',
              isSendingToRhythmForge ? 'opacity-80 cursor-not-allowed' : 'hover:bg-violet-600 active:scale-95'
            )}
            disabled={isSendingToRhythmForge}
            onClick={sendToRhythmForge}
          >
            <span className={isSendingToRhythmForge ? 'opacity-60' : ''}>Analyze in RhythmForge</span>
            {isSendingToRhythmForge && <div className="w-[14px] h-[14px] rounded-full border-2 border-white/30 border-t-white animate-spin" />}
          </button>
        </div>
      </main>

      {/* Settings Modal */}
      <AnimatePresence>
        {showSettings && (
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[100] flex items-center justify-center p-6 bg-black/80 backdrop-blur-md"
          >
            <motion.div 
              initial={{ scale: 0.9, y: 20 }}
              animate={{ scale: 1, y: 0 }}
              className="bg-zinc-900 border border-zinc-800 rounded-3xl p-8 w-full max-w-lg shadow-2xl"
            >
              <div className="flex items-center justify-between mb-8">
                <h2 className="text-xl font-bold">Backend Configuration</h2>
                <button onClick={() => setShowSettings(false)} className="text-zinc-500 hover:text-white">✕</button>
              </div>

              <div className="space-y-6">
                <div className="space-y-2">
                  <label className="text-xs font-bold text-zinc-500 uppercase tracking-widest">Hugging Face Space URL</label>
                  <input 
                    type="text" 
                    value={hfUrl}
                    onChange={(e) => setHfUrl(e.target.value)}
                    placeholder="https://user-stemforge.hf.space"
                    className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-4 py-3 text-sm focus:border-orange-500 outline-none transition-colors"
                  />
                  <p className="text-[10px] text-zinc-600">Enter your deployed HF Space URL to enable real AI processing.</p>
                </div>

                <div className="p-4 bg-orange-500/5 border border-orange-500/10 rounded-xl flex gap-4">
                  <Info className="w-5 h-5 text-orange-500 shrink-0" />
                  <p className="text-xs text-zinc-400 leading-relaxed">
                    By default, this app runs in <span className="text-orange-500 font-bold italic underline">Simulation Mode</span> for demonstration. 
                    Deploy the provided <code className="bg-zinc-800 px-1 rounded">app.py</code> to a Hugging Face Space (ZeroGPU) to unlock full stem separation.
                  </p>
                </div>

                <button 
                  onClick={() => setShowSettings(false)}
                  className="w-full bg-zinc-100 text-black py-3 rounded-xl font-bold hover:bg-orange-500 transition-colors"
                >
                  SAVE CONFIGURATION
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Footer */}
      <footer className="max-w-7xl mx-auto px-6 py-12 border-t border-zinc-900 mt-12">
        <div className="flex flex-col md:flex-row justify-between items-center gap-6">
          <div className="flex items-center gap-2 opacity-30">
            <Activity className="w-4 h-4" />
            <span className="text-[10px] font-bold uppercase tracking-[0.2em]">StemForge Engine v4.0.1-stable</span>
          </div>
          <div className="flex gap-8">
            <a href="#" className="text-[10px] font-bold text-zinc-600 hover:text-zinc-400 uppercase tracking-widest">Documentation</a>
            <a href="#" className="text-[10px] font-bold text-zinc-600 hover:text-zinc-400 uppercase tracking-widest">API Reference</a>
            <a href="#" className="text-[10px] font-bold text-zinc-600 hover:text-zinc-400 uppercase tracking-widest">Hugging Face</a>
          </div>
        </div>
      </footer>
    </div>
  );
};
