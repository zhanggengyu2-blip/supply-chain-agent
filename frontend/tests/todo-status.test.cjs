const test = require('node:test');
const assert = require('node:assert/strict');
const {todoStatus} = require('../.test-dist/todo-status.js');

test('checkpoint completion and legacy completion use the rendered completed state', () => {
  const checkpoint = ['completed', 'in_progress', 'pending'];
  const rendered = checkpoint.map(todoStatus);
  assert.deepEqual(rendered, checkpoint);
  assert.equal(rendered.filter(x => x === 'completed').length, 1);
  assert.equal(todoStatus('complete'), 'completed');
  assert.equal(todoStatus(undefined), 'pending');
});
