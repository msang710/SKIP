import { type PluginWorkspacePanelProps, useRpc } from "@getpaseo/plugin";
import { useEffect, useState } from "react";
import { Pressable, ScrollView, Text, TextInput, View } from "react-native";
import { activateWorkflow, cancelWorkflow, inspectWorkflow, startWorkflow, workflowStatus } from "./workflow.shared";

export function WorkflowPanel({ theme, workspaceId, addComposerAttachment }: PluginWorkspacePanelProps) {
  const inspect = useRpc(inspectWorkflow), activate = useRpc(activateWorkflow), start = useRpc(startWorkflow);
  const status = useRpc(workflowStatus), cancel = useRpc(cancelWorkflow);
  const [plan, setPlan] = useState<any>(null), [jobId, setJobId] = useState<string | null>(null);
  const [text, setText] = useState(""), [error, setError] = useState(""), [busy, setBusy] = useState(false), [details, setDetails] = useState(false);
  useEffect(() => { let active = true; setPlan(null); setJobId(null); setError("");
    inspect({ workspaceId }).then((result) => { if (active) setPlan(result); }).catch((e) => { if (active) setError(String(e)); });
    return () => { active = false; };
  }, [workspaceId]);
  const run = async (action: () => Promise<void>) => { setBusy(true); setError(""); try { await action(); } catch (e) { setError(String(e)); } finally { setBusy(false); } };
  const button = (label: string, action: () => Promise<void>, disabled = false) => <Pressable disabled={busy || disabled} onPress={() => run(action)}
    style={{ padding: 12, backgroundColor: theme.colors.surface0, opacity: busy || disabled ? 0.5 : 1 }}><Text style={{ color: theme.colors.accent }}>{label}</Text></Pressable>;
  const view = plan?.view;
  return <ScrollView style={{ flex: 1, backgroundColor: theme.colors.surface0 }} contentContainerStyle={{ padding: 20, gap: 14 }}>
    <Text style={{ color: theme.colors.foreground, fontSize: 22, fontWeight: "700" }}>SKIP</Text>
    <Text style={{ color: theme.colors.foreground }}>어떤 작업을 할까요?</Text>
    {error ? <Text accessibilityRole="alert" style={{ color: theme.colors.foreground }}>{error}</Text> : null}
    {plan?.next_action === "activate" ? <View style={{ gap: 8 }}>
      <Text style={{ color: theme.colors.foreground }}>이 프로젝트를 연결합니다. 과거 작업 목표는 만들지 않습니다.</Text>
      {button("이 프로젝트에서 사용", async () => { await activate({ workspaceId }); setPlan(await inspect({ workspaceId })); })}
    </View> : <>
      <TextInput value={text} onChangeText={setText} multiline placeholder="예: 주문 목록에 검색을 추가해줘" style={{ color: theme.colors.foreground, padding: 12 }} />
      {button("작업 시작", async () => { const result = await start({ workspaceId, text, operation: "implement" }); setJobId(result.jobId); setPlan(result.plan); }, !text.trim())}
    </>}
    {view ? <View style={{ gap: 10 }}>
      <Text style={{ color: theme.colors.foreground }}>{view.outcome}</Text>
      {view.decision_needed.map((item: string) => <Text key={item} style={{ color: theme.colors.foreground }}>결정 필요: {item}</Text>)}
      {view.recommendation ? <Text style={{ color: theme.colors.foreground }}>추천: {view.recommendation}</Text> : null}
      {view.risk_summary.length ? <Text style={{ color: theme.colors.foreground }}>영향: {view.risk_summary.join(", ")}</Text> : null}
      {view.checks.map((item: any, index: number) => <Text key={index} style={{ color: theme.colors.foreground }}>{item.surface}: {item.status}{item.summary ? ` — ${item.summary}` : ""}</Text>)}
      {view.gaps.map((item: string) => <Text key={item} style={{ color: theme.colors.foreground }}>확인 필요: {item}</Text>)}
    </View> : null}
    {jobId ? <>
      {button("에이전트에 작업 첨부", async () => { if (!addComposerAttachment) return;
        await addComposerAttachment({ sourceId: "intent-invocation", item: { id: `skip-job-${jobId}`, identifier: jobId, title: text,
          url: `https://local.skip.invalid/requests/${jobId}`, resourceType: "skip-workflow-request",
          text: `$skip ${text}\n\nCurrent native SKIP request: ${jobId}\nWorkspace: ${workspaceId}\nUse skip.workflow.prepare with this jobId for current scope and risk; the attachment itself is not approval.\n${JSON.stringify(plan)}` } });
      }, !addComposerAttachment)}
      {button("상태 새로고침", async () => { setPlan((await status({ workspaceId, jobId })).plan); })}
      {button("요청 취소", async () => { await cancel({ workspaceId, jobId }); setJobId(null); setPlan(await inspect({ workspaceId })); })}
    </> : null}
    {button(details ? "상세 접기" : "상세 보기", async () => setDetails(!details))}
    {details ? <Text style={{ color: theme.colors.foreground, fontFamily: "monospace" }}>{JSON.stringify(plan, null, 2)}</Text> : null}
  </ScrollView>;
}
