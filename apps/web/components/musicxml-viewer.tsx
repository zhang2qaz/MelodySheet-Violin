"use client";

import { useEffect, useRef, useState } from "react";
import { AlertCircle } from "lucide-react";
import { apiUrl } from "@/lib/api";

export function MusicXmlViewer({ musicXmlUrl }: { musicXmlUrl: string | null }) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function renderMusicXml() {
      if (!musicXmlUrl || !containerRef.current) {
        return;
      }
      setLoading(true);
      setError(null);
      containerRef.current.innerHTML = "";

      try {
        const [{ OpenSheetMusicDisplay }, response] = await Promise.all([
          import("opensheetmusicdisplay"),
          fetch(apiUrl(musicXmlUrl), { cache: "no-store" }),
        ]);
        if (!response.ok) {
          throw new Error("无法下载 MusicXML 文件。");
        }
        const xml = await response.text();
        if (cancelled || !containerRef.current) {
          return;
        }
        const osmd = new OpenSheetMusicDisplay(containerRef.current, {
          autoResize: true,
          backend: "svg",
          drawTitle: false,
        });
        await osmd.load(xml);
        if (!cancelled) {
          osmd.render();
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : "五线谱渲染失败。请下载 MusicXML 文件检查内容。",
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    renderMusicXml();

    return () => {
      cancelled = true;
    };
  }, [musicXmlUrl]);

  return (
    <section className="border border-ink/10 bg-white/65 p-5 shadow-soft">
      <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase text-staff">五线谱</p>
          <h2 className="text-2xl font-semibold text-ink">生成的旋律谱</h2>
        </div>
        {loading ? <span className="text-sm text-ink/60">正在渲染 MusicXML...</span> : null}
      </div>

      {error ? (
        <div className="mb-4 flex items-start gap-2 border border-rosin/25 bg-rosin/10 p-4 text-sm text-rosin">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <span>{error} 你仍然可以在下方下载 MusicXML 文件。</span>
        </div>
      ) : null}

      <div
        ref={containerRef}
        className="osmd-container min-h-[260px] overflow-x-auto bg-white px-2 py-4"
      />
    </section>
  );
}
