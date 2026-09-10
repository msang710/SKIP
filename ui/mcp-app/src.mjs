import { App } from '@modelcontextprotocol/ext-apps';
import { selectionMessage, unpack } from './view-model.mjs';
const app = new App({ name: 'SKIP', version: '0.3.0-dev.1' }, {});
const root = document.getElementById('app');
let current;
function el(tag, text, parent = root) { const n = document.createElement(tag); if (text !== undefined) n.textContent = text; parent.append(n); return n; }
function show(value) {
  current = value; root.replaceChildren();
  el('h1', 'SKIP'); el('p', '필요한 결정과 확인된 결과만 읽으세요.');
  if (!value || value.status === 'error') { el('p', value?.error ?? '현재 기록을 기다리고 있습니다.'); return; }
  const data = value.data;
  if (data?.items) {
    if (!data.items.length) el('p', '현재 표시할 결정이 없습니다.');
    for (const card of data.items) {
      const section = el('section'); el('small', '결정 필요', section); el('h2', card.fields.question, section);
      const form = el('fieldset', undefined, section); el('legend', '선택지', form);
      let chosen;
      for (const option of card.children.options) {
        const label = el('label', undefined, form), radio = el('input', undefined, label);
        radio.type = 'radio'; radio.name = card.id; radio.value = option.option_id;
        radio.addEventListener('change', () => { chosen = option.option_id; button.disabled = !app.getHostCapabilities()?.message; });
        el('span', `${option.label}${option.recommended ? ' · 추천' : ''}`, label);
        el('p', option.consequences, label);
      }
      el('p', card.fields.rationale, section); el('p', `위험: ${card.fields.risk_summary}`, section);
      if (card.selection) el('p', `저장된 선택: ${card.children.options.find(o => o.option_id === card.selection.option_id)?.label}`, section);
      const button = el('button', '선택을 현재 대화에 전달', section); button.disabled = true;
      const note = el('p', '확정은 이 호스트의 실제 사용자 입력 확인을 거칩니다.', section);
      button.addEventListener('click', async () => {
        button.disabled = true;
        try {
          const result = await app.sendMessage({ role: 'user', content: [{ type: 'text', text: selectionMessage(value.project_id, card, chosen) }] });
          note.textContent = result.isError ? '호스트가 전달을 거절했습니다.' : '대화 전달을 요청했습니다. 선택 확정과 실행 여부는 호스트에서 확인합니다.';
        } catch { note.textContent = '전달 여부를 확인할 수 없습니다. 대화를 확인하세요.'; }
      });
      if (!app.getHostCapabilities()?.message) el('p', '이 호스트에서는 대화에서 선택을 알려주세요.', section);
    }
  } else if (data?.facts) {
    el('h2', '결과'); for (const fact of data.facts) el('p', `${fact.statement} · ${fact.freshness === 'current' ? '현재 확인' : '재확인 필요'}`);
    el('h2', '확인'); for (const c of data.checks) el('p', `${c.result === 'PASS' ? '✓' : '!'} ${c.summary} · ${c.surface} · ${c.result}`);
    el('h2', '남은 일'); for (const r of data.remaining) el('p', `! ${r.description} · ${r.state}`);
  }
  const detail = el('details'); el('summary', '상세 기록', detail); el('pre', JSON.stringify(value, null, 2), detail);
}
app.ontoolresult = result => show(unpack(result));
app.onhostcontextchanged = context => { if (context.theme) document.documentElement.dataset.theme = context.theme; };
app.onteardown = async () => { current = undefined; root.replaceChildren(); return {}; };
await app.connect();
const host = app.getHostContext(); if (host?.theme) document.documentElement.dataset.theme = host.theme;
if (current) show(current);
