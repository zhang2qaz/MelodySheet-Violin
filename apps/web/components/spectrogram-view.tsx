"use client";

import { useState } from "react";
import Image from "next/image";
import { Waves, AlertCircle } from "lucide-react";
import { apiUrl } from "@/lib/api";

export function SpectrogramView({ spectrogramUrl }: { spectrogramUrl: string | null }) {
  const [failed, setFailed] = useState(false);
  if (!spectrogramUrl) return null;
  const src = apiUrl(spectrogramUrl);

  return (
    <section className="border border-ink/10 bg-white/65 p-5 shadow-soft">
      <div className="mb-3 flex items-center gap-2 text-sm font-semibold uppercase text-staff">
        <Waves className="h-4 w-4" aria-hidden="true" />
        AI 看到的频谱
      </div>
      <p className="mb-3 text-sm leading-6 text-ink/65">
        亮的横线就是 AI 识别到的音高分量；颜色越亮说明该频段能量越强。
        竖向变化代表节奏起伏。可以对照五线谱，看是否对应得上。
      </p>
      {failed ? (
        <div className="flex items-start gap-2 border border-rosin/25 bg-rosin/10 p-3 text-sm text-rosin">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <span>频谱图加载失败。可能是这次任务尚未生成（旧版本兼容回退路径）。</span>
        </div>
      ) : (
        <div className="overflow-x-auto bg-white px-1 py-2">
          {/* next/image with unoptimized to keep things simple under static export */}
          <Image
            src={src}
            alt="audio spectrogram"
            width={1600}
            height={540}
            unoptimized
            onError={() => setFailed(true)}
            className="max-w-full h-auto"
          />
        </div>
      )}
    </section>
  );
}
