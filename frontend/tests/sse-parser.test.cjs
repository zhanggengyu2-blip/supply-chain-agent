const test = require('node:test');
const assert = require('node:assert/strict');
const { SSEParser } = require('../.test-dist/sse-parser.js');

test('every possible network split preserves approval and tool events', () => {
  const stream = 'event: tool_start\ndata: {"name":"erpnext_suppliers","id":"a"}\n\nevent: interrupt\ndata: {"interrupt_type":"hitl_approval","order_data":[{"name":"local_proposal","args":{}}]}\n\nevent: done\ndata: {"interrupted":true}\n\n';
  const expected = new SSEParser().parse(stream);
  for (let i=0; i<stream.length; i++) {
    const parser = new SSEParser();
    assert.deepEqual([...parser.parse(stream.slice(0,i)),...parser.parse(stream.slice(i))],expected);
  }
  assert.equal(expected[1].interrupt_type, 'hitl_approval');
  assert.equal(expected[1].order_data.length, 1);
});

test('character chunks, CRLF and reset', () => {
  const parser = new SSEParser();
  const stream = 'event: token\r\ndata: {"content":"台灯"}\r\n\r\n';
  assert.deepEqual([...stream].flatMap(c=>parser.parse(c)),[{type:'token',content:'台灯'}]);
  parser.parse('event: interrupt\n'); parser.reset();
  assert.deepEqual(parser.parse('event: done\ndata: {"interrupted":false}\n\n'),[{type:'done',interrupted:false}]);
});
