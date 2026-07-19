/** Typed API error handling shared by the client, query layer, and UI. */
import axios from "axios";

import { ApiError, type ApiErrorBody } from "@/types/api";

export function toApiError(error: unknown): ApiError {
  // axios.isAxiosError is the robust check (instanceof can fail across
  // realms and for adapter-produced errors).
  if (error instanceof ApiError) return error;
  if (axios.isAxiosError(error)) {
    const body = error.response?.data as ApiErrorBody | undefined;
    return new ApiError({
      status: error.response?.status ?? 0,
      code: body?.error?.code ?? (error.response ? "http_error" : "network_error"),
      message:
        body?.error?.message ??
        (error.response ? "The request failed." : "Cannot reach the Caviar server."),
      details: body?.error?.details,
    });
  }
  return new ApiError({ status: 0, code: "unknown_error", message: "Something went wrong." });
}

export function getApiErrorMessage(error: unknown): string {
  return toApiError(error).message;
}

export function isClientError(error: unknown): boolean {
  const status = toApiError(error).status;
  return status >= 400 && status < 500;
}
