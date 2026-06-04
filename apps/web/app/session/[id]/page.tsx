import { SessionExperience } from "@/components/session-experience";

export default async function SessionPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <SessionExperience key={id} sessionId={id} />;
}
