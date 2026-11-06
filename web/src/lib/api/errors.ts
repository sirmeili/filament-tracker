import { ApiError } from "#lib/api/client.ts";

/** A sentence for a failed request, to show on the page. */
export function describeError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 0) return "Cannot reach the server.";
    if (error.status === 403) return "Your role cannot do that.";
    if (error.status === 404) return "Not found. It may have been removed.";
    return error.message.endsWith(".") ? error.message : `${error.message}.`;
  }
  return "Something went wrong. Try again.";
}
