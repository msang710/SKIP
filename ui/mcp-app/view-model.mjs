export function unpack(result) {
  if (result.structuredContent) return result.structuredContent;
  const content = result.content?.find(item => item.type === 'text');
  try { return JSON.parse(content?.text ?? '{}'); } catch { return { status: 'error', error: '기록 형식을 읽을 수 없습니다.' }; }
}
export function selectionMessage(project, card, option) {
  if (!card.children.options.some(o => o.option_id === option)) throw new Error('Invalid option');
  return 'SKIP 사용자 선택\n' + JSON.stringify({ schema: 'skip-user-selection/v1', project_id: project,
    decision_id: card.id, revision: card.revision, option_id: option });
}
