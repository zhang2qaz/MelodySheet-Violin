import { UploadPanel } from "@/components/upload-panel";

export default function HomePage() {
  return (
    <main className="mx-auto flex min-h-screen w-full max-w-6xl flex-col px-5 py-8 sm:px-8 lg:px-10">
      <header className="flex flex-col gap-5 border-b border-ink/10 pb-7 md:flex-row md:items-end md:justify-between">
        <div className="max-w-3xl">
          <p className="mb-3 text-sm font-semibold uppercase text-staff">音频转小提琴谱</p>
          <h1 className="text-4xl font-semibold text-ink sm:text-5xl">小提琴旋律谱</h1>
          <p className="mt-4 text-lg text-ink/72">
            把清晰的旋律录音转换成可编辑的小提琴练习谱。
          </p>
        </div>
        <div className="max-w-xs text-sm leading-6 text-ink/65">
          清晰的单旋律、哼唱、人声或独奏乐器录音，通常能得到更好的结果。
        </div>
      </header>

      <UploadPanel />
    </main>
  );
}
