"use client";

import { useEffect, useState } from "react";
import { LayoutList } from "lucide-react";
import { apiUrl } from "@/lib/api";

type Section = { start_time: number; end_time: number; label: string };

const SECTION_COLORS = [
  "bg-staff/20 text-staff border-staff/40",
  "bg-rosin/20 text-rosin border-rosin/40",
  "bg-ink/15 text-ink border-ink/35",
  "bg-amber-500/20 text-amber-700 border-amber-500/40",
  "bg-emerald-500/20 text-emerald-700 border-emerald-500/40",
  "bg-violet-500/20 text-violet-700 border-violet-500/40",
];

function colorForLabel(label: string): string {
  const idx = label.charCodeAt(0) - 65;
  return SECTION_COLORS[Math.max(0, idx) % SECTION_COLORS.length];
}

export function SectionsView({ sectionsUrl }: { sectionsUrl: string | null }) {
  const [sections, setSections] = useState<Section[] | null>(null);

  useEffect(() => {
    if (!sectionsUrl) return;
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch(apiUrl(sectionsUrl), { cache: "no-store" });
        if (!r.ok) return;
        const data = (await r.json()) as { sections: Section[] };
        if (!cancelled) setSections(data.sections || []);
      } catch {
        /* silent */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [sectionsUrl]);

  if (!sectionsUrl || !sections || sections.length < 2) return null;
  const totalDur = sections[sections.length - 1].end_time;

  return (
    <section className="border border-ink/10 bg-white/65 p-5 shadow-soft">
      <div className="mb-3 flex items-center gap-2 text-sm font-semibold uppercase text-staff">
        <LayoutList className="h-4 w-4" aria-hidden="true" />
        段落结构（{sections.length} 段)
      </div>
      <p className="mb-3 text-sm leading-6 text-ink/65">
        基于 MFCC 相似度聚类的段落划分。相同字母代表音色 / 和声相似的段落 — 比如 A-B-A-B-C-B
        通常对应 主歌-副歌-主歌-副歌-桥段-副歌 这种流行结构。
      </p>
      <div className="flex w-full overflow-hidden rounded border border-ink/15">
        {sections.map((s, i) => {
          const widthPct = ((s.end_time - s.start_time) / totalDur) * 100;
          return (
            <div
              key={i}
              className={`relative flex items-center justify-center border-r border-ink/15 px-1 py-3 text-sm font-semibold last:border-r-0 ${colorForLabel(s.label)}`}
              style={{ width: `${widthPct}%` }}
              title={`${s.start_time.toFixed(1)}s - ${s.end_time.toFixed(1)}s (${(s.end_time - s.start_time).toFixed(1)}s)`}
            >
              {widthPct > 4 ? s.label : ""}
            </div>
          );
        })}
      </div>
      <div className="mt-2 flex justify-between text-xs text-ink/50">
        <span>0:00</span>
        <span>
          {Math.floor(totalDur / 60)}:{Math.floor(totalDur % 60).toString().padStart(2, "0")}
        </span>
      </div>
    </section>
  );
}
