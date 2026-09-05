type SkeletonProps = {
  className?: string;
};

export function Skeleton({ className }: SkeletonProps) {
  return <div className={`rounded-lg bg-raised motion-safe:animate-shimmer ${className ?? ""}`} />;
}
