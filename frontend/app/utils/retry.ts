/**
 * Retry a failing async call once (or `retries` times) after a short delay.
 * Covers transient network blips / backend restarts — the common case where
 * the exact same request would succeed a moment later.
 */
export async function withRetry<T>(fn: () => Promise<T>, retries = 1, delayMs = 800): Promise<T> {
  try {
    return await fn()
  } catch (e) {
    // Errors that opt out of retry (ApiError with retryable === false: timeouts
    // and deterministic server/AI failures) surface immediately — re-firing a
    // 90s timeout or a guaranteed-500 just doubles the wait. Anything else
    // (fast network blips, backend restarts) is retried once.
    if (retries <= 0 || (e as { retryable?: boolean })?.retryable === false) throw e
    await new Promise(r => setTimeout(r, delayMs))
    return withRetry(fn, retries - 1, delayMs)
  }
}
