import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate } from "react-router";
import { toast } from "sonner";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { useSignup } from "@/features/auth/hooks";
import { signupSchema, type SignupValues } from "@/features/auth/schemas";
import { PATHS } from "@/routes/paths";

export function SignupForm() {
  const signup = useSignup();
  const navigate = useNavigate();
  const [needsConfirmation, setNeedsConfirmation] = useState(false);

  const form = useForm<SignupValues>({
    resolver: zodResolver(signupSchema),
    defaultValues: { email: "", password: "", confirmPassword: "" },
  });

  const onSubmit = form.handleSubmit((values) => {
    signup.mutate(values, {
      onSuccess: ({ needsConfirmation: pending }) => {
        if (pending) {
          setNeedsConfirmation(true);
        } else {
          toast.success("Account created.");
          void navigate(PATHS.dashboard, { replace: true });
        }
      },
    });
  });

  if (needsConfirmation) {
    return (
      <Alert>
        <AlertDescription>
          Check your inbox: confirm your email address, then sign in.
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Create your account</CardTitle>
        <CardDescription>Start evaluating your interview readiness.</CardDescription>
      </CardHeader>
      <CardContent>
        <Form {...form}>
          <form onSubmit={(event) => void onSubmit(event)} className="space-y-4" noValidate>
            {signup.isError ? (
              <Alert variant="destructive">
                <AlertDescription>{signup.error.message}</AlertDescription>
              </Alert>
            ) : null}
            <FormField
              control={form.control}
              name="email"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Email</FormLabel>
                  <FormControl>
                    <Input type="email" autoComplete="email" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="password"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Password</FormLabel>
                  <FormControl>
                    <Input type="password" autoComplete="new-password" {...field} />
                  </FormControl>
                  <FormDescription>At least 8 characters.</FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="confirmPassword"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Confirm password</FormLabel>
                  <FormControl>
                    <Input type="password" autoComplete="new-password" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <Button type="submit" className="w-full" disabled={signup.isPending}>
              {signup.isPending ? <Spinner className="text-primary-foreground" /> : null}
              Create account
            </Button>
          </form>
        </Form>
        <p className="mt-4 text-center text-sm text-muted-foreground">
          Already have an account?{" "}
          <Link className="font-medium text-foreground underline-offset-4 hover:underline" to={PATHS.login}>
            Sign in
          </Link>
        </p>
      </CardContent>
    </Card>
  );
}
