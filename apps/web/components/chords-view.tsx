"use client";

import { useEffect, useState } from "react";
import { Music } from "lucide-react";
import { apiUrl } from "@/lib/api";
import type { ChordEvent, ChordsPayload } from "@/lib/types";

export function ChordsView({ chordsUrl }: { chordsUrl: string | null }) {
  const [chords, setChords] = useState<ChordEvent[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!chordsUrl) return;
    let cancelled = false;
    (async () => {
      try {
        const response = await fetch(apiUrl(chordsUrl), { cache: "no-store" });
        if (!response.ok) throw new Error("无法加载和弦数据");
        const data = (await response.json()) as ChordsPayload;
        if (!cancelled) setChords(data.chords || []);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "加载失败");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [chordsUrl]);

  if (!chordsUrl) return null;
  if (error)
    return (
      <section className="border border-ink/10 bg-white/65 p-5 shadow-soft">
        <p className="text-sm text-ink/55">和弦识别暂不可用：{error}</p>
      </section>
    );
  if (!chords) return null;
  if (chords.length === 0) {
    return (
      <section className="border border-ink/10 bg-white/65 p-5 shadow-soft">
        <p className="text-sm text-ink/55">未检测到清晰的和弦进行（可能音频较单薄或纯旋律）。</p>
      </section>
    );
  }

  function formatDuration(s: number): string {
    return s >= 1 ? `${s.toFixed(1)}s` : `${Math.round(s * 1000)}ms`;
  }

  return (
    <section className="border border-ink/10 bg-white/65 p-5 shadow-soft">
      <div className="mb-3 flex items-center gap-2 text-sm font-semibold uppercase text-staff">
        <Music className="h-4 w-4" aria-hidden="true" />
        和弦进行（AI 推断 · 共 {chords.length} 个变化）
      </div>
      <p className="mb-3 text-sm leading-6 text-ink/65">
        基于色度（chroma）分析推断的和弦序列。仅供参考 — 对纯主旋律录音准确率较低,
        对带伴奏的歌曲（钢琴/吉他/混音）效果更好。
      </p>
      <div className="flex flex-wrap gap-2">
        {chords.map((chord, idx) => {
          const dur = chord.end_time - chord.start_time;
          const opacity = Math.max(0.5, chord.confidence);
          return (
            <div
              key={`${chord.start_time}-${idx}`}
              title={`${chord.start_time.toFixed(2)}s - ${chord.end_time.toFixed(2)}s · 置信度 ${(chord.confidence * 100).toFixed(0)}%`}
              className="flex flex-col items-center border border-ink/15 bg-white px-3 py-2 text-center"
              style={{ opacity }}
            >
              <span className="text-base font-semibold text-ink">{chord.chord}</span>
              <span className="text-xs text-ink/50">{formatDuration(dur)}</span>
            </div>
          );
        })}
      </div>
    </section>
  );
}
