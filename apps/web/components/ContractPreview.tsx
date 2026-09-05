import { Skeleton } from "@/components/Skeleton";
import type { IntentContract } from "@/lib/schemas";

function rupees(amount: number): string {
  return `₹${amount.toLocaleString("en-IN")}`;
}

function Row({ label, value, index }: { label: string; value: string; index: number }) {
  return (
    <div
      className="animate-fade-up grid grid-cols-[8.5rem_1fr] gap-3 py-2"
      style={{ animationDelay: `${index * 70}ms` }}
    >
      <dt className="text-[10px] font-medium uppercase tracking-[0.18em] text-muted">{label}</dt>
      <dd className="font-mono text-sm tracking-[0.04em] text-ink">{value}</dd>
    </div>
  );
}

type ContractPreviewProps = {
  contract: IntentContract | null;
  status: "draft" | "active";
  loading?: boolean;
  error?: string | null;
};

export function ContractPreview({ contract, status, loading, error }: ContractPreviewProps) {
  const hard = contract?.hard_constraints;
  const prefs = contract?.preferences;
  const brands = prefs?.preferred_brands ?? [];

  return (
    <div className="flex flex-col gap-6 p-6 md:p-8">
      <div className="flex items-center justify-between">
        <p className="text-[10px] font-medium uppercase tracking-[0.18em] text-muted">
          Intent contract
        </p>
        <span
          className={`rounded-full px-3 py-1 text-[10px] font-medium uppercase tracking-[0.18em] ring-1 ${
            status === "active"
              ? "text-teal ring-teal/40"
              : "text-faint ring-hairline"
          }`}
        >
          {status}
        </span>
      </div>

      {error ? (
        <p className="max-w-[65ch] text-sm leading-relaxed text-block">{error}</p>
      ) : null}

      {loading ? (
        <div className="flex flex-col gap-4">
          <Skeleton className="h-10" />
          <Skeleton className="h-10" />
          <Skeleton className="h-10 w-2/3" />
        </div>
      ) : null}

      {!loading && !contract && !error ? (
        <div className="flex flex-col gap-6">
          <p className="max-w-[65ch] text-sm leading-relaxed text-muted">
            Compile the task to fill this contract. The agent cannot change it after you confirm.
          </p>
          <div>
            <p className="mb-2 text-[10px] font-medium uppercase tracking-[0.18em] text-muted">
              Hard constraints
            </p>
            <dl className="divide-y divide-hairline">
              <Row index={0} label="Max amount" value="—" />
              <Row index={1} label="Currency" value="—" />
              <Row index={2} label="Category" value="—" />
            </dl>
          </div>
          <div>
            <p className="mb-2 text-[10px] font-medium uppercase tracking-[0.18em] text-muted">
              Preferences
            </p>
            <p className="text-sm text-faint">None until compile</p>
          </div>
        </div>
      ) : null}

      {contract && hard ? (
        <div className="flex flex-col gap-6">
          <p className="text-base leading-relaxed text-ink">{contract.goal}</p>
          <div>
            <p className="mb-2 text-[10px] font-medium uppercase tracking-[0.18em] text-muted">
              Hard constraints
            </p>
            <dl className="divide-y divide-hairline">
              <Row index={0} label="Max amount" value={rupees(hard.max_amount)} />
              <Row index={1} label="Currency" value={hard.currency} />
              {hard.category ? <Row index={2} label="Category" value={hard.category} /> : null}
              <Row index={3} label="Quantity" value={String(hard.quantity)} />
              {hard.must_include.length > 0 ? (
                <Row index={4} label="Must include" value={hard.must_include.join(", ")} />
              ) : null}
            </dl>
          </div>
          <div>
            <p className="mb-2 text-[10px] font-medium uppercase tracking-[0.18em] text-muted">
              Preferences
            </p>
            {brands.length === 0 && !prefs?.weight && !prefs?.use_case ? (
              <p className="text-sm text-faint">None stated</p>
            ) : (
              <dl className="divide-y divide-hairline">
                {brands.length > 0 ? <Row index={5} label="Brands" value={brands.join(", ")} /> : null}
                {prefs?.weight ? <Row index={6} label="Weight" value={prefs.weight} /> : null}
                {prefs?.use_case ? <Row index={7} label="Use case" value={prefs.use_case} /> : null}
              </dl>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
