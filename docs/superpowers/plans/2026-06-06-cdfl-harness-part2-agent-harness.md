# CDFL Harness — Part 2: Agent Harness, Adapters, Demo & Docs — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **Prerequisite: Part 1 (`2026-06-06-cdfl-harness-part1-core-libraries.md`) is complete and its suite is green.**

**Goal:** Build the PLAN→EXECUTE→CRITIC agent loop with the Reasoning wiring (coverage gate, memory consolidation, empowerment, four-fold DE), the three real provider adapters (Anthropic/OpenAI/Ollama), a runnable demo, and the architecture documentation, completing the `cdfl_harness` gem at `D:\CDFL harness`.

**Architecture:** `Agent::Session` owns the loop and the only Store writes; `Planner`/`Executor`/`Critic` are pure transforms. The Gateway (Part 1) is the LLM chokepoint. The critic runs the Grounding gate ("học 1 hiểu 10"); a successful, non-dry session consolidates into the memory palace; irreversible steps get empowerment consent advice; the result carries a four-fold DE dashboard.

**Tech Stack:** Ruby ≥ 3.1, RSpec + WebMock, stdlib `net/http`/`json`/`securerandom`. Builds on Part 1.

**Conventions:** gem root `D:\CDFL harness`; paths relative to it; module `CDFLHarness`; run commands from the gem root.

---

## Phase 10 — Agent workflows

### Task 10.1: Workflow + Workflows registry

**Files:**
- Create: `lib/cdfl_harness/agent/workflow.rb`
- Create: `lib/cdfl_harness/agent/workflows.rb`
- Test: `spec/agent/workflows_spec.rb`

Port of `agents/workflows.py` (workflow definition + registry; input_schema, allowed_tools, prompt builders, flags).

- [ ] **Step 1: Write the failing test**

```ruby
# spec/agent/workflows_spec.rb
# frozen_string_literal: true

RSpec.describe CDFLHarness::Agent::Workflow do
  it "builds a workflow with prompt callables and flag defaults" do
    wf = described_class.new(
      workflow_id: "insight-to-action",
      input_schema: { "type" => "object", "required" => ["question"],
                      "properties" => { "question" => { "type" => "string" } } },
      allowed_tools: %w[retrieve_evidence draft_action],
      planner_prompt: ->(input) { "Plan for: #{input['question']}" },
      critic_prompt: ->(_plan, _ts, input) { "Review answer to: #{input['question']}" }
    )
    expect(wf.workflow_id).to eq("insight-to-action")
    expect(wf.llm_critic).to be(true)
    expect(wf.requires_grounding).to be(false)
    expect(wf.planner_prompt.call({ "question" => "x" })).to eq("Plan for: x")
    expect(wf.allowed_tools).to include("retrieve_evidence")
  end
end

RSpec.describe CDFLHarness::Agent::Workflows do
  it "registers and fetches workflows; raises for unknown" do
    reg = described_class.new
    wf = CDFLHarness::Agent::Workflow.new(
      workflow_id: "w", input_schema: { "type" => "object" }, allowed_tools: [],
      planner_prompt: ->(_i) { "p" }, critic_prompt: ->(_p, _t, _i) { "c" }
    )
    reg.register(wf)
    expect(reg.get("w")).to eq(wf)
    expect { reg.get("nope") }.to raise_error(CDFLHarness::Errors::WorkflowInputError)
  end
end
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bundle exec rspec spec/agent/workflows_spec.rb`
Expected: FAIL.

- [ ] **Step 3: Write the implementations**

```ruby
# lib/cdfl_harness/agent/workflow.rb
# frozen_string_literal: true

module CDFLHarness
  module Agent
    # A workflow definition. prompt builders are callables; flags control the
    # critic + grounding behaviour. static_plan (optional) skips the LLM planner.
    Workflow = Struct.new(
      :workflow_id, :input_schema, :allowed_tools,
      :planner_prompt, :critic_prompt, :static_plan,
      :llm_critic, :requires_grounding,
      keyword_init: true
    ) do
      def initialize(workflow_id:, input_schema:, allowed_tools:, planner_prompt:,
                     critic_prompt:, static_plan: nil, llm_critic: true, requires_grounding: false)
        super(workflow_id: workflow_id, input_schema: input_schema,
              allowed_tools: allowed_tools.to_a, planner_prompt: planner_prompt,
              critic_prompt: critic_prompt, static_plan: static_plan,
              llm_critic: llm_critic, requires_grounding: requires_grounding)
      end

      def allowed_tool?(name) = allowed_tools.include?(name)
    end
  end
end
```

```ruby
# lib/cdfl_harness/agent/workflows.rb
# frozen_string_literal: true

require_relative "../errors"
require_relative "workflow"

module CDFLHarness
  module Agent
    # Registry of built-in / project-defined workflows.
    class Workflows
      def initialize
        @workflows = {}
      end

      def register(workflow)
        @workflows[workflow.workflow_id] = workflow
        self
      end

      def get(workflow_id)
        @workflows[workflow_id] ||
          raise(Errors::WorkflowInputError, "unknown workflow: #{workflow_id}")
      end

      def all = @workflows.values
    end
  end
end
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bundle exec rspec spec/agent/workflows_spec.rb`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/cdfl_harness/agent/workflow.rb lib/cdfl_harness/agent/workflows.rb spec/agent/workflows_spec.rb
git commit -m "feat: Agent Workflow + Workflows registry"
```

---

## Phase 11 — Planner

### Task 11.1: Planner

**Files:**
- Create: `lib/cdfl_harness/agent/planner.rb`
- Test: `spec/agent/planner_spec.rb`

Port of `agents/planner.py` (PLAN_SCHEMA, tools block, allowed_tools enforcement, static_plan).

- [ ] **Step 1: Write the failing test**

```ruby
# spec/agent/planner_spec.rb
# frozen_string_literal: true

RSpec.describe CDFLHarness::Agent::Planner do
  def registry_with_echo
    reg = CDFLHarness::Tooling::Registry.new
    klass = Class.new(CDFLHarness::Tooling::Tool) do
      tool_name "retrieve_evidence"; description "find evidence"; scope "enterprise"
      parameters({ "type" => "object", "properties" => { "q" => { "type" => "string" } } })
      def call(_a, _c) = { "citations" => [] }
    end
    reg.register(klass.new)
    reg
  end

  def workflow(static: nil)
    CDFLHarness::Agent::Workflow.new(
      workflow_id: "w", input_schema: { "type" => "object" }, allowed_tools: %w[retrieve_evidence],
      planner_prompt: ->(_i) { "make a plan" }, critic_prompt: ->(_p, _t, _i) { "c" }, static_plan: static
    )
  end

  it "uses a static plan without calling the LLM" do
    static = ->(_input) { [CDFLHarness::Types::PlanStep.new(tool_name: "retrieve_evidence", args: { "q" => "x" }, rationale: "r")] }
    gw = CDFLHarness::Gateway::Client.new(
      config: CDFLHarness::Config.new.tap { |c| c.adapter_override = CDFLHarness::Gateway::Adapters::Fake.new(completions: []) }
    )
    plan, toks = described_class.new(gateway: gw).plan_workflow(workflow: workflow(static: static), input: {}, registry: registry_with_echo)
    expect(plan.steps.first.tool_name).to eq("retrieve_evidence")
    expect(toks).to eq(0)
  end

  it "parses a structured LLM plan and enforces allowed_tools" do
    completion = '{"steps":[{"tool_name":"retrieve_evidence","args":{"q":"x"},"rationale":"r"}],"rationale":"overall"}'
    gw = CDFLHarness::Gateway::Client.new(
      config: CDFLHarness::Config.new.tap { |c| c.adapter_override = CDFLHarness::Gateway::Adapters::Fake.new(completions: [completion]) }
    )
    plan, = described_class.new(gateway: gw).plan_workflow(workflow: workflow, input: {}, registry: registry_with_echo)
    expect(plan.steps.first.tool_name).to eq("retrieve_evidence")
  end

  it "raises when the LLM picks a tool not in allowed_tools" do
    completion = '{"steps":[{"tool_name":"evil","args":{},"rationale":"r"}],"rationale":"o"}'
    gw = CDFLHarness::Gateway::Client.new(
      config: CDFLHarness::Config.new.tap { |c| c.adapter_override = CDFLHarness::Gateway::Adapters::Fake.new(completions: [completion]) }
    )
    expect do
      described_class.new(gateway: gw).plan_workflow(workflow: workflow, input: {}, registry: registry_with_echo)
    end.to raise_error(ArgumentError, /not in workflow/)
  end
end
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bundle exec rspec spec/agent/planner_spec.rb`
Expected: FAIL.

- [ ] **Step 3: Write the implementation**

```ruby
# lib/cdfl_harness/agent/planner.rb
# frozen_string_literal: true

require "json"
require_relative "../types"
require_relative "../errors"

module CDFLHarness
  module Agent
    # Single LLM call → ordered tool steps (Plan). Port of agents/planner.py.
    class Planner
      PLAN_OUTPUT_SCHEMA = {
        "$schema" => "https://json-schema.org/draft/2020-12/schema",
        "type" => "object", "additionalProperties" => false,
        "required" => %w[steps rationale],
        "properties" => {
          "steps" => {
            "type" => "array", "minItems" => 1, "maxItems" => 10,
            "items" => {
              "type" => "object", "additionalProperties" => false,
              "required" => %w[tool_name args rationale],
              "properties" => {
                "tool_name" => { "type" => "string", "minLength" => 1 },
                "args" => { "type" => "object" },
                "rationale" => { "type" => "string", "maxLength" => 500 }
              }
            }
          },
          "rationale" => { "type" => "string", "maxLength" => 2000 }
        }
      }.freeze

      def initialize(gateway:)
        @gateway = gateway
      end

      # Returns [Plan, tokens_used].
      def plan_workflow(workflow:, input:, registry:, scope: "enterprise")
        if workflow.static_plan
          steps = workflow.static_plan.call(input)
          steps.each_with_index do |s, i|
            unless workflow.allowed_tool?(s.tool_name)
              raise ArgumentError, "static plan step #{i + 1} tool '#{s.tool_name}' not in workflow allowed_tools"
            end
          end
          return [Types::Plan.new(steps: steps, rationale: "(static plan — no LLM planner)"), 0]
        end

        tools_block = render_tools(registry, workflow.allowed_tools, scope)
        prompt = "#{workflow.planner_prompt.call(input)}\n\n#{tools_block}"
        parsed = @gateway.complete_structured(
          prompt: prompt, task: "agent.plan.#{workflow.workflow_id}",
          schema: PLAN_OUTPUT_SCHEMA, consent_external: false, max_tokens: 2000
        )

        steps = parsed.fetch("steps").map do |s|
          Types::PlanStep.new(tool_name: s["tool_name"], args: s["args"] || {}, rationale: s["rationale"] || "")
        end
        steps.each_with_index do |s, i|
          unless workflow.allowed_tool?(s.tool_name)
            raise ArgumentError, "planner picked tool '#{s.tool_name}' (step #{i + 1}) not in workflow allowed_tools=#{workflow.allowed_tools.sort}"
          end
        end
        [Types::Plan.new(steps: steps, rationale: parsed["rationale"] || ""), 0]
      end

      private

      def render_tools(registry, allowed, scope)
        lines = ["Tool có sẵn:"]
        registry.list_for_scope(scope).each do |tool|
          name = tool.class.tool_name
          next unless allowed.include?(name)

          lines << "  • #{name} — #{tool.class.description}\n      params: #{JSON.generate(tool.class.parameters)}"
        end
        if lines.size == 1
          raise Errors::ConfigError, "planner has no tools — workflow allowed_tools ∩ registry is empty"
        end

        lines.join("\n")
      end
    end
  end
end
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bundle exec rspec spec/agent/planner_spec.rb`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/cdfl_harness/agent/planner.rb spec/agent/planner_spec.rb
git commit -m "feat: Agent Planner (structured plan, allowed_tools enforcement, static_plan)"
```

---

## Phase 12 — Executor

### Task 12.1: Executor (dispatch + dry_run + empowerment advice)

**Files:**
- Create: `lib/cdfl_harness/agent/executor.rb`
- Test: `spec/agent/executor_spec.rb`

Port of `agents/executor.py`, adding empowerment advice for irreversible steps.

- [ ] **Step 1: Write the failing test**

```ruby
# spec/agent/executor_spec.rb
# frozen_string_literal: true

RSpec.describe CDFLHarness::Agent::Executor do
  def registry
    reg = CDFLHarness::Tooling::Registry.new
    ev = Class.new(CDFLHarness::Tooling::Tool) do
      tool_name "retrieve_evidence"; description "d"
      def call(_a, _c) = { "citations" => [{ "similarity" => 0.9 }] }
    end
    send_email = Class.new(CDFLHarness::Tooling::Tool) do
      tool_name "send_email"; description "d"
      def side_effect_class = "external"
      def call(_a, ctx) = { "sent" => !ctx.dry_run }
    end
    blocked = Class.new(CDFLHarness::Tooling::Tool) do
      tool_name "blocked"; description "d"
      def call(_a, _c) = raise(CDFLHarness::Errors::ToolDispatchError, "nope")
    end
    reg.register(ev.new); reg.register(send_email.new); reg.register(blocked.new)
    reg
  end

  let(:ctx) { CDFLHarness::Tooling::Context.new(scope: "enterprise", tenant_id: "t1", dry_run: true) }

  it "dispatches steps in order, producing transcript entries" do
    plan = CDFLHarness::Types::Plan.new(
      steps: [CDFLHarness::Types::PlanStep.new(tool_name: "retrieve_evidence", args: {}, rationale: "r")], rationale: "o"
    )
    entries = described_class.new.execute_steps(plan: plan, ctx: ctx, registry: registry, starting_step_index: 1)
    expect(entries.size).to eq(1)
    expect(entries.first.role).to eq("executor")
    expect(entries.first.tool_ok).to be(true)
  end

  it "attaches empowerment consent advice for an irreversible step" do
    plan = CDFLHarness::Types::Plan.new(
      steps: [CDFLHarness::Types::PlanStep.new(tool_name: "send_email", args: {}, rationale: "r")], rationale: "o"
    )
    entries = described_class.new.execute_steps(plan: plan, ctx: ctx, registry: registry, starting_step_index: 1)
    expect(entries.first.reasoning).to match(/phê duyệt|consent|empowerment/i)
  end

  it "hard-stops on a ToolDispatchError" do
    plan = CDFLHarness::Types::Plan.new(
      steps: [
        CDFLHarness::Types::PlanStep.new(tool_name: "blocked", args: {}, rationale: "r"),
        CDFLHarness::Types::PlanStep.new(tool_name: "retrieve_evidence", args: {}, rationale: "r")
      ], rationale: "o"
    )
    entries = described_class.new.execute_steps(plan: plan, ctx: ctx, registry: registry, starting_step_index: 1)
    expect(entries.size).to eq(1) # stopped after the blocked step
    expect(entries.first.reasoning).to start_with("[BLOCKED]")
  end
end
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bundle exec rspec spec/agent/executor_spec.rb`
Expected: FAIL.

- [ ] **Step 3: Write the implementation**

```ruby
# lib/cdfl_harness/agent/executor.rb
# frozen_string_literal: true

require_relative "../types"
require_relative "../errors"
require_relative "../reasoning/cdfl/empowerment"

module CDFLHarness
  module Agent
    # Dispatches plan steps through the tool registry. dry_run is the tool's
    # concern (it reads ctx.dry_run). Attaches empowerment consent advice for
    # irreversible steps. Hard-stops on a ToolDispatchError. Port of executor.py.
    class Executor
      def execute_steps(plan:, ctx:, registry:, starting_step_index: 1)
        entries = []
        plan.steps.each_with_index do |step, offset|
          entry = execute_one(step, ctx, registry, starting_step_index + offset)
          entries << entry
          break if entry.reasoning.start_with?("[BLOCKED]")
        end
        entries
      end

      private

      def execute_one(step, ctx, registry, step_index)
        tool = registry.fetch(step.tool_name)
        sec = tool && tool.respond_to?(:side_effect_class) ? tool.side_effect_class : "read_only"
        advice = Reasoning::CDFL::Empowerment.protection_advice(sec)

        begin
          ok, result = registry.dispatch(name: step.tool_name, args: step.args, ctx: ctx)
          base = "dispatched ok=#{ok} dry_run=#{ctx.dry_run} rationale=#{step.rationale[0, 120]}"
          reasoning = advice.needs_consent ? "#{base} | ⚠ #{advice.rationale}" : base
        rescue Errors::ToolDispatchError => e
          ok = false
          result = { "error" => e.message }
          reasoning = "[BLOCKED] #{e.message}"
        end

        Types::TranscriptEntry.new(
          step_index: step_index, role: "executor", tool_name: step.tool_name,
          tool_args: step.args, tool_result: result, tool_ok: ok, reasoning: reasoning
        )
      end
    end
  end
end
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bundle exec rspec spec/agent/executor_spec.rb`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/cdfl_harness/agent/executor.rb spec/agent/executor_spec.rb
git commit -m "feat: Agent Executor (dispatch, dry_run, empowerment advice, hard-stop)"
```

---

## Phase 13 — Critic

### Task 13.1: Critic (verdict + grounding gate override)

**Files:**
- Create: `lib/cdfl_harness/agent/critic.rb`
- Test: `spec/agent/critic_spec.rb`

Port of `agents/critic.py`: VERDICT_SCHEMA, grounding gate, deterministic critic for non-LLM workflows, grounding override.

- [ ] **Step 1: Write the failing test**

```ruby
# spec/agent/critic_spec.rb
# frozen_string_literal: true

RSpec.describe CDFLHarness::Agent::Critic do
  def evidence_entry(sim)
    CDFLHarness::Types::TranscriptEntry.new(
      step_index: 1, role: "executor", tool_name: "retrieve_evidence",
      tool_result: { "citations" => [{ "similarity" => sim }] }, tool_ok: true
    )
  end

  def workflow(llm_critic: true, requires_grounding: false)
    CDFLHarness::Agent::Workflow.new(
      workflow_id: "w", input_schema: { "type" => "object" }, allowed_tools: [],
      planner_prompt: ->(_i) { "p" }, critic_prompt: ->(_p, _t, _i) { "review" },
      llm_critic: llm_critic, requires_grounding: requires_grounding
    )
  end

  let(:plan) { CDFLHarness::Types::Plan.new(steps: [CDFLHarness::Types::PlanStep.new(tool_name: "x", args: {}, rationale: "r")], rationale: "o") }

  it "deterministic critic (llm_critic=false) accepts when coverage suffices" do
    gw = CDFLHarness::Gateway::Client.new(config: CDFLHarness::Config.new.tap { |c| c.adapter_override = CDFLHarness::Gateway::Adapters::Fake.new(completions: []) })
    strong = [evidence_entry(0.9), evidence_entry(0.85), evidence_entry(0.8)]
    verdict = described_class.new(gateway: gw).review_session(workflow: workflow(llm_critic: false), input: {}, plan: plan, transcripts: strong)
    expect(verdict.action).to eq("accept")
  end

  it "deterministic critic replans when coverage is too low" do
    gw = CDFLHarness::Gateway::Client.new(config: CDFLHarness::Config.new.tap { |c| c.adapter_override = CDFLHarness::Gateway::Adapters::Fake.new(completions: []) })
    weak = [evidence_entry(0.2)]
    verdict = described_class.new(gateway: gw).review_session(workflow: workflow(llm_critic: false), input: {}, plan: plan, transcripts: weak)
    expect(verdict.action).to eq("replan")
  end

  it "LLM critic parses a verdict" do
    gw = CDFLHarness::Gateway::Client.new(config: CDFLHarness::Config.new.tap { |c| c.adapter_override = CDFLHarness::Gateway::Adapters::Fake.new(completions: ['{"action":"accept","reason":"looks good","issues":[]}']) })
    verdict = described_class.new(gateway: gw).review_session(workflow: workflow, input: {}, plan: plan, transcripts: [evidence_entry(0.9)])
    expect(verdict.action).to eq("accept")
  end

  it "overrides an ungrounded LLM accept to replan when requires_grounding" do
    gw = CDFLHarness::Gateway::Client.new(config: CDFLHarness::Config.new.tap { |c| c.adapter_override = CDFLHarness::Gateway::Adapters::Fake.new(completions: ['{"action":"accept","reason":"ok","issues":[]}']) })
    verdict = described_class.new(gateway: gw).review_session(
      workflow: workflow(requires_grounding: true), input: {}, plan: plan, transcripts: [evidence_entry(0.1)]
    )
    expect(verdict.action).to eq("replan")
    expect(verdict.issues).to include(a_string_matching(/grounding/))
  end
end
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bundle exec rspec spec/agent/critic_spec.rb`
Expected: FAIL.

- [ ] **Step 3: Write the implementation**

```ruby
# lib/cdfl_harness/agent/critic.rb
# frozen_string_literal: true

require_relative "../types"
require_relative "../grounding/gate"

module CDFLHarness
  module Agent
    # Reviews the executor transcript → verdict (accept|replan|escalate). Runs
    # the |OR| grounding gate first; for non-LLM workflows the gate IS the
    # verdict; for LLM workflows with requires_grounding an ungrounded accept is
    # overridden to replan. Port of agents/critic.py.
    class Critic
      VERDICT_OUTPUT_SCHEMA = {
        "$schema" => "https://json-schema.org/draft/2020-12/schema",
        "type" => "object", "additionalProperties" => false,
        "required" => %w[action reason],
        "properties" => {
          "action" => { "type" => "string", "enum" => %w[accept replan escalate] },
          "reason" => { "type" => "string", "minLength" => 1, "maxLength" => 1500 },
          "issues" => { "type" => "array", "maxItems" => 10, "items" => { "type" => "string", "maxLength" => 200 } }
        }
      }.freeze

      def initialize(gateway:)
        @gateway = gateway
      end

      def review_session(workflow:, input:, plan:, transcripts:)
        grounding = Grounding::Gate.assess(transcripts)
        note = "\n\n[Cổng |OR| — độ phủ bằng chứng]: #{(grounding[:coverage] * 100).round}% " \
               "(#{grounding[:band]}); #{grounding[:evidence_count]} trích dẫn, #{grounding[:memory_hits]} ký ức. #{grounding[:note]}"

        unless workflow.llm_critic
          action = grounding[:can_generalize] ? "accept" : "replan"
          reason = "Cổng |OR| (tất định): độ phủ #{(grounding[:coverage] * 100).round}% (#{grounding[:band]}). #{grounding[:note]}"
          return Types::CriticVerdict.new(action: action, reason: reason[0, 1500],
                                          issues: action == "accept" ? [] : ["|OR| grounding insufficient"])
        end

        prompt = workflow.critic_prompt.call(plan, transcripts, input) + note
        parsed = @gateway.complete_structured(
          prompt: prompt, task: "agent.critic.#{workflow.workflow_id}",
          schema: VERDICT_OUTPUT_SCHEMA, consent_external: false, max_tokens: 1500
        )
        verdict = Types::CriticVerdict.new(action: parsed["action"], reason: parsed["reason"], issues: parsed["issues"] || [])

        if workflow.requires_grounding && !grounding[:can_generalize] && verdict.action == "accept"
          verdict = Types::CriticVerdict.new(
            action: "replan",
            reason: ("Cổng |OR|: chưa đủ cơ sở (#{(grounding[:coverage] * 100).round}%) để chấp nhận — " \
                     "cần truy hồi thêm bằng chứng trước khi kết luận. #{verdict.reason}")[0, 1500],
            issues: (verdict.issues + ["|OR| grounding insufficient"]).first(10)
          )
        end
        verdict
      end
    end
  end
end
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bundle exec rspec spec/agent/critic_spec.rb`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/cdfl_harness/agent/critic.rb spec/agent/critic_spec.rb
git commit -m "feat: Agent Critic (verdict schema, |OR| gate, deterministic + grounding override)"
```

---

## Phase 14 — Session (the orchestrator loop)

### Task 14.1: Session

**Files:**
- Create: `lib/cdfl_harness/agent/session.rb`
- Test: `spec/agent/session_spec.rb`

Port of `agents/orchestrator.py`: validate input → loop PLAN→EXECUTE→CRITIC, MAX_REPLAN, token budget, persistence, memory consolidation, four-fold DE. Never raises out of `run`.

- [ ] **Step 1: Write the failing test**

```ruby
# spec/agent/session_spec.rb
# frozen_string_literal: true

RSpec.describe CDFLHarness::Agent::Session do
  def registry
    reg = CDFLHarness::Tooling::Registry.new
    ev = Class.new(CDFLHarness::Tooling::Tool) do
      tool_name "retrieve_evidence"; description "d"
      def call(_a, _c) = { "citations" => [{ "similarity" => 0.9 }, { "similarity" => 0.85 }] }
    end
    reg.register(ev.new)
    reg
  end

  def workflow
    CDFLHarness::Agent::Workflow.new(
      workflow_id: "insight-to-action",
      input_schema: { "type" => "object", "required" => ["question"],
                      "properties" => { "question" => { "type" => "string" } } },
      allowed_tools: %w[retrieve_evidence],
      planner_prompt: ->(i) { "Plan for #{i['question']}" },
      critic_prompt: ->(_p, _t, _i) { "review" },
      static_plan: ->(_i) { [CDFLHarness::Types::PlanStep.new(tool_name: "retrieve_evidence", args: { "q" => "x" }, rationale: "r")] },
      llm_critic: false, requires_grounding: true
    )
  end

  def session(completions: [])
    cfg = CDFLHarness::Config.new
    cfg.adapter_override = CDFLHarness::Gateway::Adapters::Fake.new(completions: completions)
    wfs = CDFLHarness::Agent::Workflows.new.tap { |w| w.register(workflow) }
    described_class.new(config: cfg, workflows: wfs, registry: registry)
  end

  let(:ctx) { CDFLHarness::Tooling::Context.new(scope: "enterprise", tenant_id: "11111111-1111-1111-1111-111111111111") }

  it "runs a full session to completed with a grounded static plan + deterministic critic" do
    res = session.run(workflow_id: "insight-to-action", input: { "question" => "doanh thu?" }, context: ctx, dry_run: true)
    expect(res.status).to eq(:completed)
    expect(res.transcripts.map(&:role)).to include("planner", "executor", "critic")
    expect(res.four_fold_de).to be_a(CDFLHarness::Reasoning::CDFL::FourFoldDE)
  end

  it "returns :failed (never raises) for invalid input" do
    res = session.run(workflow_id: "insight-to-action", input: {}, context: ctx, dry_run: true)
    expect(res.status).to eq(:failed)
    expect(res.error_message).to match(/invalid|required/i)
  end

  it "escalates after MAX_REPLAN when grounding never suffices" do
    reg = CDFLHarness::Tooling::Registry.new
    weak = Class.new(CDFLHarness::Tooling::Tool) do
      tool_name "retrieve_evidence"; description "d"
      def call(_a, _c) = { "citations" => [{ "similarity" => 0.1 }] }
    end
    reg.register(weak.new)
    cfg = CDFLHarness::Config.new
    cfg.adapter_override = CDFLHarness::Gateway::Adapters::Fake.new(completions: [])
    cfg.max_replan = 1
    wfs = CDFLHarness::Agent::Workflows.new.tap { |w| w.register(workflow) }
    res = described_class.new(config: cfg, workflows: wfs, registry: reg)
            .run(workflow_id: "insight-to-action", input: { "question" => "q" }, context: ctx, dry_run: true)
    expect(res.status).to eq(:escalated)
  end

  it "consolidates a successful non-dry session into the memory palace" do
    mem = CDFLHarness::Reasoning::Memory::Service.new
    cfg = CDFLHarness::Config.new
    cfg.adapter_override = CDFLHarness::Gateway::Adapters::Fake.new(completions: [])
    cfg.memory_service = mem
    wfs = CDFLHarness::Agent::Workflows.new.tap { |w| w.register(workflow) }
    described_class.new(config: cfg, workflows: wfs, registry: registry)
      .run(workflow_id: "insight-to-action", input: { "question" => "doanh thu quý" }, context: ctx, dry_run: false)
    expect(mem.retrieve(ctx.tenant_id, "doanh thu quý", top_k: 5)).not_to be_empty
  end
end
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bundle exec rspec spec/agent/session_spec.rb`
Expected: FAIL.

- [ ] **Step 3: Write the implementation**

```ruby
# lib/cdfl_harness/agent/session.rb
# frozen_string_literal: true

require "securerandom"
require_relative "../types"
require_relative "../errors"
require_relative "../schema"
require_relative "../store/in_memory"
require_relative "../reasoning/cdfl/four_fold_de"
require_relative "../reasoning/memory/service"
require_relative "../grounding/gate"
require_relative "workflows"
require_relative "planner"
require_relative "executor"
require_relative "critic"

module CDFLHarness
  module Agent
    # The orchestrator: validate → PLAN→EXECUTE→CRITIC loop, bounded re-plan +
    # token budget, persistence, memory consolidation, four-fold DE. Never
    # raises out of #run — failures land in status: :failed. Port of
    # agents/orchestrator.py.
    class Session
      def initialize(config: CDFLHarness.config, workflows:, registry:,
                     gateway: nil, store: nil, memory_service: nil)
        @config = config
        @workflows = workflows
        @registry = registry
        @gateway = gateway || Gateway::Client.new(config: config)
        @store = store || config.store || Store::InMemory.new
        @memory = memory_service || config.memory_service
        @planner = Planner.new(gateway: @gateway)
        @executor = Executor.new
        @critic = Critic.new(gateway: @gateway)
      end

      def run(workflow_id:, input:, context:, dry_run: true)
        workflow = @workflows.get(workflow_id) # raises WorkflowInputError → caught below? No: validate path
        validate_input!(input, workflow)

        session_id = SecureRandom.uuid
        @store.create_session(session_id: session_id, tenant_id: context.tenant_id,
                              workflow_id: workflow_id, input: input, dry_run: dry_run)

        transcripts = []
        tokens = 0
        replan = 0
        last_plan = nil
        last_verdict = nil
        error_message = nil
        status = :failed
        ctx = with_dry_run(context, dry_run)

        begin
          loop do
            @store.set_status(session_id: session_id, status: :planning)
            plan, ptoks = @planner.plan_workflow(workflow: workflow, input: input, registry: @registry, scope: ctx.scope)
            tokens += ptoks
            last_plan = plan
            transcripts << add(session_id, Types::TranscriptEntry.new(step_index: transcripts.size, role: "planner", reasoning: plan.rationale.to_s.empty? ? "(no rationale)" : plan.rationale))
            @store.persist_plan(session_id: session_id, plan: plan)

            if tokens > @config.max_tokens_per_session
              error_message = "token_budget_exceeded: #{tokens} > #{@config.max_tokens_per_session}"
              break
            end

            @store.set_status(session_id: session_id, status: :executing)
            start_idx = transcripts.size
            @executor.execute_steps(plan: plan, ctx: ctx, registry: @registry, starting_step_index: start_idx).each do |e|
              transcripts << add(session_id, e)
            end

            @store.set_status(session_id: session_id, status: :critiquing)
            verdict = @critic.review_session(workflow: workflow, input: input, plan: plan, transcripts: transcripts)
            last_verdict = verdict
            transcripts << add(session_id, Types::TranscriptEntry.new(step_index: transcripts.size, role: "critic", reasoning: verdict.reason))
            @store.persist_verdict(session_id: session_id, verdict: verdict)

            case verdict.action
            when "accept"
              status = :completed
              break
            when "escalate"
              status = :escalated
              break
            else # replan
              replan += 1
              @store.bump_replan(session_id: session_id, replan_count: replan)
              if replan > @config.max_replan
                status = :escalated
                error_message = "max_replan_reached: #{@config.max_replan}"
                break
              end
            end
          end
        rescue Errors::Error => e
          error_message = "agent_error: #{e.message}"
          status = :failed
        rescue StandardError => e
          error_message = "unhandled: #{e.message}"
          status = :failed
        end

        @store.finalize(session_id: session_id, status: status, tokens_used: tokens, error_message: error_message)

        consolidate(workflow_id, last_plan, last_verdict, transcripts, context, input) if status == :completed && !dry_run && @memory

        grounding = Grounding::Gate.assess(transcripts)
        four_fold = Reasoning::CDFL::FourFoldDE.assemble(
          data_coverage: 1.0, knowledge_freshness: 1.0,
          knowledge_coverage: grounding[:coverage], grounding_score: grounding[:coverage]
        )

        Types::SessionResult.new(
          session_id: session_id, workflow_id: workflow_id, status: status, dry_run: dry_run,
          plan: last_plan, transcripts: transcripts, critic_verdict: last_verdict,
          tokens_used: tokens, replan_count: replan, error_message: error_message,
          grounding: grounding, four_fold_de: four_fold
        )
      rescue Errors::WorkflowInputError => e
        # unknown workflow / invalid input before the session row exists
        Types::SessionResult.new(session_id: nil, workflow_id: workflow_id, status: :failed,
                                 dry_run: dry_run, error_message: e.message)
      end

      private

      def validate_input!(input, workflow)
        err = Schema.first_error(input, workflow.input_schema)
        raise Errors::WorkflowInputError, "workflow '#{workflow.workflow_id}' input invalid: #{err}" if err
      end

      def add(session_id, entry)
        @store.append_transcript(session_id: session_id, entry: entry)
        entry
      end

      def with_dry_run(context, dry_run)
        Tooling::Context.new(scope: context.scope, tenant_id: context.tenant_id,
                             user_id: context.user_id, role: context.role, dry_run: dry_run)
      end

      def consolidate(workflow_id, plan, verdict, transcripts, context, input)
        question = (input["question"] || "").to_s.strip
        intent = question.empty? ? (plan&.rationale || "").to_s.strip : question
        intent = "(không rõ)" if intent.empty?
        evidence = evidence_summary(transcripts)
        actions = transcripts.select { |t| t.role == "executor" && t.tool_name }.map(&:tool_name)
        outcome = verdict ? verdict.action : "completed"
        content = "[#{workflow_id}] Hỏi: #{intent[0, 200]} → #{outcome}. " \
                  "Cơ sở: #{evidence.empty? ? '(không có bằng chứng)' : evidence} | " \
                  "Hành động: #{actions.first(6).join(', ')}."
        @memory.write(context.tenant_id, :OPERATIONAL, content,
                      metadata: { "workflow_id" => workflow_id, "outcome" => outcome,
                                  "question" => question.empty? ? nil : question })
      rescue StandardError
        nil # memory must never fail a session
      end

      def evidence_summary(transcripts)
        snippets = []
        transcripts.each do |t|
          next unless t.role == "executor" && t.tool_name == "retrieve_evidence"

          res = t.tool_result.is_a?(Hash) ? t.tool_result : {}
          (res["citations"] || []).each do |c|
            snip = c.is_a?(Hash) ? c["snippet"].to_s.strip : ""
            snippets << snip[0, 160] unless snip.empty?
            break if snippets.size >= 3
          end
          break if snippets.size >= 3
        end
        snippets.join(" · ")
      end
    end
  end
end
```

- [ ] **Step 4: Wire the require into `lib/cdfl_harness.rb`**

Add (re-enable) the agent requires at the end of the require block in `lib/cdfl_harness.rb`:
```ruby
require_relative "cdfl_harness/tooling/context"
require_relative "cdfl_harness/agent/session"
```

- [ ] **Step 5: Run test to verify it passes**

Run: `bundle exec rspec spec/agent/session_spec.rb`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add lib/cdfl_harness/agent/session.rb lib/cdfl_harness.rb spec/agent/session_spec.rb
git commit -m "feat: Agent Session loop (PLAN->EXECUTE->CRITIC, bounds, persistence, memory consolidation, four-fold DE)"
```

---

## Phase 15 — Real provider adapters

### Task 15.1: Ollama adapter

**Files:**
- Create: `lib/cdfl_harness/gateway/adapters/ollama.rb`
- Test: `spec/gateway/adapters/ollama_spec.rb`

Port of `providers.py` Ollama path (`/api/generate`, `/api/chat`).

- [ ] **Step 1: Write the failing test (WebMock)**

```ruby
# spec/gateway/adapters/ollama_spec.rb
# frozen_string_literal: true

require "webmock/rspec"

RSpec.describe CDFLHarness::Gateway::Adapters::Ollama do
  it "invoke calls /api/generate and returns response text" do
    stub_request(:post, "http://localhost:11434/api/generate")
      .to_return(status: 200, body: { "response" => "hello" }.to_json, headers: { "Content-Type" => "application/json" })
    a = described_class.new(host: "http://localhost:11434")
    expect(a.invoke(model: "qwen2.5:14b", prompt: "hi", max_tokens: 10)).to eq("hello")
  end

  it "is internal (never external)" do
    expect(described_class.new.external?).to be(false)
  end

  it "raises AdapterError on a non-200" do
    stub_request(:post, "http://localhost:11434/api/generate").to_return(status: 500, body: "boom")
    a = described_class.new(host: "http://localhost:11434")
    expect { a.invoke(model: "m", prompt: "p", max_tokens: 1) }.to raise_error(CDFLHarness::Errors::AdapterError)
  end
end
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bundle exec rspec spec/gateway/adapters/ollama_spec.rb`
Expected: FAIL.

- [ ] **Step 3: Write the implementation**

```ruby
# lib/cdfl_harness/gateway/adapters/ollama.rb
# frozen_string_literal: true

require "net/http"
require "json"
require_relative "base"
require_relative "../../errors"

module CDFLHarness
  module Gateway
    module Adapters
      # Local Ollama adapter (internal). Port of providers.py Ollama path.
      class Ollama < Base
        def initialize(host: ENV.fetch("OLLAMA_HOST", "http://localhost:11434"), timeout: 120)
          @host = host
          @timeout = timeout
        end

        def invoke(model:, prompt:, max_tokens:)
          body = { model: model, prompt: prompt, stream: false,
                   options: { num_predict: max_tokens, temperature: 0.1 } }
          post("/api/generate", body).fetch("response", "")
        end

        def invoke_chat(model:, messages:, tools: nil, tool_choice: nil, max_tokens: 1500)
          body = { model: model, messages: messages, stream: false,
                   options: { num_predict: max_tokens, temperature: 0.1 } }
          body[:tools] = tools if tools && !tools.empty?
          data = post("/api/chat", body)
          msg = data["message"] || {}
          raw = msg["tool_calls"] || []
          tool_calls = raw.empty? ? nil : raw.each_with_index.map do |c, i|
            fn = c["function"] || {}
            { "id" => c["id"] || "ollama_#{i}", "name" => fn["name"].to_s, "arguments" => fn["arguments"] || {} }
          end
          { content: msg["content"].to_s, model_used: model, tool_calls: tool_calls,
            finish_reason: tool_calls ? "tool_calls" : "stop" }
        end

        def external? = false

        private

        def post(path, body)
          uri = URI("#{@host}#{path}")
          http = Net::HTTP.new(uri.host, uri.port)
          http.use_ssl = uri.scheme == "https"
          http.read_timeout = @timeout
          req = Net::HTTP::Post.new(uri.path, "Content-Type" => "application/json")
          req.body = JSON.generate(body)
          resp = http.request(req)
          raise Errors::AdapterError, "ollama #{path} → #{resp.code}: #{resp.body[0, 200]}" unless resp.code.to_i == 200

          JSON.parse(resp.body)
        rescue JSON::ParserError => e
          raise Errors::AdapterError, "ollama bad JSON: #{e.message}"
        rescue SocketError, Timeout::Error => e
          raise Errors::AdapterError, "ollama unreachable: #{e.message}"
        end
      end
    end
  end
end
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bundle exec rspec spec/gateway/adapters/ollama_spec.rb`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/cdfl_harness/gateway/adapters/ollama.rb spec/gateway/adapters/ollama_spec.rb
git commit -m "feat: Ollama adapter (/api/generate, /api/chat, internal)"
```

### Task 15.2: Anthropic adapter

**Files:**
- Create: `lib/cdfl_harness/gateway/adapters/anthropic.rb`
- Test: `spec/gateway/adapters/anthropic_spec.rb`

Port of `providers.py` Anthropic path (Messages API; system as top-level; tool shape rename).

- [ ] **Step 1: Write the failing test (WebMock)**

```ruby
# spec/gateway/adapters/anthropic_spec.rb
# frozen_string_literal: true

require "webmock/rspec"

RSpec.describe CDFLHarness::Gateway::Adapters::Anthropic do
  it "invoke posts to the Messages API and returns text" do
    stub_request(:post, "https://api.anthropic.com/v1/messages")
      .with(headers: { "x-api-key" => "sk-test", "anthropic-version" => "2023-06-01" })
      .to_return(status: 200, body: { "content" => [{ "type" => "text", "text" => "hi there" }] }.to_json)
    a = described_class.new(api_key: "sk-test")
    expect(a.invoke(model: "claude-opus-4-8", prompt: "x", max_tokens: 50)).to eq("hi there")
  end

  it "is external" do
    expect(described_class.new(api_key: "k").external?).to be(true)
  end

  it "raises ConfigError without an api key" do
    expect { described_class.new(api_key: nil) }.to raise_error(CDFLHarness::Errors::ConfigError)
  end
end
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bundle exec rspec spec/gateway/adapters/anthropic_spec.rb`
Expected: FAIL.

- [ ] **Step 3: Write the implementation**

```ruby
# lib/cdfl_harness/gateway/adapters/anthropic.rb
# frozen_string_literal: true

require "net/http"
require "json"
require_relative "base"
require_relative "../../errors"

module CDFLHarness
  module Gateway
    module Adapters
      # Anthropic Messages API adapter (external). Caller redacts PII first.
      # Port of providers.py Anthropic path. Defaults to a current Claude model.
      class Anthropic < Base
        ENDPOINT = "https://api.anthropic.com/v1/messages"
        API_VERSION = "2023-06-01"

        def initialize(api_key: ENV.fetch("ANTHROPIC_API_KEY", nil), timeout: 60)
          raise Errors::ConfigError, "Anthropic adapter requires an api_key" if api_key.nil? || api_key.empty?

          @api_key = api_key
          @timeout = timeout
        end

        def invoke(model:, prompt:, max_tokens:)
          data = post(model: model, max_tokens: max_tokens, messages: [{ role: "user", content: prompt }])
          (data["content"] || []).select { |b| b["type"] == "text" }.map { |b| b["text"] }.join
        end

        def invoke_chat(model:, messages:, tools: nil, tool_choice: nil, max_tokens: 1500)
          system = messages.select { |m| m["role"] == "system" }.map { |m| m["content"] }.compact.join("\n\n")
          chat = messages.select { |m| %w[user assistant].include?(m["role"]) }
                         .map { |m| { role: m["role"], content: m["content"] || "" } }
          body = { model: model, max_tokens: max_tokens, messages: chat }
          body[:system] = system unless system.empty?
          if tools && !tools.empty?
            body[:tools] = tools.map do |t|
              fn = t[:function] || t["function"]
              { name: fn["name"], description: fn["description"] || "", input_schema: fn["parameters"] || {} }
            end
          end
          data = post(**body)
          blocks = data["content"] || []
          text = blocks.select { |b| b["type"] == "text" }.map { |b| b["text"] }.join
          tool_blocks = blocks.select { |b| b["type"] == "tool_use" }
          tool_calls = tool_blocks.empty? ? nil : tool_blocks.map { |b| { "id" => b["id"], "name" => b["name"], "arguments" => b["input"] || {} } }
          fr = data["stop_reason"] || (tool_calls ? "tool_calls" : "stop")
          fr = "tool_calls" if fr == "tool_use"
          { content: text, model_used: model, tool_calls: tool_calls, finish_reason: fr }
        end

        def external? = true

        private

        def post(**body)
          uri = URI(ENDPOINT)
          http = Net::HTTP.new(uri.host, uri.port)
          http.use_ssl = true
          http.read_timeout = @timeout
          req = Net::HTTP::Post.new(uri.path,
                                    "x-api-key" => @api_key, "anthropic-version" => API_VERSION,
                                    "content-type" => "application/json")
          req.body = JSON.generate(body)
          resp = http.request(req)
          raise Errors::AdapterError, "anthropic → #{resp.code}: #{resp.body[0, 200]}" unless resp.code.to_i == 200

          JSON.parse(resp.body)
        rescue JSON::ParserError => e
          raise Errors::AdapterError, "anthropic bad JSON: #{e.message}"
        rescue SocketError, Timeout::Error => e
          raise Errors::AdapterError, "anthropic unreachable: #{e.message}"
        end
      end
    end
  end
end
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bundle exec rspec spec/gateway/adapters/anthropic_spec.rb`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/cdfl_harness/gateway/adapters/anthropic.rb spec/gateway/adapters/anthropic_spec.rb
git commit -m "feat: Anthropic adapter (Messages API, tool-shape rename, external)"
```

### Task 15.3: OpenAI adapter + wire build_adapter

**Files:**
- Create: `lib/cdfl_harness/gateway/adapters/openai.rb`
- Modify: `lib/cdfl_harness/gateway/client.rb` (replace `build_adapter`)
- Test: `spec/gateway/adapters/openai_spec.rb`
- Test: `spec/gateway/client_build_adapter_spec.rb`

Port of `providers.py` OpenAI path (chat/completions; arguments JSON-decode).

- [ ] **Step 1: Write the failing tests**

```ruby
# spec/gateway/adapters/openai_spec.rb
# frozen_string_literal: true

require "webmock/rspec"

RSpec.describe CDFLHarness::Gateway::Adapters::OpenAI do
  it "invoke posts to chat/completions and returns content" do
    stub_request(:post, "https://api.openai.com/v1/chat/completions")
      .with(headers: { "Authorization" => "Bearer sk-test" })
      .to_return(status: 200, body: { "choices" => [{ "message" => { "content" => "answer" }, "finish_reason" => "stop" }] }.to_json)
    a = described_class.new(api_key: "sk-test")
    expect(a.invoke(model: "gpt-4o", prompt: "x", max_tokens: 10)).to eq("answer")
  end

  it "is external and requires a key" do
    expect(described_class.new(api_key: "k").external?).to be(true)
    expect { described_class.new(api_key: nil) }.to raise_error(CDFLHarness::Errors::ConfigError)
  end
end
```

```ruby
# spec/gateway/client_build_adapter_spec.rb
# frozen_string_literal: true

RSpec.describe "Gateway::Client#build_adapter" do
  it "builds the configured provider adapter" do
    cfg = CDFLHarness::Config.new.tap { |c| c.provider = :ollama; c.ollama_host = "http://h:11434" }
    client = CDFLHarness::Gateway::Client.new(config: cfg)
    expect(client.send(:adapter)).to be_a(CDFLHarness::Gateway::Adapters::Ollama)
  end

  it "builds anthropic with the configured key" do
    cfg = CDFLHarness::Config.new.tap { |c| c.provider = :anthropic; c.api_keys = { anthropic: "sk-x" } }
    client = CDFLHarness::Gateway::Client.new(config: cfg)
    expect(client.send(:adapter)).to be_a(CDFLHarness::Gateway::Adapters::Anthropic)
  end
end
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `bundle exec rspec spec/gateway/adapters/openai_spec.rb spec/gateway/client_build_adapter_spec.rb`
Expected: FAIL.

- [ ] **Step 3: Write the OpenAI adapter**

```ruby
# lib/cdfl_harness/gateway/adapters/openai.rb
# frozen_string_literal: true

require "net/http"
require "json"
require_relative "base"
require_relative "../../errors"

module CDFLHarness
  module Gateway
    module Adapters
      # OpenAI Chat Completions adapter (external). Caller redacts PII first.
      # Port of providers.py OpenAI path.
      class OpenAI < Base
        ENDPOINT = "https://api.openai.com/v1/chat/completions"

        def initialize(api_key: ENV.fetch("OPENAI_API_KEY", nil), timeout: 60)
          raise Errors::ConfigError, "OpenAI adapter requires an api_key" if api_key.nil? || api_key.empty?

          @api_key = api_key
          @timeout = timeout
        end

        def invoke(model:, prompt:, max_tokens:)
          data = post(model: model, messages: [{ role: "user", content: prompt }],
                      max_tokens: max_tokens, temperature: 0.1)
          dig_content(data)
        end

        def invoke_chat(model:, messages:, tools: nil, tool_choice: nil, max_tokens: 1500)
          body = { model: model, messages: messages, max_tokens: max_tokens, temperature: 0.1 }
          if tools && !tools.empty?
            body[:tools] = tools
            body[:tool_choice] = tool_choice || "auto"
          end
          data = post(**body)
          choice = (data["choices"] || [{}]).first
          msg = choice["message"] || {}
          raw = msg["tool_calls"] || []
          tool_calls = raw.empty? ? nil : raw.map do |c|
            fn = c["function"] || {}
            args = fn["arguments"]
            args = (JSON.parse(args) rescue {}) if args.is_a?(String)
            { "id" => c["id"], "name" => fn["name"].to_s, "arguments" => args || {} }
          end
          { content: msg["content"].to_s, model_used: model, tool_calls: tool_calls,
            finish_reason: choice["finish_reason"] || (tool_calls ? "tool_calls" : "stop") }
        end

        def external? = true

        private

        def dig_content(data)
          ((data["choices"] || [{}]).first["message"] || {})["content"].to_s
        end

        def post(**body)
          uri = URI(ENDPOINT)
          http = Net::HTTP.new(uri.host, uri.port)
          http.use_ssl = true
          http.read_timeout = @timeout
          req = Net::HTTP::Post.new(uri.path, "Authorization" => "Bearer #{@api_key}",
                                              "Content-Type" => "application/json")
          req.body = JSON.generate(body)
          resp = http.request(req)
          raise Errors::AdapterError, "openai → #{resp.code}: #{resp.body[0, 200]}" unless resp.code.to_i == 200

          JSON.parse(resp.body)
        rescue JSON::ParserError => e
          raise Errors::AdapterError, "openai bad JSON: #{e.message}"
        rescue SocketError, Timeout::Error => e
          raise Errors::AdapterError, "openai unreachable: #{e.message}"
        end
      end
    end
  end
end
```

- [ ] **Step 4: Replace `build_adapter` in `lib/cdfl_harness/gateway/client.rb`**

Add the requires near the top of `client.rb`:
```ruby
require_relative "adapters/ollama"
require_relative "adapters/anthropic"
require_relative "adapters/openai"
```
Replace the `build_adapter` method body with:
```ruby
      def build_adapter
        case @config.provider
        when :fake then Adapters::Fake.new
        when :ollama then Adapters::Ollama.new(host: @config.ollama_host)
        when :anthropic then Adapters::Anthropic.new(api_key: @config.api_keys[:anthropic])
        when :openai then Adapters::OpenAI.new(api_key: @config.api_keys[:openai])
        else
          raise Errors::ConfigError, "unknown provider #{@config.provider.inspect}"
        end
      end
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `bundle exec rspec spec/gateway/adapters/openai_spec.rb spec/gateway/client_build_adapter_spec.rb`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add lib/cdfl_harness/gateway/adapters/openai.rb lib/cdfl_harness/gateway/client.rb spec/gateway/adapters/openai_spec.rb spec/gateway/client_build_adapter_spec.rb
git commit -m "feat: OpenAI adapter + wire build_adapter for all providers"
```

---

## Phase 16 — Runnable demo

### Task 16.1: `examples/insight_to_action.rb`

**Files:**
- Create: `examples/insight_to_action.rb`
- Test: `spec/examples/insight_to_action_spec.rb`

- [ ] **Step 1: Write the failing test (runs the example as a library)**

```ruby
# spec/examples/insight_to_action_spec.rb
# frozen_string_literal: true

RSpec.describe "examples/insight_to_action" do
  it "runs end-to-end on the Fake adapter and reports a completed grounded session" do
    load File.expand_path("../../examples/insight_to_action.rb", __dir__)
    result = InsightToActionDemo.run
    expect(result.status).to eq(:completed)
    expect(result.four_fold_de.manifest_or).to be_between(0.0, 1.0)
  end
end
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bundle exec rspec spec/examples/insight_to_action_spec.rb`
Expected: FAIL (no such file).

- [ ] **Step 3: Write the example**

```ruby
# examples/insight_to_action.rb
# frozen_string_literal: true

# Runnable demo: a grounded "insight → action" workflow on the offline Fake
# adapter. Run directly:  ruby -Ilib examples/insight_to_action.rb
require "cdfl_harness"

module InsightToActionDemo
  module_function

  def build_registry
    reg = CDFLHarness::Tooling::Registry.new

    retrieve = Class.new(CDFLHarness::Tooling::Tool) do
      tool_name "retrieve_evidence"
      description "Truy hồi bằng chứng cho câu hỏi"
      parameters({ "type" => "object", "properties" => { "q" => { "type" => "string" } } })
      def call(args, _ctx)
        { "citations" => [
          { "similarity" => 0.91, "snippet" => "Doanh thu quý 1 tăng 18% so với cùng kỳ." },
          { "similarity" => 0.84, "snippet" => "Nhóm khách VIP đóng góp 62% doanh thu." }
        ], "q" => args["q"] }
      end
    end

    draft = Class.new(CDFLHarness::Tooling::Tool) do
      tool_name "draft_action"
      description "Soạn đề xuất hành động (khả hồi — chỉ là bản nháp)"
      parameters({ "type" => "object", "properties" => { "note" => { "type" => "string" } } })
      def side_effect_class = "write_idempotent"
      def call(args, ctx)
        { "draft" => "Đề xuất: chăm sóc nhóm VIP. (dry_run=#{ctx.dry_run})", "note" => args["note"] }
      end
    end

    reg.register(retrieve.new)
    reg.register(draft.new)
  end

  def workflow
    CDFLHarness::Agent::Workflow.new(
      workflow_id: "insight-to-action",
      input_schema: { "type" => "object", "required" => ["question"],
                      "properties" => { "question" => { "type" => "string" } } },
      allowed_tools: %w[retrieve_evidence draft_action],
      planner_prompt: ->(input) { "Lập kế hoạch trả lời: #{input['question']}" },
      critic_prompt: ->(_plan, _ts, input) { "Đánh giá câu trả lời cho: #{input['question']}" },
      static_plan: lambda do |_input|
        [
          CDFLHarness::Types::PlanStep.new(tool_name: "retrieve_evidence", args: { "q" => "doanh thu VIP" }, rationale: "thu thập bằng chứng"),
          CDFLHarness::Types::PlanStep.new(tool_name: "draft_action", args: { "note" => "VIP" }, rationale: "đề xuất khả hồi")
        ]
      end,
      llm_critic: false,        # deterministic |OR| gate IS the verdict
      requires_grounding: true  # enforce học-1-hiểu-10
    )
  end

  def run
    config = CDFLHarness::Config.new
    config.provider = :fake
    config.adapter_override = CDFLHarness::Gateway::Adapters::Fake.new(completions: [])
    config.memory_service = CDFLHarness::Reasoning::Memory::Service.new

    workflows = CDFLHarness::Agent::Workflows.new.tap { |w| w.register(workflow) }
    session = CDFLHarness::Agent::Session.new(config: config, workflows: workflows, registry: build_registry)
    ctx = CDFLHarness::Tooling::Context.new(scope: "enterprise", tenant_id: "11111111-1111-1111-1111-111111111111")

    session.run(workflow_id: "insight-to-action",
                input: { "question" => "Vì sao doanh thu quý 1 tăng?" }, context: ctx, dry_run: true)
  end

  def main
    result = run
    puts "=== CDFL Harness demo: insight → action ==="
    puts "status: #{result.status}"
    puts "\n-- transcript --"
    result.transcripts.each do |t|
      line = "[#{t.step_index}] #{t.role}"
      line += " · #{t.tool_name} (ok=#{t.tool_ok})" if t.tool_name
      puts line
      puts "    #{t.reasoning}" unless t.reasoning.to_s.empty?
    end
    g = result.grounding
    puts "\n-- |OR| coverage gate (học 1 hiểu 10) --"
    puts "coverage=#{(g[:coverage] * 100).round}% band=#{g[:band]} can_generalize=#{g[:can_generalize]}"
    de = result.four_fold_de
    puts "\n-- four-fold DE (vùng tối) --"
    puts "x=#{de.x.round(2)} t=#{de.t.round(2)} if=#{de.if_.round(2)} mf=#{de.mf.round(2)} | manifest_or=#{de.manifest_or.round(2)}"
  end
end

InsightToActionDemo.main if $PROGRAM_NAME == __FILE__
```

- [ ] **Step 4: Run test + the script**

Run: `bundle exec rspec spec/examples/insight_to_action_spec.rb`
Expected: PASS.
Run: `ruby -Ilib examples/insight_to_action.rb`
Expected: prints the transcript, the coverage band, and the four-fold DE line.

- [ ] **Step 5: Commit**

```bash
git add examples/insight_to_action.rb spec/examples/insight_to_action_spec.rb
git commit -m "feat: runnable insight->action demo (offline Fake adapter, grounded + DE dashboard)"
```

---

## Phase 17 — Architecture documentation

> These are documentation tasks. Each step writes a real Markdown file with the
> listed sections + the concrete formulas/invariants noted. No "TODO" sections.

### Task 17.1: README + ARCHITECTURE

**Files:**
- Create: `README.md`
- Create: `docs/ARCHITECTURE.md`
- Create: `LICENSE` (MIT)

- [ ] **Step 1: Write `README.md`** with these sections, each filled in:
  - **What it is** — a pluggable Ruby LLM + agent harness porting Kaori/NNL-NTHT semantics (CDFL, học 1 hiểu 10, memory palace).
  - **Install** — `gem "cdfl_harness", path: "D:/CDFL harness"` (quote the space); `bundle install`.
  - **Quickstart** — paste a ~25-line condensed version of `examples/insight_to_action.rb` (build registry → workflow → `Session#run` → read `result.status` / `result.grounding` / `result.four_fold_de`).
  - **Providers** — `config.provider = :anthropic | :openai | :ollama | :fake`; keys via `config.api_keys`; external calls gated by `consent_external` + `external_enabled`.
  - **Docs index** — links to each `docs/*.md`.
  - **Run tests** — `bundle exec rspec`. **Run demo** — `ruby -Ilib examples/insight_to_action.rb`.

- [ ] **Step 2: Write `docs/ARCHITECTURE.md`** with:
  - The module tree (copy from the design spec §3).
  - A data-flow section for the gateway (`complete_structured`: resolve → PII → breaker → invoke → validate/repair → audit) and the agent loop (validate → PLAN → EXECUTE → CRITIC → branch → finalize → consolidate → DE).
  - A table mapping each Ruby module to the Kaori Python source it ports.
  - The "design for isolation" notes (Gateway standalone; Reasoning pure; Session owns Store).

- [ ] **Step 3: Write `LICENSE`** (standard MIT text, author "Nguyen Truong An", year 2026).

- [ ] **Step 4: Commit**

```bash
git add README.md docs/ARCHITECTURE.md LICENSE
git commit -m "docs: README + ARCHITECTURE + LICENSE"
```

### Task 17.2: GATEWAY + AGENT_LOOP + TOOLING docs

**Files:**
- Create: `docs/GATEWAY.md`
- Create: `docs/AGENT_LOOP.md`
- Create: `docs/TOOLING.md`

- [ ] **Step 1: Write `docs/GATEWAY.md`**: adapters (Base contract, Fake/Ollama/Anthropic/OpenAI), the unified chat tool-call shape `{id,name,arguments}`, Router resolution + consent/external downgrade rule (table of the four cases), StructuredOutput (extract strategies: whole/fenced/first-brace; single repair; `StructuredOutputError`), CircuitBreaker (threshold/window/cooldown), Middleware (PII patterns, Audit hash sink). State the invariant: **every model call goes through the Client** (chokepoint).
- [ ] **Step 2: Write `docs/AGENT_LOOP.md`**: the ASCII loop diagram `PLAN → EXECUTE → CRITIC → {accept|escalate|replan}`; bounds `MAX_REPLAN` + `MAX_TOKENS_PER_SESSION`; transcript shape; the "Session owns persistence, sub-agents are pure" asymmetry; the wiring points (critic↔grounding gate, success↔memory consolidation, irreversible step↔empowerment advice, result↔four-fold DE); the "never raises out of `run`" guarantee.
- [ ] **Step 3: Write `docs/TOOLING.md`**: how to write a `Tool` subclass (the DSL: `tool_name`/`description`/`parameters`/`scope`, optional `side_effect_class`); `Context` and the identity-from-context rule (forbidden args stripped — K-12/K-16); dispatch return `[ok, payload]`; a worked example tool.
- [ ] **Step 4: Commit**

```bash
git add docs/GATEWAY.md docs/AGENT_LOOP.md docs/TOOLING.md
git commit -m "docs: GATEWAY + AGENT_LOOP + TOOLING"
```

### Task 17.3: CDFL doc (the thesis port)

**Files:**
- Create: `docs/CDFL.md`

- [ ] **Step 1: Write `docs/CDFL.md`** covering, with the real content:
  - **NNL-NTHT in one page**: IF (belief σ + representation Φ), MF (environment ρ), OR (resonant overlap IF-known ⋈ MF-known, γ>0 = true knowledge), DE (four faces: X/T/IF/MF), K = Φ(OR), knowledge gap D = |MF|−|OR|; black dots (γ<0 illusion) / white dots (high ∂OR intuition); action `argmax E[Δ|OR_true|]`; continual loop (DE regrows), local "Aha!"; multi-agent: preserve other IFs → richer global OR → empowerment.
  - **Dynamics equations**: `IF_{t+1}=IF_t+α·∇_IF K`, `MF_{t+1}=Ψ(MF_t,a_t)`, `OR_{t+1}=IF_{t+1}∩MF_{t+1}`, `J=max|OR|`.
  - **The Ruby modules**: TransitionModel (P(s'|s,a), ablation −31.6pp), InfoGain (`novelty=1/√(N+1)`, `uncertainty=1/√(n+1)`, `IG=novelty+λ·uncertainty`), LookaheadPlanner (H-step Monte-Carlo), Agent (Boltzmann pick), FourFoldDE, Empowerment.
  - **HilbertMetric — DESCRIPTIVE gauge**: `I(I:M)=S(ρ_I)+S(ρ_M)−S(ρ_IM)` (the |OR| proxy), `DE=S(ρ‖σ)`; the v11 caveat (active selection ≈ random → measurement only, never on the action path); the real-embedding implementation note (Hermitian → real symmetric 2n×2n, stdlib eigensystem, eigenvalues doubled).
  - **Citations**: `Thuật toán tương ứng.docx` (canonical 12-step), `Phan_IV_Dong_hoc_CDFL`, `Phan_IX_Nghiem_chung` (REPORT_V8/V10/V11), author Nguyễn Trường An.
- [ ] **Step 2: Commit**

```bash
git add docs/CDFL.md
git commit -m "docs: CDFL (NNL-NTHT theory -> algorithm map, |OR|/DE, Hilbert gauge caveat)"
```

### Task 17.4: COVERAGE_GATE + MEMORY_PALACE + EXTENDING + INVARIANTS docs

**Files:**
- Create: `docs/COVERAGE_GATE.md`
- Create: `docs/MEMORY_PALACE.md`
- Create: `docs/EXTENDING.md`
- Create: `docs/INVARIANTS.md`

- [ ] **Step 1: Write `docs/COVERAGE_GATE.md`** ("học 1 hiểu 10"): the coverage formula `1 − exp(−k·Σ sim·confidence)` over **foundational tiers (1,2) only**; the bands (`đủ ≥0.60`, `thận trọng ≥0.30`, `chưa đủ` else) and `can_generalize`; why volatile/tenant tiers are excluded (durable understanding grows over time); the decline-not-hallucinate principle (K-3); how the critic enforces it via `Grounding::Gate` (sim floor `0.35`, memory mass cap); all thresholds are `ReasoningConfig` / env knobs.
- [ ] **Step 2: Write `docs/MEMORY_PALACE.md`** ("cung điện ký ức"): the two orthogonal axes (4 lifecycle tiers L1–L4 × 5 cognitive types) + the classic-taxonomy view; importance formula (§7.5); trust decay (`confidence·0.5^(age/half-life)`, per-type half-lives, fresh/aging/stale, "confident-but-unchecked" flag); maturation (`reinforce_confidence` learning curve toward per-source ceiling; `experience_level = 1−exp(−k·Σ trust)` bands "mới→chuyên gia"); operations (write/retrieve/consolidate/promote/forget/verify/reinforce/link/experience); associative recall (one-hop `links`) + entity boost + trust ranking; the memory→KB promotion loop concept (and that the in-memory ships, DB stores are pluggable).
- [ ] **Step 3: Write `docs/EXTENDING.md`**: how to add a provider adapter (subclass `Adapters::Base`, implement `invoke`/`invoke_chat`/`external?`, wire via `config.adapter_override` or extend `build_adapter`); how to add a `Store` / `Knowledge::Store` / `Memory::TierStore` (implement the contract; pass via `config`); how to add a middleware (input hook `call(prompt:, method:)` or the Audit sink); how to register workflows + tools; how to embed the harness in a host app (build `Config`, `Workflows`, `Registry`, call `Session#run`).
- [ ] **Step 4: Write `docs/INVARIANTS.md`**: the invariants carried over — (1) single LLM chokepoint (Gateway::Client); (2) consent/external downgrade (Router); (3) PII redaction before external (Middleware::PII); (4) identity from Context, forbidden args stripped (Registry); (5) bounded loop (`MAX_REPLAN`, `MAX_TOKENS_PER_SESSION`); (6) decline-not-hallucinate (coverage gate + `requires_grounding` override); (7) `dry_run` ⇒ no side effects + no memory consolidation; (8) option-preservation / consent for irreversible steps (Empowerment); (9) memory writes are best-effort and never fail a session. Map each to its module + spec.
- [ ] **Step 5: Commit**

```bash
git add docs/COVERAGE_GATE.md docs/MEMORY_PALACE.md docs/EXTENDING.md docs/INVARIANTS.md
git commit -m "docs: COVERAGE_GATE + MEMORY_PALACE + EXTENDING + INVARIANTS"
```

---

## Phase 18 — Final verification

### Task 18.1: Full suite + demo + load check

- [ ] **Step 1: Run the entire suite**

Run: `bundle exec rspec`
Expected: ALL PASS (Part 1 + Part 2 specs).

- [ ] **Step 2: Run the demo end-to-end**

Run: `ruby -Ilib examples/insight_to_action.rb`
Expected: prints status=completed, a coverage band, and a four-fold DE line.

- [ ] **Step 3: Verify install-as-a-gem from another dir**

Create a throwaway dir with a `Gemfile`:
```ruby
source "https://rubygems.org"
gem "cdfl_harness", path: "D:/CDFL harness"
```
Run `bundle install` then `ruby -e "require 'cdfl_harness'; p CDFLHarness::VERSION"`.
Expected: prints `"0.1.0"` — confirms the gem is pluggable into any project.

- [ ] **Step 4: Commit a CHANGELOG entry + tag**

```bash
cd "D:\CDFL harness"
# create CHANGELOG.md with a "## 0.1.0" entry summarising the harness
git add CHANGELOG.md
git commit -m "docs: CHANGELOG 0.1.0"
git tag v0.1.0
```

---

## Self-Review (Part 2)

- **Spec coverage:** Workflow/Workflows ✓; Planner (static + LLM + allowed_tools) ✓; Executor (dispatch + dry_run + empowerment + hard-stop) ✓; Critic (deterministic + LLM + grounding override) ✓; Session (loop + bounds + persistence + consolidation + DE + never-raises) ✓; Ollama/Anthropic/OpenAI adapters + `build_adapter` ✓; demo ✓; all 10 architecture docs (README, ARCHITECTURE, GATEWAY, AGENT_LOOP, TOOLING, CDFL, COVERAGE_GATE, MEMORY_PALACE, EXTENDING, INVARIANTS) ✓.
- **Placeholder scan:** no code step is a stub; doc steps list concrete sections + the actual formulas/invariants to include (not "TODO").
- **Type consistency:** `Session#run` → `Types::SessionResult`; `Planner#plan_workflow` → `[Plan, tokens]`; `Critic#review_session` → `Types::CriticVerdict`; `Executor#execute_steps` → `[TranscriptEntry]`; adapter `invoke` → String, `invoke_chat` → `{content:, model_used:, tool_calls:, finish_reason:}`; `Grounding::Gate.assess` keys consumed by Critic + Session match Part 1. `Workflow` flags (`llm_critic`, `requires_grounding`, `static_plan`) consistent across Planner/Critic/Session.
- **Cross-part consistency:** Part 2 re-enables the `agent/session` require in `lib/cdfl_harness.rb` (deferred in Part 1 Phase 9). `build_adapter` replaced in Task 15.3 matches the Part 1 stub's contract (returns an adapter responding to `invoke`).
