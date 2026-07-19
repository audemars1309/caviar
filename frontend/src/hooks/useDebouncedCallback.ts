import { useCallback, useEffect, useMemo, useRef } from "react";

/** Debounce a callback; the latest invocation wins. `flush` runs any
 *  pending call immediately (used on blur/unmount so edits are never
 *  lost); `cancel` drops it. All mutable state lives in refs and is
 *  only touched inside event callbacks - never during render. */
export function useDebouncedCallback<TArgs extends unknown[]>(
  callback: (...args: TArgs) => void,
  delayMs: number,
) {
  const callbackRef = useRef(callback);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingArgsRef = useRef<TArgs | null>(null);

  useEffect(() => {
    callbackRef.current = callback;
  }, [callback]);

  const invoke = useCallback(() => {
    timerRef.current = null;
    const args = pendingArgsRef.current;
    if (args) {
      pendingArgsRef.current = null;
      callbackRef.current(...args);
    }
  }, []);

  const debounced = useCallback(
    (...args: TArgs) => {
      pendingArgsRef.current = args;
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(invoke, delayMs);
    },
    [delayMs, invoke],
  );

  const flush = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    invoke();
  }, [invoke]);

  const cancel = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = null;
    pendingArgsRef.current = null;
  }, []);

  // Flush pending work on unmount so the last edit is never lost.
  useEffect(() => flush, [flush]);

  return useMemo(() => ({ run: debounced, flush, cancel }), [debounced, flush, cancel]);
}
