/**
 * Tiny external store: is the API server currently unreachable and being
 * retried (e.g. a sleeping free-tier host waking up)? Read it in React with
 * useSyncExternalStore.
 *
 * It counts the requests that are retrying, so with two concurrent reads the
 * first to finish does not hide the banner while the other still waits.
 */
type Listener = () => void;

let retrying = 0;
let waking = false;
const listeners = new Set<Listener>();

function sync() {
  const next = retrying > 0;
  if (next === waking) return;
  waking = next;
  listeners.forEach((l) => l());
}

export const serverStatus = {
  /** A request started retrying. Pair every call with one `endWaking`. */
  beginWaking() {
    retrying++;
    sync();
  },
  endWaking() {
    retrying = Math.max(0, retrying - 1);
    sync();
  },
  subscribe(listener: Listener) {
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  },
  getSnapshot: () => waking,
  getServerSnapshot: () => false,
};
