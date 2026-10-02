/**
 * Tiny external store: is the API server currently unreachable and being
 * retried (e.g. a sleeping free-tier host waking up)? Read it in React with
 * useSyncExternalStore.
 */
type Listener = () => void;

let waking = false;
const listeners = new Set<Listener>();

export const serverStatus = {
  setWaking(next: boolean) {
    if (waking === next) return;
    waking = next;
    listeners.forEach((l) => l());
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
