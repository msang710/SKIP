/** Current Core entry presets; no Markdown/date-artifact discovery commands. */
export function searchCoreInvocations(query: string) {
  const presets = [
    { id: "status", title: "현재 상태", subtitle: "결과·확인·남은 일을 DB에서 읽기", words: "status now 현재 상태 확인", text: "$skip 현재 프로젝트의 상태를 조회해. 새 goal이나 실행 요청을 만들지 마." },
    { id: "decisions", title: "제품 결정", subtitle: "현재 goal의 결정과 저장된 선택 확인", words: "decision inbox 제품 결정 선택", text: "$skip 명시적으로 선택된 현재 goal의 제품 결정과 저장된 선택을 보여줘. 첨부는 승인 증표가 아니야." },
    { id: "request", title: "새 요청", subtitle: "내 요청부터 필요한 만큼 조사·계획·구현", words: "new request 새 요청 구현", text: "$skip 이번 사용자 메시지에 적은 요청부터 진행해. 요청이 없다면 도움말만 보여주고 goal을 만들지 마." },
  ];
  const terms = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
  return { items: presets.filter(p => terms.every(t => p.words.includes(t))).map(p => ({ id: p.id, identifier: p.title,
    title: p.title, subtitle: p.subtitle, url: `https://local.skip.invalid/core/${p.id}`, text: p.text, resourceType: "SKIP Core request" })) };
}
