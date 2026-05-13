"use client";

import { useEffect, useState } from "react";
import { Drum } from "lucide-react";
import { apiUrl } from "@/lib/api";

type DrumHit = {
  time: number;
  instrument: "kick" | "snare" | "hat" | string;
  confidence: number;
};

const INST_LABELS: Record<string, { zh: string; color: string }> = {
  kick: { zh: "底鼓", color: "bg-rosin/30 text-rosin" },
  snare: { zh: "军鼓", color: "bg-staff/25 text-staff" },
  hat: { zh: "踩镲", color: "bg-ink/15 text-ink" },
};

export function DrumsView({ drumsUrl }: { drumsUrl: string | null }) {
  const [hits, setHits] = useState<DrumHit[] | null>(null);

  useEffect(() => {
    if (!drumsUrl) return;
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch(apiUrl(drumsUrl), { cache: "no-store" });
        if (!r.ok) return;
        const data = (await r.json()) as { hits: DrumHit[] };
        if (!cancelled) setHits(data.hits || []);
      } catch {
        /* silent */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [drumsUrl]);

  if (!drumsUrl || !hits || hits.length === 0) return null;
  const counts = hits.reduce<Record<string, number>>((acc, h) => {
    acc[h.instrument] = (acc[h.instrument] || 0) + 1;
    return acc;
  }, {});

  return (
    <section className="border border-ink/10 bg-white/65 p-5 shadow-soft">
      <div className="mb-3 flex items-center gap-2 text-sm font-semibold uppercase text-staff">
        <Drum className="h-4 w-4" aria-hidden="true" />
        鼓点识别（{hits.length} 个鼓点）
      </div>
      <p className="mb-3 text-sm leading-6 text-ink/65">
        基于频段能量分类的鼓声识别（底鼓 / 军鼓 / 踩镲）。需要 Demucs 已安装并把鼓 stem 分离;否则在
        完整混音上跑准确率会下降。
      </p>
      <div className="mb-3 flex gap-2 text-xs">
        {Object.entries(counts).map(([inst, count]) => {
          const meta = INST_LABELS[inst] || { zh: inst, color: "bg-ink/10 text-ink" };
          return (
            <span key={inst} className={`border border-ink/15 px-2 py-1 ${meta.color}`}>
              {meta.zh} × {count}
            </span>
          );
        })}
      </div>
      <div className="overflow-x-auto bg-white p-2 font-mono text-xs">
        <div className="inline-flex items-center gap-px whitespace-nowrap">
          {hits.slice(0, 200).map((h, i) => {
            const meta = INST_LABELS[h.instrument] || { zh: "?", color: "bg-ink/10 text-ink/60" };
            return (
              <span
                key={i}
                className={`min-w-[2.5em] border border-ink/10 px-1 py-0.5 text-center ${meta.color}`}
                title={`t=${h.time.toFixed(2)}s · ${h.instrument} · ${(h.confidence * 100).toFixed(0)}%`}
                style={{ opacity: Math.max(0.5, h.confidence) }}
              >
                {meta.zh[0]}
              </span>
            );
          })}
          {hits.length > 200 ? (
            <span className="ml-2 text-ink/40">…+{hits.length - 200}</span>
          ) : null}
        </div>
      </div>
    </section>
  );
}
