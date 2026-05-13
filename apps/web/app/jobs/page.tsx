"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { JobPageClient } from "@/components/job-page-client";

function JobPageInner() {
  const params = useSearchParams();
  const jobId = params.get("id");
  if (!jobId) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-16 text-ink">
        <h1 className="text-2xl font-semibold">未找到任务 ID</h1>
        <p className="mt-4 text-ink/70">
          请回到首页重新上传音频。
        </p>
      </main>
    );
  }
  return <JobPageClient jobId={jobId} />;
}

export default function JobPage() {
  return (
    <Suspense fallback={<div className="mx-auto max-w-3xl px-6 py-16 text-ink/60">正在加载...</div>}>
      <JobPageInner />
    </Suspense>
  );
}
