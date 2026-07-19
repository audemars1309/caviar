import { Spinner } from "@/components/ui/spinner";

export function LoadingScreen({ label = "Loading" }: { label?: string }) {
  return (
    <div className="flex min-h-[50vh] items-center justify-center" aria-busy>
      <Spinner className="size-6" label={label} />
    </div>
  );
}
