type SkeletonProps = {
  className?: string;
};

export function Skeleton({ className }: SkeletonProps) {
  return <div className={`animate-shimmer rounded-lg bg-raised ${className ?? ""}`} />;
}
