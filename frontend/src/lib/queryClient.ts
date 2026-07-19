/**
 * TanStack Query configuration (Phase 9A): server state lives here, not
 * in Zustand. Conservative retry (no retry on 4xx client errors), sane
 * staleness, and a global mutation error hook that surfaces API errors
 * as toasts unless the mutation opts out via meta.silent.
 */
import { MutationCache, QueryCache, QueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { getApiErrorMessage, isClientError } from "@/services/api/errors";

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        gcTime: 5 * 60_000,
        refetchOnWindowFocus: false,
        retry: (failureCount, error) => !isClientError(error) && failureCount < 2,
      },
      mutations: { retry: 0 },
    },
    queryCache: new QueryCache({
      onError: (error, query) => {
        if (query.meta?.silent) return;
        toast.error(getApiErrorMessage(error));
      },
    }),
    mutationCache: new MutationCache({
      onError: (error, _variables, _context, mutation) => {
        if (mutation.meta?.silent) return;
        toast.error(getApiErrorMessage(error));
      },
    }),
  });
}

export const queryClient = createQueryClient();
