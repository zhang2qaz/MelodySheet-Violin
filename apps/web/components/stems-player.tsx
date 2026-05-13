"use client";

import { Layers } from "lucide-react";
import { apiUrl } from "@/lib/api";

const STEM_LABELS: Record<string, string> = {
  vocals: "人声",
  drums: "鼓",
  bass: "贝斯",
  guitar: "吉他",
  piano: "钢琴",
  other: "其他(弦/管/打击)",
};

export function StemsPlayer({ stems }: { stems: Record<string, string> }) {
  const keys = Object.keys(stems || {});
  if (keys.length === 0) return null;

  return (
    <section className="border border-ink/10 bg-white/65 p-5 shadow-soft">
      <div className="mb-3 flex items-center gap-2 text-sm font-semibold uppercase text-staff">
        <Layers className="h-4 w-4" aria-hidden="true" />
        分轨试听（Demucs 六轨分离）
      </div>
      <p className="mb-3 text-sm leading-6 text-ink/65">
        AI 已经把原始混音切成单独的乐器轨。每条都能独立播放和下载,
        可以拿去做卡拉 OK、伴奏移除、单独练琴。
      </p>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {keys.map((stem) => (
          <div key={stem} className="flex flex-col gap-2 border border-ink/15 bg-white p-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold text-ink">
                {STEM_LABELS[stem] || stem}
              </span>
              <a
                href={apiUrl(stems[stem])}
                download
                className="text-xs text-staff hover:underline"
              >
                下载
              </a>
            </div>
            <audio src={apiUrl(stems[stem])} controls className="w-full" />
          </div>
        ))}
      </div>
    </section>
  );
}
