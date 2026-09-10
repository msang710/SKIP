/** Exact viewed revision, with full native fields; never an instruction to execute. */
export function recordAttachment(projectId: string, record: any, title: string) {
  if (!record?.id || !record?.kind || !Number.isInteger(record.revision)) throw new Error("첨부할 기록의 버전을 확인하지 못했습니다.");
  return {sourceId:"intent-invocation",item:{
    id:`${projectId}:${record.kind}:${record.id}:${record.revision}`,identifier:record.id,title,
    url:`https://local.skip.invalid/projects/${encodeURIComponent(projectId)}/records/${record.kind}/${encodeURIComponent(record.id)}/${record.revision}`,
    resourceType:"skip-record",
    text:JSON.stringify({schema:"skip-record-attachment/v1",project_id:projectId,record,
      notice:"사용자가 고른 기록의 스냅샷입니다. 첨부는 실행 승인이 아닙니다. 작업 전 Core에서 현재 결정·선택과 유효성을 다시 확인하세요."}),
  }};
}

export function recordCaller(projectId: string, record: any) {
  if (!/^[A-Za-z0-9_.-]+$/.test(projectId) || !record?.id || !Number.isInteger(record.revision)) throw new Error("기록 선택자를 확인하지 못했습니다.");
  const input=JSON.stringify({kind:record.kind,id:record.id,revision:record.revision});
  const quoted="'"+input.replace(/'/g,"'\\''")+"'";
  return `$skip --project ${projectId} query record --input ${quoted}`;
}
