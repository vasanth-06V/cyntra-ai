import { ListSkeleton, Skeleton } from "@/components/ui/Skeleton";

/** Shown inside the dashboard shell while a page's server work streams in. */
export default function DashboardLoading() {
  return (
    <div>
      <Skeleton className="h-8 w-48" />
      <Skeleton className="mt-3 h-4 w-72 max-w-full" />
      <ListSkeleton className="mt-6 max-w-3xl" rows={3} />
    </div>
  );
}
