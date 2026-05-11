export const ASSISTANT_ACTIVITY_EVENT = "moradins:assistant-activity";

export interface AssistantActivityEventDetail {
  action: "open" | "run-started";
  runId?: string;
}

function dispatchAssistantActivity(detail: AssistantActivityEventDetail) {
  if (typeof window === "undefined") {
    return;
  }
  window.dispatchEvent(new CustomEvent<AssistantActivityEventDetail>(ASSISTANT_ACTIVITY_EVENT, { detail }));
}

export function openAssistantActivity(runId?: string) {
  dispatchAssistantActivity({ action: "open", runId });
}

export function notifyAssistantRunStarted(runId: string) {
  dispatchAssistantActivity({ action: "run-started", runId });
}
