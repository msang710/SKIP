import {deviceStorage,subscribeStorage} from "./web";
/** UI-wide on this client; never project policy or agent authority. */
const pinnedKey = "skip.ui.pin-goals";
let memory = false;
const listeners = new Set<() => void>();
export function readPinned(storage = deviceStorage()) {
  try {
    const saved = storage?.getItem(pinnedKey);
    if (saved !== null && saved !== undefined) return saved === "true";
  } catch {}
  return memory;
}
export function savePinned(value: boolean, storage = deviceStorage()) {
  memory = value;
  try { storage?.setItem(pinnedKey, String(value)); } catch {}
  for (const listener of listeners) listener();
}
export function subscribePinned(listener: () => void) {
  listeners.add(listener);
  const stop=subscribeStorage(pinnedKey,value=>{memory=value==="true";listener();});
  return ()=>{listeners.delete(listener);stop();};
}
