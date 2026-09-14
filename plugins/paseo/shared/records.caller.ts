export type CallerRecord = {
  projectId: string;
  scope: "now" | "history";
  goal?: string;
  artifact: string;
};

export function recordCaller(record: CallerRecord): string {
  const project = `--project ${record.projectId}`;
  if (record.scope === "now") {
    return `$skip ${project} --now${record.goal ? ` --goal ${record.goal}` : ""}`;
  }
  const artifact = record.artifact.replaceAll("_", "-");
  return `$skip ${project}${record.goal ? ` --goal ${record.goal}` : ""} --artifacts ${artifact}`;
}
