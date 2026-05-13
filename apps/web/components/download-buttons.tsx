import { Download } from "lucide-react";
import { apiUrl } from "@/lib/api";
import type { JobResult } from "@/lib/types";

const DOWNLOADS: Array<{
  key: keyof JobResult;
  label: string;
}> = [
  { key: "midi_url", label: "MIDI" },
  { key: "musicxml_url", label: "MusicXML" },
  { key: "lily_url", label: "LilyPond (.ly)" },
  { key: "abc_url", label: "ABC notation" },
  { key: "numbered_json_url", label: "简谱 JSON" },
  { key: "notes_url", label: "音符 JSON" },
];

export function DownloadButtons({ result }: { result: JobResult }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {DOWNLOADS.map((download) => {
        const href = result[download.key];
        return (
          <a
            key={download.key}
            href={apiUrl(typeof href === "string" ? href : null)}
            download
            className={`inline-flex min-h-11 items-center justify-center gap-2 border px-4 py-2 text-sm font-semibold transition ${
              href
                ? "border-ink/15 bg-white text-ink hover:border-staff hover:text-staff"
                : "pointer-events-none border-ink/10 bg-ink/5 text-ink/35"
            }`}
          >
            <Download className="h-4 w-4" aria-hidden="true" />
            {download.label}
          </a>
        );
      })}
    </div>
  );
}
