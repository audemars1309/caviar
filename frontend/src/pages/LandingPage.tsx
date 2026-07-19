import { Link } from "react-router";

import { Button } from "@/components/ui/button";
import { PATHS } from "@/routes/paths";
import { APP_TAGLINE } from "@/utils/constants";

export default function LandingPage() {
  return (
    <section className="mx-auto flex max-w-3xl flex-col items-center gap-6 px-6 py-24 text-center">
      <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">
        Know exactly how ready you are.
      </h1>
      <p className="max-w-xl text-muted-foreground">
        Caviar is {APP_TAGLINE.toLowerCase()}: resume intelligence, adaptive AI interviews, and
        evidence-based readiness scoring.
      </p>
      <div className="flex gap-3">
        <Button asChild size="lg">
          <Link to={PATHS.signup}>Get started</Link>
        </Button>
        <Button asChild size="lg" variant="outline">
          <Link to={PATHS.login}>Sign in</Link>
        </Button>
      </div>
    </section>
  );
}
