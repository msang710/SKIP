import test from 'node:test';
import assert from 'node:assert/strict';
import { unpack, selectionMessage } from '../view-model.mjs';
test('structured Core result and text fallback agree', () => {
 const value = { project_id: 'p', data: { items: [] } };
 assert.deepEqual(unpack({ structuredContent: value }), unpack({ content: [{ type: 'text', text: JSON.stringify(value) }] }));
});
test('a choice sends an exact revision request, never grants approval or starts a turn', () => {
 const card = { id: 'd', revision: 3, children: { options: [{ option_id: 'keep' }] } };
 const value = JSON.parse(selectionMessage('p', card, 'keep').split('\n')[1]);
 assert.deepEqual(value, { schema: 'skip-user-selection/v1', project_id: 'p', decision_id: 'd', revision: 3, option_id: 'keep' });
 assert.throws(() => selectionMessage('p', card, 'other'));
});
