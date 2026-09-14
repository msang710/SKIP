/** Terminal state requires this exact user message and its host turn ID. */
export class TurnReceipt {
  private turn?: string;
  private terminal?: "finished" | "failed" | "cancelled";
  private accepted = false;
  private emitted = false;
  constructor(private messageKey: string, private report: (state: "finished" | "failed" | "cancelled", turn: string) => void) {}
  event(event: { type: string; turnId?: string; item?: { type: string; messageId?: string; clientMessageId?: string } }) {
    if (event.type === "timeline" && event.item?.type === "user_message" &&
        (event.item.messageId === this.messageKey || event.item.clientMessageId === this.messageKey) && event.turnId) this.turn = event.turnId;
    if (!this.turn || event.turnId !== this.turn) return;
    if (event.type === "turn_completed") this.terminal = "finished";
    if (event.type === "turn_failed") this.terminal = "failed";
    if (event.type === "turn_canceled") this.terminal = "cancelled";
    this.flush();
  }
  acknowledge() { this.accepted = true; this.flush(); }
  private flush() {
    if (this.accepted && this.terminal && this.turn && !this.emitted) {
      this.emitted = true; this.report(this.terminal, this.turn);
    }
  }
}
