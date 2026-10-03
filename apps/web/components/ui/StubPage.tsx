import { EmptyState } from "./EmptyState";
import { PageHeader } from "./PageHeader";
import { ClockIcon } from "./icons";

export function StubPage({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div>
      <PageHeader title={title} description={description} />
      <EmptyState className="mt-6" icon={<ClockIcon size={20} />}>
        Not available yet. This page is planned for a later release.
      </EmptyState>
    </div>
  );
}
