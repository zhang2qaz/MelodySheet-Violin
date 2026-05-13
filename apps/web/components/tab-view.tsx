"use client";

import { useEffect, useState } from "react";
import { Guitar } from "lucide-react";
import { apiUrl } from "@/lib/api";

type TabNote = {
  start_time: number;
  midi_number: number;
  pitch: string;
  string?: number;  // 0 = low E, 5 = high E
  fret?: number;
  out_of_range?: boolean;
};

export function TabView({ tabUrl }: { tabUrl: string | null }) {
  const [notes, setNotes] = useState<TabNote[] | null>(null);

  useEffect(() => {
    if (!tabUrl) return;
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch(apiUrl(tabUrl), { cache: "no-store" });
        if (!r.ok) return;
        const data = (await r.json()) as { notes: TabNote[] };
        if (!cancelled) setNotes(data.notes || []);
      } catch {
        /* silent */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [tabUrl]);

  if (!tabUrl || !notes || notes.length === 0) return null;

  // Render as 6-row table; each note is a column.
  const stringLabels = ["e", "B", "G", "D", "A", "E"]; // top → bottom (high → low)
  return (
    <section className="border border-ink/10 bg-white/65 p-5 shadow-soft">
      <div className="mb-3 flex items-center gap-2 text-sm font-semibold uppercase text-staff">
        <Guitar className="h-4 w-4" aria-hidden="true" />
        吉他六线谱（自动推荐指位）
      </div>
      <p className="mb-3 text-sm leading-6 text-ink/65">
        把识别到的旋律映射成标准调弦（EADGBE）的吉他指位,贪心算法选低把位 + 同弦优先。
        即使目标乐器不是吉他,也能让吉他玩家直接照着弹。
      </p>
      <div className="overflow-x-auto bg-white p-3 font-mono text-xs">
        <div className="inline-block min-w-full">
          {stringLabels.map((label, rowIdx) => {
            // rowIdx 0 = high E (top); string index 5 = high E
            const stringIndex = 5 - rowIdx;
            return (
              <div key={label} className="flex items-center whitespace-nowrap">
                <span className="mr-1 w-3 text-ink/55">{label}|</span>
                {notes.map((n, i) => {
                  let cell = "─";
                  if (n.out_of_range) cell = "X";
                  else if (n.string === stringIndex && n.fret !== undefined)
                    cell = String(n.fret);
                  return (
                    <span
                      key={i}
                      className={`inline-block min-w-[1.5em] px-0.5 text-center ${
                        cell !== "─" && cell !== "X" ? "font-semibold text-rosin" : "text-ink/40"
                      }`}
                    >
                      {cell}
                    </span>
                  );
                })}
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
