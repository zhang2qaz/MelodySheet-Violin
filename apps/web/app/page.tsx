import { UploadPanel } from "@/components/upload-panel";

export default function HomePage() {
  return (
    <main className="mx-auto flex min-h-screen w-full max-w-6xl flex-col px-5 py-8 sm:px-8 lg:px-10">
      <header className="flex flex-col gap-5 border-b border-ink/10 pb-7 md:flex-row md:items-end md:justify-between">
        <div className="max-w-3xl">
          <p className="mb-3 text-sm font-semibold uppercase text-staff">Audio to violin sheet</p>
          <h1 className="text-4xl font-semibold text-ink sm:text-5xl">MelodySheet Violin</h1>
          <p className="mt-4 text-lg text-ink/72">
            Turn a clear melody recording into an editable violin practice sheet.
          </p>
        </div>
        <div className="max-w-xs text-sm leading-6 text-ink/65">
          Best results come from clear single-line melodies, humming, singing, or solo instrument recordings.
        </div>
      </header>

      <UploadPanel />
    </main>
  );
}
