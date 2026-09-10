/** Expected Core failures are data, not uncaught plugin handler errors. */
export async function rpcResult(action: () => Promise<any>) {
  try { return await action(); }
  catch (error) {
    const code = typeof (error as any)?.code === "string" ? (error as any).code : "UNAVAILABLE";
    return { status: "error", code, error: message(code) };
  }
}
export function message(code: string) {
  if (code === "OUTCOME_UNKNOWN") return "처리 결과를 확인하지 못했습니다. 작업 상태를 확인해 주세요.";
  if (code === "STALE" || code === "CONFLICT") return "기록이 변경되어 최신 내용을 불러왔습니다. 선택을 확인해 주세요.";
  if (code === "CONTEXT_EXPIRED" || code === "TARGET_CHANGED" || code === "CONNECTION_LOST") return "연결을 갱신했습니다. 내용을 확인한 뒤 다시 진행해 주세요.";
  return "요청을 완료하지 못했습니다. 잠시 후 다시 시도해 주세요.";
}
export function reconnectable(code: string) { return code === "CONTEXT_EXPIRED" || code === "TARGET_CHANGED" || code === "CONNECTION_LOST"; }
