import { JobPageClient } from "@/components/job-page-client";

type JobPageProps = {
  params: Promise<{
    jobId: string;
  }>;
};

export default async function JobPage({ params }: JobPageProps) {
  const { jobId } = await params;
  return <JobPageClient jobId={jobId} />;
}
