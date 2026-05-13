"use client";

import { useEffect, useRef, useState } from "react";
import { AlertCircle, FileText, Loader2 } from "lucide-react";
import { apiUrl } from "@/lib/api";

export function MusicXmlViewer({ musicXmlUrl }: { musicXmlUrl: string | null }) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [exportingPdf, setExportingPdf] = useState(false);

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
          drawTitle: true,
          drawSubtitle: true,
          drawComposer: true,
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

  async function handleExportPdf() {
    if (!containerRef.current) return;
    setExportingPdf(true);
    try {
      const svgs = Array.from(containerRef.current.querySelectorAll("svg"));
      if (svgs.length === 0) {
        throw new Error("还没有渲染好的乐谱，请稍候再试。");
      }

      // jspdf + svg2pdf.js handle SVG → PDF conversion entirely client-side.
      // We lay each OSMD page on its own PDF page using A4 portrait and let
      // svg2pdf preserve the underlying vector data so the export stays
      // resolution-independent (great for printing at home).
      const [{ default: jsPDFModule }, svg2pdfModule] = await Promise.all([
        import("jspdf"),
        import("svg2pdf.js"),
      ]);
      const JsPDFCtor = (jsPDFModule as unknown as { jsPDF?: typeof import("jspdf").jsPDF }).jsPDF
        || (jsPDFModule as unknown as typeof import("jspdf").jsPDF);
      const svg2pdf = (svg2pdfModule as unknown as { svg2pdf?: typeof import("svg2pdf.js").svg2pdf }).svg2pdf
        || (svg2pdfModule as unknown as { default?: typeof import("svg2pdf.js").svg2pdf }).default;

      const pdf = new JsPDFCtor({ orientation: "portrait", unit: "pt", format: "a4" });
      const pageWidth = pdf.internal.pageSize.getWidth();
      const pageHeight = pdf.internal.pageSize.getHeight();
      const margin = 28;

      for (let i = 0; i < svgs.length; i += 1) {
        const svgEl = svgs[i];
        // Pick a width/height by reading attributes; fall back to client rect.
        const widthAttr = svgEl.getAttribute("width") || `${svgEl.clientWidth}`;
        const heightAttr = svgEl.getAttribute("height") || `${svgEl.clientHeight}`;
        const intrinsicW = parseFloat(widthAttr) || 800;
        const intrinsicH = parseFloat(heightAttr) || 1100;
        const scale = Math.min(
          (pageWidth - margin * 2) / intrinsicW,
          (pageHeight - margin * 2) / intrinsicH,
          1.0,
        );
        const drawW = intrinsicW * scale;
        const drawH = intrinsicH * scale;
        if (i > 0) pdf.addPage();
        if (!svg2pdf) {
          throw new Error("svg2pdf.js 加载失败。");
        }
        await svg2pdf(svgEl, pdf, {
          x: (pageWidth - drawW) / 2,
          y: margin,
          width: drawW,
          height: drawH,
        });
      }

      pdf.save("melody-sheet.pdf");
    } catch (err) {
      setError(err instanceof Error ? err.message : "PDF 导出失败。");
    } finally {
      setExportingPdf(false);
    }
  }

  return (
    <section className="border border-ink/10 bg-white/65 p-5 shadow-soft">
      <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase text-staff">五线谱</p>
          <h2 className="text-2xl font-semibold text-ink">生成的旋律谱</h2>
        </div>
        <div className="flex items-center gap-3">
          {loading ? <span className="text-sm text-ink/60">正在渲染 MusicXML...</span> : null}
          {musicXmlUrl && !loading ? (
            <button
              type="button"
              onClick={handleExportPdf}
              disabled={exportingPdf}
              className="inline-flex min-h-10 items-center gap-2 border border-ink/15 bg-white px-3 py-1.5 text-sm font-semibold text-ink shadow-soft transition hover:border-staff hover:text-staff disabled:cursor-not-allowed disabled:opacity-60"
            >
              {exportingPdf ? (
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <FileText className="h-4 w-4" aria-hidden="true" />
              )}
              {exportingPdf ? "导出中..." : "导出 PDF"}
            </button>
          ) : null}
        </div>
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
