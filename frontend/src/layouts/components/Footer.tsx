import { APP_NAME } from "@/utils/constants";

export function Footer() {
  return (
    <footer className="border-t px-6 py-4 text-center text-xs text-muted-foreground">
      {APP_NAME} — Analyze. Simulate. Evaluate. Improve.
    </footer>
  );
}
