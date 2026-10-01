"""Execute production frontend functions for catalog and editor regressions."""

import shutil
import subprocess
from pathlib import Path

import pytest

STATIC = Path(__file__).parents[1] / "src" / "paper_factory" / "web_static"


def run_frontend(assertions):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required to execute frontend regression checks")
    bootstrap = r'''
const fs = require("fs");
const vm = require("vm");
const assert = require("assert");
const nodes = new Map();
const makeNode = (value = "") => ({value, innerHTML: "", querySelectorAll: () => []});
const document = {
  activeElement: null,
  querySelector: selector => nodes.get(selector) || null,
  querySelectorAll: () => [],
};
const source = fs.readFileSync(process.argv[1], "utf8");
const context = vm.createContext({document, nodes, makeNode, assert, URL, console});
vm.runInContext(source.slice(0, source.indexOf('\ndocument.addEventListener("click"')), context);
Promise.resolve(vm.runInContext(process.argv[2], context)).catch(error => {
  console.error(error);
  process.exitCode = 1;
});
'''
    result = subprocess.run([node, "-e", bootstrap, str(STATIC / "app.js"), assertions],
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr


def test_catalog_accepts_missing_and_null_repository():
    run_frontend(r'''
assert.equal(repo({repository: null}), "");
assert.equal(repo({repository: {name: "owner/project"}}), "owner/project");
assert.equal(repo({source: "https://github.com/owner/project"}), "owner/project");
state.search = "Fixture";
const study = {title: "Fixture", repository: null, files: []};
assert.equal(visible([study]).length, 1);
assert.ok(paperCard(study, 0).includes("Fixture"));
''')


def test_manuscript_refresh_and_stage_switch_preserve_unsaved_prose():
    run_frontend(r'''
state.selectedProject = "web-test";
state.stage = "manuscript";
state.projectDetail = {status: "ready", records: {paper: [{id: "paper-1", title: "Saved title"}]}, files: []};
state.canonical = {
  paper_id: "paper-1", study_id: "study-1", title: "Saved title",
  sections: [{heading: "Results", blocks: [{kind: "prose", text: "Saved paragraph"}]}],
  limitations: ["Saved limitation"],
};
nodes.set("#canonical-title", makeNode("Unsaved author title"));
nodes.set("#canonical-limitations", makeNode("Unsaved limitation"));
nodes.set("#canonical-form", {
  querySelectorAll: selector => selector === "[data-section-heading]"
    ? [{dataset: {sectionHeading: "0"}, value: "Edited results"}]
    : [{dataset: {proseSection: "0", proseBlock: "0"}, value: "Unsaved author paragraph"}],
});
nodes.set("#project-dialog", {open: false});
nodes.set("#project-title", makeNode());
nodes.set("#project-subtitle", makeNode());
nodes.set("#manuscript-editor", makeNode());
let body = "";
nodes.set("#project-dialog-body", {
  get innerHTML() {return body;},
  set innerHTML(value) {
    body = value;
    nodes.delete("#canonical-form");
    nodes.delete("#canonical-title");
    nodes.delete("#canonical-limitations");
    nodes.set("#manuscript-editor", makeNode());
  },
  querySelectorAll: () => [],
});
renderProject();
assert.equal(state.canonical.title, "Unsaved author title");
assert.ok(nodes.get("#manuscript-editor").innerHTML.includes("Unsaved author paragraph"));
assert.ok(nodes.get("#manuscript-editor").innerHTML.includes("Edited results"));
state.stage = "files";
renderProject();
state.stage = "manuscript";
renderProject();
assert.ok(nodes.get("#manuscript-editor").innerHTML.includes("Unsaved author title"));
assert.ok(nodes.get("#manuscript-editor").innerHTML.includes("Unsaved limitation"));
assert.ok(body.includes('value="paper-1" selected'));
''')


def test_production_markup_uses_stylesheet_rules_under_strict_csp():
    source = (STATIC / "app.js").read_text(encoding="utf-8")
    index = (STATIC / "index.html").read_text(encoding="utf-8")
    assert 'style="' not in source + index
    run_frontend(r'''
state.projectDetail = {files: [], records: {}};
assert.ok(literatureStage().includes('class="field field-count"'));
assert.ok(manuscriptStage().includes('class="author-fields"'));
''')


def test_runner_readiness_identifies_native_windows_backend():
    run_frontend(r'''
state.agent = {provider: {ready: true}, runner: {ready: true, backend: "windows-appcontainer"}};
assert.ok(agentReadiness().includes("Windows 네이티브 실험 환경"));
assert.ok(!agentReadiness().includes("Docker 격리 실험 환경"));
state.agent.runner = {ready: true, backend: "docker"};
assert.ok(agentReadiness().includes("Docker 격리 실험 환경"));
''')


def test_effective_cli_readiness_is_independent_of_connection_operations():
    run_frontend(r'''
state.agent = {provider: {ready: true, authentication: "chatgpt"}, runner: {ready: false}};
state.modelConnection = {status: "disconnected", authentication: "logged_out", connected: false};
assert.ok(agentReadiness().includes('status-badge ready'));
assert.ok(agentReadiness().includes("현재 사용되는 ChatGPT 구독 로그인을 확인했습니다"));
assert.ok(connectionPanel().includes("현재 구독 로그인을 사용할 수 있습니다"));
assert.ok(connectionPanel().includes("새 계정 연결 전"));
assert.ok(!connectionPanel().includes('data-action="probe-model"'));
state.agent.provider = {ready: false, available: true, authenticated: true};
state.modelConnection = {status: "authenticated", authentication: "chatgpt", connected: false};
assert.ok(!agentReadiness().includes('status-badge ready'));
assert.ok(connectionPanel().includes('data-action="probe-model"'));
''')


def test_cli_prerequisite_diagnostics_distinguish_installation_capabilities_and_auth():
    run_frontend(r'''
state.agent = {provider: {ready: false, executable_available: false}, runner: {ready: false}};
assert.ok(agentReadiness().includes("공식 Codex CLI를 찾지 못했습니다"));
state.agent.provider = {ready: false, executable_available: true, authentication: "chatgpt", capabilities_supported: false, missing_capabilities: ["--ignore-user-config"]};
assert.ok(agentReadiness().includes("필요한 기능을 지원하지 않습니다"));
assert.ok(agentReadiness().includes("--ignore-user-config"));
state.agent.provider = {ready: false, executable_available: true, authentication: "api_key", capabilities_supported: true};
assert.ok(agentReadiness().includes("API 키로 로그인되어 있습니다"));
''')


def test_refresh_accepts_current_flat_connection_contract_and_clears_stale_private_state():
    run_frontend(r'''
(async () => {
  updateConnection = () => {};
  render = () => {};
  updateProjectJob = () => {};
  notice = () => {};
  nodes.set("#project-dialog", {open: false});
  let readOnly = false;
  let failConnection = false;
  const connection = {status: "waiting_user", user_code: "STALE-CODE", authentication: "unknown"};
  api = async path => {
    if (path === "/api/health") return {writes_enabled: !readOnly};
    if (path === "/api/agent/status") return {provider: {ready: false}, runner: {ready: false}};
    if (path === "/api/agent/connection") {
      if (failConnection) throw new Error("Connection endpoint unavailable");
      return connection;
    }
    return {};
  };
  await refresh({silent: true});
  assert.equal(state.modelConnection, connection);
  assert.ok(connectionPanel().includes("STALE-CODE"));
  failConnection = true;
  readOnly = true;
  await refresh({silent: true});
  assert.equal(state.modelConnection, null);
  assert.equal(state.modelConnectionFetchError, "");
  assert.ok(!connectionPanel().includes("STALE-CODE"));
  state.modelConnection = connection;
  readOnly = false;
  await refresh({silent: true});
  assert.equal(state.modelConnection, null);
  assert.equal(state.modelConnectionFetchError, "Connection endpoint unavailable");
})()
''')


def test_connection_action_uses_current_flat_response():
    run_frontend(r'''
(async () => {
  render = () => {};
  refresh = async () => {};
  nodes.set("#project-dialog", {open: false});
  const connection = {status: "probing", connected: true, model_available: false};
  api = async (path, options) => {
    assert.equal(path, "/api/agent/connection/probe");
    assert.equal(options.method, "POST");
    return connection;
  };
  await changeModelConnection("probe");
  assert.equal(state.modelConnection, connection);
  assert.equal(state.modelConnectionBusy, false);
})()
''')
