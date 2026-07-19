import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useDebouncedCallback } from "@/hooks/useDebouncedCallback";

describe("useDebouncedCallback", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("debounces: only the last call within the window fires", () => {
    const spy = vi.fn();
    const { result } = renderHook(() => useDebouncedCallback(spy, 500));
    act(() => {
      result.current.run("a");
      result.current.run("b");
      result.current.run("c");
    });
    expect(spy).not.toHaveBeenCalled();
    void act(() => vi.advanceTimersByTime(500));
    expect(spy).toHaveBeenCalledTimes(1);
    expect(spy).toHaveBeenCalledWith("c");
  });

  it("flush runs the pending call immediately", () => {
    const spy = vi.fn();
    const { result } = renderHook(() => useDebouncedCallback(spy, 500));
    act(() => {
      result.current.run("draft");
      result.current.flush();
    });
    expect(spy).toHaveBeenCalledExactlyOnceWith("draft");
    void act(() => vi.advanceTimersByTime(1000));
    expect(spy).toHaveBeenCalledTimes(1); // no double fire
  });

  it("cancel drops the pending call", () => {
    const spy = vi.fn();
    const { result } = renderHook(() => useDebouncedCallback(spy, 500));
    act(() => {
      result.current.run("draft");
      result.current.cancel();
      vi.advanceTimersByTime(1000);
    });
    expect(spy).not.toHaveBeenCalled();
  });

  it("flushes pending work on unmount so edits are not lost", () => {
    const spy = vi.fn();
    const { result, unmount } = renderHook(() => useDebouncedCallback(spy, 500));
    act(() => result.current.run("last-edit"));
    unmount();
    expect(spy).toHaveBeenCalledExactlyOnceWith("last-edit");
  });

  it("flush with nothing pending is a no-op", () => {
    const spy = vi.fn();
    const { result } = renderHook(() => useDebouncedCallback(spy, 500));
    act(() => result.current.flush());
    expect(spy).not.toHaveBeenCalled();
  });
});
