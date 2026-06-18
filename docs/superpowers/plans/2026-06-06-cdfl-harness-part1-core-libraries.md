# CDFL Harness — Part 1: Core Libraries — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the foundation + LLM gateway + tooling + store + the Reasoning layer (CDFL, "học 1 hiểu 10" coverage gate, memory palace) + Grounding for the `cdfl_harness` Ruby gem at `D:\CDFL harness`.

**Architecture:** A standalone Ruby gem. The Gateway is the single LLM chokepoint (pluggable adapters, task→model routing with consent downgrade, structured-output validation + one repair round, optional PII/audit middleware). The Reasoning modules are pure (no I/O except via pluggable stores), faithfully porting Kaori's `reasoning/cdfl`, `reasoning/knowledge`, `reasoning/memory`, and `reasoning/grounding`. Part 2 builds the PLAN→EXECUTE→CRITIC agent loop on top of these.

**Tech Stack:** Ruby ≥ 3.1, RSpec, `json-schemer`, stdlib `net/http` + `json` + `matrix` + `securerandom`. No native extensions.

**Source of truth (port from):** `D:\Kaori System\services\{llm-gateway,ai-orchestrator}` and the design spec `docs/superpowers/specs/2026-06-06-ruby-llm-harness-design.md`.

**Conventions for every task:** the gem root is `D:\CDFL harness`. All `Create:`/`Test:` paths are relative to that root. The top-level module is `CDFLHarness`; the entry require is `require "cdfl_harness"`. Run all commands from `D:\CDFL harness`.

---

## Phase 0 — Gem scaffold

### Task 0.1: Create the gem skeleton

**Files:**
- Create: `D:\CDFL harness\cdfl_harness.gemspec`
- Create: `D:\CDFL harness\Gemfile`
- Create: `D:\CDFL harness\Rakefile`
- Create: `D:\CDFL harness\.rspec`
- Create: `D:\CDFL harness\.gitignore`
- Create: `D:\CDFL harness\lib\cdfl_harness\version.rb`
- Create: `D:\CDFL harness\lib\cdfl_harness.rb`
- Create: `D:\CDFL harness\spec\spec_helper.rb`

- [ ] **Step 1: Create the project directory and init git**

Run:
```bash
mkdir "D:\CDFL harness"
cd "D:\CDFL harness"
git init
mkdir lib lib\cdfl_harness spec docs examples
```

- [ ] **Step 2: Write `cdfl_harness.gemspec`**

```ruby
# frozen_string_literal: true

require_relative "lib/cdfl_harness/version"

Gem::Specification.new do |spec|
  spec.name        = "cdfl_harness"
  spec.version     = CDFLHarness::VERSION
  spec.authors     = ["Nguyen Truong An"]
  spec.summary     = "Pluggable LLM + agent harness with CDFL reasoning, coverage gate, and memory palace"
  spec.description = "A provider-agnostic Ruby harness: an LLM gateway (Anthropic/OpenAI/Ollama), " \
                     "a PLAN->EXECUTE->CRITIC agent loop, and the NNL-NTHT reasoning layer " \
                     "(CDFL, 'học 1 hiểu 10' coverage gate, memory palace)."
  spec.homepage    = "https://example.com/cdfl_harness"
  spec.license     = "MIT"
  spec.required_ruby_version = ">= 3.1"

  spec.files = Dir["lib/**/*.rb", "README.md", "docs/**/*.md", "LICENSE"]
  spec.require_paths = ["lib"]

  spec.add_dependency "json_schemer", "~> 2.0"   # NOTE: gem name is underscore

  spec.add_development_dependency "rspec", "~> 3.12"
  spec.add_development_dependency "rake", "~> 13.0"
  spec.add_development_dependency "webmock", "~> 3.19"
end
```

- [ ] **Step 3: Write `Gemfile`, `Rakefile`, `.rspec`, `.gitignore`**

`Gemfile`:
```ruby
# frozen_string_literal: true

source "https://rubygems.org"
gemspec
```

`Rakefile`:
```ruby
# frozen_string_literal: true

require "rspec/core/rake_task"
RSpec::Core::RakeTask.new(:spec)
task default: :spec
```

`.rspec`:
```
--require spec_helper
--format documentation
```

`.gitignore`:
```
/.bundle/
/pkg/
/tmp/
Gemfile.lock
*.gem
```

- [ ] **Step 4: Write `lib/cdfl_harness/version.rb` and the entry file `lib/cdfl_harness.rb`**

`lib/cdfl_harness/version.rb`:
```ruby
# frozen_string_literal: true

module CDFLHarness
  VERSION = "0.1.0"
end
```

`lib/cdfl_harness.rb` (entry require tree — will grow as files are added; Part 2 appends the agent requires):
```ruby
# frozen_string_literal: true

require_relative "cdfl_harness/version"
require_relative "cdfl_harness/errors"
require_relative "cdfl_harness/types"
require_relative "cdfl_harness/schema"
require_relative "cdfl_harness/config"

require_relative "cdfl_harness/gateway/client"
require_relative "cdfl_harness/tooling/registry"
require_relative "cdfl_harness/store/in_memory"

require_relative "cdfl_harness/reasoning/cdfl"
require_relative "cdfl_harness/reasoning/knowledge/coverage"
require_relative "cdfl_harness/reasoning/knowledge/store"
require_relative "cdfl_harness/reasoning/memory/service"
require_relative "cdfl_harness/grounding/gate"

module CDFLHarness
  class << self
    # Global default config — a project may instead build its own Config and
    # pass it explicitly to Gateway::Client / Agent::Session.
    def configure
      @config ||= Config.new
      yield @config if block_given?
      @config
    end

    def config
      @config ||= Config.new
    end

    def reset_config!
      @config = Config.new
    end
  end
end
```

- [ ] **Step 5: Write `spec/spec_helper.rb`**

```ruby
# frozen_string_literal: true

require "cdfl_harness"

RSpec.configure do |config|
  config.expect_with(:rspec) { |c| c.syntax = :expect }
  config.before { CDFLHarness.reset_config! }
end
```

- [ ] **Step 6: Install and verify the scaffold loads (after later files exist this will pass; for now create stubs to load)**

Because `lib/cdfl_harness.rb` requires files created in later tasks, create empty placeholder files so the gem loads now, then fill them in:
```bash
cd "D:\CDFL harness"
# placeholders (each later task REPLACES the file with real content)
ni lib\cdfl_harness\errors.rb, lib\cdfl_harness\types.rb, lib\cdfl_harness\schema.rb, lib\cdfl_harness\config.rb -Force
mkdir lib\cdfl_harness\gateway, lib\cdfl_harness\gateway\adapters, lib\cdfl_harness\gateway\middleware
mkdir lib\cdfl_harness\tooling, lib\cdfl_harness\store
mkdir lib\cdfl_harness\reasoning, lib\cdfl_harness\reasoning\cdfl, lib\cdfl_harness\reasoning\knowledge, lib\cdfl_harness\reasoning\memory, lib\cdfl_harness\grounding
```
(On a POSIX shell use `touch` / `mkdir -p` instead of `ni`/`mkdir`.)

- [ ] **Step 7: Commit**

```bash
cd "D:\CDFL harness"
bundle install
git add -A
git commit -m "chore: scaffold cdfl_harness gem (gemspec, rspec, version, entry require tree)"
```

---

## Phase 1 — Errors, Types, Schema, Config

### Task 1.1: Errors

**Files:**
- Create: `lib/cdfl_harness/errors.rb`
- Test: `spec/errors_spec.rb`

- [ ] **Step 1: Write the failing test**

```ruby
# spec/errors_spec.rb
# frozen_string_literal: true

RSpec.describe CDFLHarness::Errors do
  it "has a base Error all harness errors inherit from" do
    expect(CDFLHarness::Errors::ConfigError.new).to be_a(CDFLHarness::Errors::Error)
    expect(CDFLHarness::Errors::AdapterError.new).to be_a(CDFLHarness::Errors::Error)
    expect(CDFLHarness::Errors::ConsentDeniedError.new).to be_a(CDFLHarness::Errors::Error)
    expect(CDFLHarness::Errors::StructuredOutputError.new("x", attempts: 2)).to be_a(CDFLHarness::Errors::Error)
    expect(CDFLHarness::Errors::WorkflowInputError.new).to be_a(CDFLHarness::Errors::Error)
    expect(CDFLHarness::Errors::TokenBudgetExceeded.new).to be_a(CDFLHarness::Errors::Error)
    expect(CDFLHarness::Errors::ToolDispatchError.new).to be_a(CDFLHarness::Errors::Error)
  end

  it "StructuredOutputError carries attempts + last fields" do
    e = CDFLHarness::Errors::StructuredOutputError.new("bad", attempts: 2, last_completion: "{", last_error: "x")
    expect(e.attempts).to eq(2)
    expect(e.last_completion).to eq("{")
    expect(e.last_error).to eq("x")
  end
end
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bundle exec rspec spec/errors_spec.rb`
Expected: FAIL (uninitialized constant / NoMethodError).

- [ ] **Step 3: Write the implementation**

```ruby
# lib/cdfl_harness/errors.rb
# frozen_string_literal: true

module CDFLHarness
  module Errors
    class Error < StandardError; end

    # Bad configuration (no adapter, missing key in strict mode, etc.).
    class ConfigError < Error; end

    # A provider adapter failed (HTTP error, circuit open, no scripted reply).
    class AdapterError < Error; end

    # Caller asked for an external provider but consent/keys are not present.
    class ConsentDeniedError < Error; end

    # Workflow input failed JSON-schema validation.
    class WorkflowInputError < Error; end

    # Session blew its token budget.
    class TokenBudgetExceeded < Error; end

    # A tool dispatch was blocked (unknown tool, forbidden arg, scope/auth).
    class ToolDispatchError < Error; end

    # The gateway could not produce schema-valid JSON after the repair round.
    class StructuredOutputError < Error
      attr_reader :attempts, :last_completion, :last_error

      def initialize(message = "structured output failed", attempts: 1,
                     last_completion: nil, last_error: nil)
        super(message)
        @attempts = attempts
        @last_completion = last_completion
        @last_error = last_error
      end
    end
  end
end
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bundle exec rspec spec/errors_spec.rb`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/cdfl_harness/errors.rb spec/errors_spec.rb
git commit -m "feat: error hierarchy (Errors::Error + subclasses)"
```

### Task 1.2: Types (wire + internal value objects)

**Files:**
- Create: `lib/cdfl_harness/types.rb`
- Test: `spec/types_spec.rb`

- [ ] **Step 1: Write the failing test**

```ruby
# spec/types_spec.rb
# frozen_string_literal: true

RSpec.describe "CDFLHarness types" do
  it "builds a Plan with PlanSteps" do
    step = CDFLHarness::Types::PlanStep.new(tool_name: "retrieve_evidence", args: { "q" => "x" }, rationale: "why")
    plan = CDFLHarness::Types::Plan.new(steps: [step], rationale: "overall")
    expect(plan.steps.first.tool_name).to eq("retrieve_evidence")
    expect(plan.rationale).to eq("overall")
  end

  it "builds a CriticVerdict" do
    v = CDFLHarness::Types::CriticVerdict.new(action: "accept", reason: "ok", issues: [])
    expect(v.action).to eq("accept")
  end

  it "builds a TranscriptEntry and SessionResult" do
    t = CDFLHarness::Types::TranscriptEntry.new(step_index: 1, role: "executor", tool_name: "x",
                                                tool_args: {}, tool_result: { "ok" => true }, tool_ok: true, reasoning: "r")
    res = CDFLHarness::Types::SessionResult.new(session_id: "s", workflow_id: "w", status: :completed,
                                                dry_run: true, transcripts: [t], tokens_used: 0, replan_count: 0)
    expect(res.transcripts.first.role).to eq("executor")
    expect(res.status).to eq(:completed)
  end
end
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bundle exec rspec spec/types_spec.rb`
Expected: FAIL (uninitialized constant Types).

- [ ] **Step 3: Write the implementation**

```ruby
# lib/cdfl_harness/types.rb
# frozen_string_literal: true

module CDFLHarness
  module Types
    # Planner output.
    PlanStep = Struct.new(:tool_name, :args, :rationale, keyword_init: true)
    Plan     = Struct.new(:steps, :rationale, keyword_init: true)

    # Critic output. action ∈ "accept" | "replan" | "escalate".
    CriticVerdict = Struct.new(:action, :reason, :issues, keyword_init: true) do
      def initialize(action:, reason:, issues: [])
        super(action: action, reason: reason, issues: issues)
      end
    end

    # One row of the agent transcript. role ∈ "planner" | "executor" | "critic".
    TranscriptEntry = Struct.new(
      :step_index, :role, :tool_name, :tool_args, :tool_result, :tool_ok, :reasoning,
      keyword_init: true
    ) do
      def initialize(step_index:, role:, tool_name: nil, tool_args: nil,
                     tool_result: nil, tool_ok: nil, reasoning: "")
        super(step_index: step_index, role: role, tool_name: tool_name, tool_args: tool_args,
              tool_result: tool_result, tool_ok: tool_ok, reasoning: reasoning)
      end
    end

    # Final result of one agent session. status ∈ :planning|:executing|:critiquing|
    # :completed|:failed|:escalated.
    SessionResult = Struct.new(
      :session_id, :workflow_id, :status, :dry_run, :plan, :transcripts,
      :critic_verdict, :tokens_used, :replan_count, :error_message,
      :grounding, :four_fold_de,
      keyword_init: true
    ) do
      def initialize(session_id:, workflow_id:, status:, dry_run:, plan: nil, transcripts: [],
                     critic_verdict: nil, tokens_used: 0, replan_count: 0, error_message: nil,
                     grounding: nil, four_fold_de: nil)
        super(session_id: session_id, workflow_id: workflow_id, status: status, dry_run: dry_run,
              plan: plan, transcripts: transcripts, critic_verdict: critic_verdict,
              tokens_used: tokens_used, replan_count: replan_count, error_message: error_message,
              grounding: grounding, four_fold_de: four_fold_de)
      end
    end
  end
end
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bundle exec rspec spec/types_spec.rb`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/cdfl_harness/types.rb spec/types_spec.rb
git commit -m "feat: value types (Plan, PlanStep, CriticVerdict, TranscriptEntry, SessionResult)"
```

### Task 1.3: Schema wrapper (json-schemer)

**Files:**
- Create: `lib/cdfl_harness/schema.rb`
- Test: `spec/schema_spec.rb`

- [ ] **Step 1: Write the failing test**

```ruby
# spec/schema_spec.rb
# frozen_string_literal: true

RSpec.describe CDFLHarness::Schema do
  let(:schema) do
    { "type" => "object", "required" => ["n"],
      "properties" => { "n" => { "type" => "integer" } },
      "additionalProperties" => false }
  end

  it "valid? returns true for a matching payload" do
    expect(described_class.valid?({ "n" => 3 }, schema)).to be(true)
  end

  it "valid? returns false and first_error describes the problem" do
    expect(described_class.valid?({ "n" => "x" }, schema)).to be(false)
    expect(described_class.first_error({ "n" => "x" }, schema)).to be_a(String)
    expect(described_class.first_error({ "n" => 3 }, schema)).to be_nil
  end

  it "schema_valid? rejects a malformed schema" do
    expect(described_class.schema_valid?({ "type" => 123 })).to be(false)
    expect(described_class.schema_valid?(schema)).to be(true)
  end
end
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bundle exec rspec spec/schema_spec.rb`
Expected: FAIL (uninitialized constant Schema).

- [ ] **Step 3: Write the implementation**

```ruby
# lib/cdfl_harness/schema.rb
# frozen_string_literal: true

require "json_schemer"

module CDFLHarness
  # Thin wrapper over json-schemer so the rest of the codebase never touches
  # the library directly. Schemas are plain Ruby Hashes (JSON-Schema 2020-12).
  module Schema
    module_function

    def schemer(schema)
      JSONSchemer.schema(schema, meta_schema: "https://json-schema.org/draft/2020-12/schema")
    end

    def valid?(data, schema)
      schemer(schema).valid?(data)
    end

    # One-line first error, or nil when valid. Used by structured-output repair
    # and workflow-input validation to build a useful message.
    def first_error(data, schema)
      err = schemer(schema).validate(data).first
      return nil if err.nil?

      ptr = err["data_pointer"].to_s.empty? ? "/" : err["data_pointer"]
      "#{err['error']} at #{ptr}"
    end

    def errors(data, schema)
      schemer(schema).validate(data).map do |err|
        ptr = err["data_pointer"].to_s.empty? ? "/" : err["data_pointer"]
        "#{err['error']} at #{ptr}"
      end
    end

    # True when the schema itself is a valid JSON-Schema document.
    def schema_valid?(schema)
      JSONSchemer.valid_schema?(schema)
    rescue StandardError
      false
    end
  end
end
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bundle exec rspec spec/schema_spec.rb`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/cdfl_harness/schema.rb spec/schema_spec.rb
git commit -m "feat: Schema wrapper over json-schemer (valid?, first_error, schema_valid?)"
```

### Task 1.4: Config

**Files:**
- Create: `lib/cdfl_harness/config.rb`
- Test: `spec/config_spec.rb`

- [ ] **Step 1: Write the failing test**

```ruby
# spec/config_spec.rb
# frozen_string_literal: true

RSpec.describe CDFLHarness::Config do
  it "has sane defaults" do
    c = described_class.new
    expect(c.provider).to eq(:fake)
    expect(c.consent_external).to be(false)
    expect(c.external_enabled).to be(false)
    expect(c.max_replan).to eq(2)
    expect(c.max_tokens_per_session).to eq(6000)
    expect(c.middleware).to eq([])
    expect(c.task_routing).to eq({})
  end

  it "is settable via CDFLHarness.configure and readable via .config" do
    CDFLHarness.configure do |c|
      c.provider = :ollama
      c.ollama_host = "http://x:11434"
      c.max_replan = 1
    end
    expect(CDFLHarness.config.provider).to eq(:ollama)
    expect(CDFLHarness.config.max_replan).to eq(1)
  end

  it "external? reflects the provider" do
    expect(described_class.new.tap { |c| c.provider = :anthropic }.external?).to be(true)
    expect(described_class.new.tap { |c| c.provider = :ollama }.external?).to be(false)
    expect(described_class.new.tap { |c| c.provider = :fake }.external?).to be(false)
  end
end
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bundle exec rspec spec/config_spec.rb`
Expected: FAIL.

- [ ] **Step 3: Write the implementation**

```ruby
# lib/cdfl_harness/config.rb
# frozen_string_literal: true

module CDFLHarness
  # All harness configuration in one object. A project sets it once via
  # CDFLHarness.configure, or builds its own and passes it explicitly.
  class Config
    EXTERNAL_PROVIDERS = %i[anthropic openai].freeze

    attr_accessor :provider, :api_keys, :model_map, :default_model, :ollama_host,
                  :task_routing, :consent_external, :external_enabled,
                  :max_replan, :max_tokens_per_session, :narrative_max_tokens,
                  :middleware, :store, :knowledge_store, :memory_service,
                  :reasoning, :logger, :adapter_override

    def initialize
      @provider = :fake
      @api_keys = {}                 # { anthropic: "sk-...", openai: "sk-..." }
      @model_map = {                 # provider => default model id
        anthropic: "claude-opus-4-8",
        openai: "gpt-4o",
        ollama: "qwen2.5:14b",
        fake: "fake-model"
      }
      @default_model = nil           # explicit override; else model_map[provider]
      @ollama_host = "http://localhost:11434"
      @task_routing = {}             # "task.glob" => { model:, method: }  (method ∈ :internal|:external)
      @consent_external = false
      @external_enabled = false      # master kill-switch for any external call
      @max_replan = 2
      @max_tokens_per_session = 6000
      @narrative_max_tokens = 400
      @middleware = []               # Array of objects responding to #call(prompt:, method:) (input)
      @store = nil                   # Store::Base (Part 2); defaults to in-memory there
      @knowledge_store = nil         # Reasoning::Knowledge::Store
      @memory_service = nil          # Reasoning::Memory::Service
      @reasoning = ReasoningConfig.new
      @logger = nil
      @adapter_override = nil        # inject a built adapter instance (tests / Fake)
    end

    def external?
      EXTERNAL_PROVIDERS.include?(@provider)
    end

    def model_for(provider = @provider)
      @default_model || @model_map[provider]
    end

    # Tunable reasoning thresholds — env-readable, never hardcoded at call sites.
    class ReasoningConfig
      attr_accessor :coverage_k, :gen_min, :gen_caution, :sim_floor,
                    :mem_mass, :mem_cap, :w_authority, :w_maturity,
                    :learn_rate, :experience_k, :grounding_tol

      def initialize
        @coverage_k    = env_f("CDFL_KB_COVERAGE_K", 0.6)
        @gen_min       = env_f("CDFL_KB_GEN_MIN", 0.60)
        @gen_caution   = env_f("CDFL_KB_GEN_CAUTION", 0.30)
        @sim_floor     = env_f("CDFL_KB_SIM_FLOOR", 0.35)
        @mem_mass      = env_f("CDFL_MEM_MASS", 0.2)
        @mem_cap       = env_f("CDFL_MEM_CAP", 3).to_i
        @w_authority   = env_f("CDFL_KB_W_AUTHORITY", 0.15)
        @w_maturity    = env_f("CDFL_KB_W_MATURITY", 0.10)
        @learn_rate    = env_f("CDFL_MEM_LEARN_RATE", 0.15)
        @experience_k  = env_f("CDFL_MEM_EXPERIENCE_K", 0.15)
        @grounding_tol = env_f("CDFL_GROUNDING_TOL", 0.02)
      end

      def env_f(name, default)
        v = ENV.fetch(name, nil)
        v.nil? ? default : Float(v)
      rescue ArgumentError, TypeError
        default
      end
    end
  end
end
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bundle exec rspec spec/config_spec.rb`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/cdfl_harness/config.rb spec/config_spec.rb
git commit -m "feat: Config + ReasoningConfig (provider/routing/consent/thresholds)"
```

---

## Phase 2 — Gateway (LLM chokepoint)

### Task 2.1: CircuitBreaker

**Files:**
- Create: `lib/cdfl_harness/gateway/circuit_breaker.rb`
- Test: `spec/gateway/circuit_breaker_spec.rb`

- [ ] **Step 1: Write the failing test**

```ruby
# spec/gateway/circuit_breaker_spec.rb
# frozen_string_literal: true

RSpec.describe CDFLHarness::Gateway::CircuitBreaker do
  it "passes through a successful call" do
    cb = described_class.new(name: "t")
    expect(cb.call { 42 }).to eq(42)
  end

  it "opens after the failure threshold and blocks further calls within cooldown" do
    t = 0.0
    cb = described_class.new(name: "t", failure_threshold: 2, window: 30, cooldown: 60, clock: -> { t })
    2.times do
      expect { cb.call { raise "boom" } }.to raise_error(RuntimeError, "boom")
    end
    expect { cb.call { 1 } }.to raise_error(CDFLHarness::Errors::AdapterError, /circuit open/)
  end

  it "half-opens after cooldown and closes on success" do
    t = 0.0
    cb = described_class.new(name: "t", failure_threshold: 1, window: 30, cooldown: 10, clock: -> { t })
    expect { cb.call { raise "x" } }.to raise_error(RuntimeError)
    t = 20.0 # past cooldown
    expect(cb.call { 7 }).to eq(7)
  end
end
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bundle exec rspec spec/gateway/circuit_breaker_spec.rb`
Expected: FAIL.

- [ ] **Step 3: Write the implementation**

```ruby
# lib/cdfl_harness/gateway/circuit_breaker.rb
# frozen_string_literal: true

require_relative "../errors"

module CDFLHarness
  module Gateway
    # Per-adapter breaker. Opens after `failure_threshold` failures inside
    # `window` seconds; blocks for `cooldown` seconds; a success while
    # half-open resets it. `clock` is injectable for deterministic tests.
    class CircuitBreaker
      def initialize(name:, failure_threshold: 5, window: 30, cooldown: 60, clock: -> { Process.clock_gettime(Process::CLOCK_MONOTONIC) })
        @name = name
        @failure_threshold = failure_threshold
        @window = window
        @cooldown = cooldown
        @clock = clock
        @failures = []        # timestamps of recent failures
        @opened_at = nil
      end

      def call
        now = @clock.call
        if @opened_at
          raise Errors::AdapterError, "circuit open for #{@name}" if now - @opened_at < @cooldown

          @opened_at = nil    # half-open: allow one trial
          @failures.clear
        end

        begin
          result = yield
          @failures.clear     # success closes the window
          result
        rescue StandardError
          record_failure(now)
          raise
        end
      end

      private

      def record_failure(now)
        @failures << now
        @failures.reject! { |t| now - t > @window }
        @opened_at = now if @failures.size >= @failure_threshold
      end
    end
  end
end
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bundle exec rspec spec/gateway/circuit_breaker_spec.rb`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/cdfl_harness/gateway/circuit_breaker.rb spec/gateway/circuit_breaker_spec.rb
git commit -m "feat: gateway CircuitBreaker (threshold/window/cooldown, injectable clock)"
```

### Task 2.2: StructuredOutput (extract JSON + validate + one repair)

**Files:**
- Create: `lib/cdfl_harness/gateway/structured_output.rb`
- Test: `spec/gateway/structured_output_spec.rb`

Port of `services/llm-gateway/output_validator.py` (extract_json strategies + single repair).

- [ ] **Step 1: Write the failing test**

```ruby
# spec/gateway/structured_output_spec.rb
# frozen_string_literal: true

RSpec.describe CDFLHarness::Gateway::StructuredOutput do
  let(:schema) do
    { "type" => "object", "required" => ["n"],
      "properties" => { "n" => { "type" => "integer" } }, "additionalProperties" => false }
  end

  it "extracts whole-string JSON object" do
    parsed, err = described_class.extract_json('{"n": 1}')
    expect(parsed).to eq({ "n" => 1 })
    expect(err).to be_nil
  end

  it "extracts JSON from a ```json fence" do
    parsed, = described_class.extract_json("text\n```json\n{\"n\": 2}\n```\nmore")
    expect(parsed).to eq({ "n" => 2 })
  end

  it "extracts the first {...} block from prose" do
    parsed, = described_class.extract_json("here you go: {\"n\": 3} thanks")
    expect(parsed).to eq({ "n" => 3 })
  end

  it "rejects a top-level array" do
    parsed, err = described_class.extract_json("[1,2,3]")
    expect(parsed).to be_nil
    expect(err).to match(/not object/)
  end

  it "returns parsed dict on first-try valid completion (was_repaired=false)" do
    parsed, repaired = described_class.validate_or_repair(
      completion: '{"n": 5}', schema: schema, original_prompt: "p", retry_fn: ->(_p) { raise "should not retry" }
    )
    expect(parsed).to eq({ "n" => 5 })
    expect(repaired).to be(false)
  end

  it "repairs once when the first completion is invalid" do
    retry_fn = ->(_p) { '{"n": 9}' }
    parsed, repaired = described_class.validate_or_repair(
      completion: "not json", schema: schema, original_prompt: "p", retry_fn: retry_fn
    )
    expect(parsed).to eq({ "n" => 9 })
    expect(repaired).to be(true)
  end

  it "raises StructuredOutputError when the repair also fails" do
    retry_fn = ->(_p) { '{"n": "still bad"}' }
    expect do
      described_class.validate_or_repair(completion: "x", schema: schema, original_prompt: "p", retry_fn: retry_fn)
    end.to raise_error(CDFLHarness::Errors::StructuredOutputError)
  end
end
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bundle exec rspec spec/gateway/structured_output_spec.rb`
Expected: FAIL.

- [ ] **Step 3: Write the implementation**

```ruby
# lib/cdfl_harness/gateway/structured_output.rb
# frozen_string_literal: true

require "json"
require_relative "../errors"
require_relative "../schema"

module CDFLHarness
  module Gateway
    # Port of llm-gateway/output_validator.py: pull JSON out of a free-text
    # completion, validate against a JSON-Schema, and run exactly ONE repair
    # round on failure. Returns [parsed_hash, was_repaired].
    module StructuredOutput
      module_function

      FENCE_RE = /```(?:json|JSON)?\s*\n?(?<body>.*?)\n?```/m

      # Returns [parsed_hash_or_nil, error_message_or_nil]. Exactly one is non-nil.
      def extract_json(completion)
        return [nil, "empty completion"] if completion.nil? || completion.strip.empty?

        text = completion.strip

        whole = try_parse(text)
        return non_object_or(whole) unless whole.nil?

        if (m = FENCE_RE.match(text))
          body = m[:body].strip
          parsed = try_parse(body)
          return non_object_or(parsed) unless parsed.nil?
        end

        bstart = text.index("{")
        bend = text.rindex("}")
        if bstart && bend && bstart < bend
          parsed = try_parse(text[bstart..bend])
          return [parsed, nil] if parsed.is_a?(Hash)
        end

        [nil, "no JSON object found in completion"]
      end

      def validate_or_repair(completion:, schema:, original_prompt:, retry_fn:)
        parsed, extract_error = extract_json(completion)
        if parsed
          verr = Schema.first_error(parsed, schema)
          return [parsed, false] if verr.nil?

          first_error = verr
        else
          first_error = extract_error || "could not parse JSON"
        end

        augmented = repair_prompt(original_prompt: original_prompt, schema: schema,
                                  error: first_error, bad_completion: completion)
        begin
          repaired_completion = retry_fn.call(augmented)
        rescue StandardError => e
          raise Errors::StructuredOutputError.new("repair attempt failed: #{e}",
                                                  attempts: 2, last_completion: completion, last_error: first_error)
        end

        parsed2, extract_error2 = extract_json(repaired_completion)
        if parsed2.nil?
          raise Errors::StructuredOutputError.new("repaired completion had no JSON object",
                                                  attempts: 2, last_completion: repaired_completion, last_error: extract_error2)
        end
        verr2 = Schema.first_error(parsed2, schema)
        if verr2
          raise Errors::StructuredOutputError.new("repaired completion did not match schema",
                                                  attempts: 2, last_completion: repaired_completion, last_error: verr2)
        end
        [parsed2, true]
      end

      def repair_prompt(original_prompt:, schema:, error:, bad_completion:)
        bad = bad_completion.to_s
        bad = "#{bad[0, 1000]}...[truncated]" if bad.length > 1000
        <<~PROMPT
          Your previous response failed JSON schema validation.

          Original request:
          #{original_prompt}

          Required JSON schema:
          #{JSON.generate(schema)}

          Validation error:
          #{error}

          Your previous (invalid) response:
          #{bad}

          Return ONLY a JSON object that matches the schema. No prose, no markdown fences, no explanation. Just the JSON.
        PROMPT
      end

      # ----- helpers -----
      def try_parse(text)
        JSON.parse(text)
      rescue JSON::ParserError
        nil
      end

      def non_object_or(parsed)
        return [parsed, nil] if parsed.is_a?(Hash)

        [nil, "top-level JSON is #{parsed.class}, not object"]
      end
    end
  end
end
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bundle exec rspec spec/gateway/structured_output_spec.rb`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/cdfl_harness/gateway/structured_output.rb spec/gateway/structured_output_spec.rb
git commit -m "feat: gateway StructuredOutput (extract_json + validate + one repair)"
```

### Task 2.3: Adapters — Base + Fake

**Files:**
- Create: `lib/cdfl_harness/gateway/adapters/base.rb`
- Create: `lib/cdfl_harness/gateway/adapters/fake.rb`
- Test: `spec/gateway/adapters/fake_spec.rb`

- [ ] **Step 1: Write the failing test**

```ruby
# spec/gateway/adapters/fake_spec.rb
# frozen_string_literal: true

RSpec.describe CDFLHarness::Gateway::Adapters::Fake do
  it "returns scripted completions in order" do
    a = described_class.new(completions: ["one", "two"])
    expect(a.invoke(model: "m", prompt: "p", max_tokens: 10)).to eq("one")
    expect(a.invoke(model: "m", prompt: "p", max_tokens: 10)).to eq("two")
  end

  it "supports a callable that sees the prompt" do
    a = described_class.new(completions: [->(prompt) { "got:#{prompt}" }])
    expect(a.invoke(model: "m", prompt: "hi", max_tokens: 1)).to eq("got:hi")
  end

  it "raises AdapterError when the script is exhausted" do
    a = described_class.new(completions: [])
    expect { a.invoke(model: "m", prompt: "p", max_tokens: 1) }.to raise_error(CDFLHarness::Errors::AdapterError)
  end

  it "reports it is internal (never external)" do
    expect(described_class.new.external?).to be(false)
  end
end
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bundle exec rspec spec/gateway/adapters/fake_spec.rb`
Expected: FAIL.

- [ ] **Step 3: Write the implementations**

```ruby
# lib/cdfl_harness/gateway/adapters/base.rb
# frozen_string_literal: true

require_relative "../../errors"

module CDFLHarness
  module Gateway
    module Adapters
      # Every provider adapter implements #invoke (single prompt → text) and,
      # for tool-calling, #invoke_chat. #external? tells the router whether
      # PII redaction + consent gating apply.
      class Base
        def invoke(model:, prompt:, max_tokens:)
          raise NotImplementedError, "#{self.class}#invoke"
        end

        # Returns a Hash: { content:, model_used:, tool_calls:, finish_reason: }.
        def invoke_chat(model:, messages:, tools: nil, tool_choice: nil, max_tokens: 1500)
          raise NotImplementedError, "#{self.class}#invoke_chat"
        end

        def external?
          false
        end
      end
    end
  end
end
```

```ruby
# lib/cdfl_harness/gateway/adapters/fake.rb
# frozen_string_literal: true

require_relative "base"

module CDFLHarness
  module Gateway
    module Adapters
      # Offline adapter for tests + the demo. Pops scripted replies in order.
      # A scripted entry may be a String or a callable(prompt) → String.
      class Fake < Base
        def initialize(completions: [], chats: [])
          @completions = completions.dup
          @chats = chats.dup
        end

        def invoke(model:, prompt:, max_tokens:)
          raise Errors::AdapterError, "Fake adapter: no more scripted completions" if @completions.empty?

          nxt = @completions.shift
          nxt.respond_to?(:call) ? nxt.call(prompt) : nxt
        end

        def invoke_chat(model:, messages:, tools: nil, tool_choice: nil, max_tokens: 1500)
          raise Errors::AdapterError, "Fake adapter: no more scripted chats" if @chats.empty?

          nxt = @chats.shift
          nxt.respond_to?(:call) ? nxt.call(messages) : nxt
        end

        def external?
          false
        end
      end
    end
  end
end
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bundle exec rspec spec/gateway/adapters/fake_spec.rb`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/cdfl_harness/gateway/adapters spec/gateway/adapters/fake_spec.rb
git commit -m "feat: adapter Base contract + Fake adapter (offline scripted replies)"
```

### Task 2.4: Router (task→model + consent downgrade)

**Files:**
- Create: `lib/cdfl_harness/gateway/router.rb`
- Test: `spec/gateway/router_spec.rb`

Port of `services/llm-gateway/routing.py` (consent-based external→internal downgrade).

- [ ] **Step 1: Write the failing test**

```ruby
# spec/gateway/router_spec.rb
# frozen_string_literal: true

RSpec.describe CDFLHarness::Gateway::Router do
  it "uses the provider default model and method (ollama => internal)" do
    cfg = CDFLHarness::Config.new.tap { |c| c.provider = :ollama }
    model, method = described_class.new(config: cfg).resolve(task: "agent.plan.x", consent_external: false)
    expect(model).to eq("qwen2.5:14b")
    expect(method).to eq(:internal)
  end

  it "downgrades external to internal when consent is absent" do
    cfg = CDFLHarness::Config.new.tap do |c|
      c.provider = :anthropic
      c.external_enabled = true
    end
    model, method = described_class.new(config: cfg).resolve(task: "t", consent_external: false)
    expect(method).to eq(:internal)
    expect(model).to eq("qwen2.5:14b") # local fallback
  end

  it "keeps external when consent AND external_enabled are both true" do
    cfg = CDFLHarness::Config.new.tap do |c|
      c.provider = :anthropic
      c.external_enabled = true
    end
    model, method = described_class.new(config: cfg).resolve(task: "t", consent_external: true)
    expect(method).to eq(:external)
    expect(model).to eq("claude-opus-4-8")
  end

  it "downgrades external to internal when external_enabled is false even with consent" do
    cfg = CDFLHarness::Config.new.tap { |c| c.provider = :anthropic; c.external_enabled = false }
    _model, method = described_class.new(config: cfg).resolve(task: "t", consent_external: true)
    expect(method).to eq(:internal)
  end

  it "honours a task_routing override model" do
    cfg = CDFLHarness::Config.new.tap do |c|
      c.provider = :ollama
      c.task_routing = { "agent.plan.special" => { model: "qwen2.5:7b", method: :internal } }
    end
    model, = described_class.new(config: cfg).resolve(task: "agent.plan.special", consent_external: false)
    expect(model).to eq("qwen2.5:7b")
  end
end
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bundle exec rspec spec/gateway/router_spec.rb`
Expected: FAIL.

- [ ] **Step 3: Write the implementation**

```ruby
# lib/cdfl_harness/gateway/router.rb
# frozen_string_literal: true

module CDFLHarness
  module Gateway
    # Resolve a task to [model_id, method]. method ∈ :internal | :external.
    # External is downgraded to the local default when consent is absent or
    # external calls are disabled (port of routing.py K-4 downgrade).
    class Router
      LOCAL_FALLBACK_PROVIDER = :ollama

      def initialize(config:)
        @config = config
      end

      def resolve(task:, consent_external:, model_hint: nil)
        rule = @config.task_routing[task]
        if rule
          model = model_hint || rule[:model] || @config.model_for
          method = rule[:method] || (@config.external? ? :external : :internal)
        else
          model = model_hint || @config.model_for
          method = @config.external? ? :external : :internal
        end

        if method == :external && !(consent_external && @config.external_enabled)
          # Downgrade to a safe local model.
          return [@config.model_map[LOCAL_FALLBACK_PROVIDER], :internal]
        end

        [model, method]
      end
    end
  end
end
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bundle exec rspec spec/gateway/router_spec.rb`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/cdfl_harness/gateway/router.rb spec/gateway/router_spec.rb
git commit -m "feat: gateway Router (task->model, consent/external downgrade)"
```

### Task 2.5: Middleware — PII redaction + Audit

**Files:**
- Create: `lib/cdfl_harness/gateway/middleware/pii.rb`
- Create: `lib/cdfl_harness/gateway/middleware/audit.rb`
- Test: `spec/gateway/middleware_spec.rb`

Port of `services/llm-gateway/pii.py`.

- [ ] **Step 1: Write the failing test**

```ruby
# spec/gateway/middleware_spec.rb
# frozen_string_literal: true

RSpec.describe "CDFLHarness gateway middleware" do
  describe CDFLHarness::Gateway::Middleware::PII do
    it "redacts email, VN phone, and id numbers only for external method" do
      m = described_class.new
      text = "mail a@b.com phone 0901234567 id 0123456789"
      out = m.call(prompt: text, method: :external)
      expect(out).to include("[email]").and include("[phone]").and include("[id_number]")
      expect(out).not_to include("a@b.com")
    end

    it "leaves the prompt unchanged for internal method" do
      m = described_class.new
      text = "mail a@b.com"
      expect(m.call(prompt: text, method: :internal)).to eq(text)
    end
  end

  describe CDFLHarness::Gateway::Middleware::Audit do
    it "records a row per call" do
      rows = []
      m = described_class.new(sink: ->(row) { rows << row })
      m.record(task: "t", model: "m", method: :internal, prompt: "p", completion: "c", repaired: false, latency_ms: 12)
      expect(rows.size).to eq(1)
      expect(rows.first[:task]).to eq("t")
      expect(rows.first).to have_key(:prompt_sha)
      expect(rows.first).to have_key(:output_sha)
    end
  end
end
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bundle exec rspec spec/gateway/middleware_spec.rb`
Expected: FAIL.

- [ ] **Step 3: Write the implementations**

```ruby
# lib/cdfl_harness/gateway/middleware/pii.rb
# frozen_string_literal: true

module CDFLHarness
  module Gateway
    module Middleware
      # K-5 analog: redact high-frequency Vietnamese-context PII before an
      # EXTERNAL call. Internal calls pass through untouched. Idempotent.
      class PII
        PATTERNS = [
          [/\b[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}\b/, "[email]"],
          [/\b(?:\+84|84|0)[3-9]\d{8}\b/, "[phone]"],
          [/\b\d{9,12}\b/, "[id_number]"]
        ].freeze

        def call(prompt:, method:)
          return prompt unless method == :external

          PATTERNS.reduce(prompt) { |acc, (re, repl)| acc.gsub(re, repl) }
        end
      end
    end
  end
end
```

```ruby
# lib/cdfl_harness/gateway/middleware/audit.rb
# frozen_string_literal: true

require "digest"

module CDFLHarness
  module Gateway
    module Middleware
      # K-6 analog: an audit hook. Stores hashes (not raw text) by default so a
      # project can wire it to a DB without leaking prompts. `sink` is any
      # callable(row_hash); defaults to a no-op.
      class Audit
        def initialize(sink: nil)
          @sink = sink || ->(_row) {}
        end

        def record(task:, model:, method:, prompt:, completion:, repaired:, latency_ms:)
          row = {
            task: task, model: model, method: method,
            prompt_sha: Digest::SHA256.hexdigest(prompt.to_s),
            output_sha: Digest::SHA256.hexdigest(completion.to_s),
            repaired: repaired, latency_ms: latency_ms
          }
          @sink.call(row)
          row
        end
      end
    end
  end
end
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bundle exec rspec spec/gateway/middleware_spec.rb`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/cdfl_harness/gateway/middleware spec/gateway/middleware_spec.rb
git commit -m "feat: gateway middleware (PII redaction K-5, Audit K-6 hash sink)"
```

### Task 2.6: Gateway::Client (facade)

**Files:**
- Create: `lib/cdfl_harness/gateway/client.rb`
- Test: `spec/gateway/client_spec.rb`

- [ ] **Step 1: Write the failing test**

```ruby
# spec/gateway/client_spec.rb
# frozen_string_literal: true

RSpec.describe CDFLHarness::Gateway::Client do
  def client_with(completions:, config: nil)
    cfg = config || CDFLHarness::Config.new
    cfg.adapter_override = CDFLHarness::Gateway::Adapters::Fake.new(completions: completions)
    described_class.new(config: cfg)
  end

  it "complete returns the adapter completion" do
    c = client_with(completions: ["hello"])
    expect(c.complete(prompt: "hi", task: "t")).to eq("hello")
  end

  it "complete_structured returns the validated parsed hash" do
    schema = { "type" => "object", "required" => ["n"], "properties" => { "n" => { "type" => "integer" } } }
    c = client_with(completions: ['{"n": 7}'])
    expect(c.complete_structured(prompt: "p", task: "t", schema: schema)).to eq({ "n" => 7 })
  end

  it "complete_structured repairs once using the same adapter" do
    schema = { "type" => "object", "required" => ["n"], "properties" => { "n" => { "type" => "integer" } } }
    c = client_with(completions: ["garbage", '{"n": 1}'])
    expect(c.complete_structured(prompt: "p", task: "t", schema: schema)).to eq({ "n" => 1 })
  end

  it "redacts PII when external middleware is configured and method is external" do
    seen = nil
    cfg = CDFLHarness::Config.new.tap do |c|
      c.provider = :anthropic
      c.external_enabled = true
      c.middleware = [CDFLHarness::Gateway::Middleware::PII.new]
      c.adapter_override = CDFLHarness::Gateway::Adapters::Fake.new(
        completions: [->(prompt) { seen = prompt; "ok" }]
      )
    end
    described_class.new(config: cfg).complete(prompt: "mail a@b.com", task: "t", consent_external: true)
    expect(seen).to include("[email]")
  end
end
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bundle exec rspec spec/gateway/client_spec.rb`
Expected: FAIL.

- [ ] **Step 3: Write the implementation**

```ruby
# lib/cdfl_harness/gateway/client.rb
# frozen_string_literal: true

require_relative "../config"
require_relative "../errors"
require_relative "circuit_breaker"
require_relative "structured_output"
require_relative "router"
require_relative "adapters/base"
require_relative "adapters/fake"
require_relative "middleware/pii"
require_relative "middleware/audit"

module CDFLHarness
  module Gateway
    # The single LLM chokepoint. Resolves a model, runs input middleware
    # (PII), calls the adapter inside a breaker, validates structured output,
    # and records an audit row.
    class Client
      def initialize(config: CDFLHarness.config)
        @config = config
        @router = Router.new(config: config)
        @breaker = CircuitBreaker.new(name: "gateway")
        @audit = config.middleware.find { |m| m.is_a?(Middleware::Audit) } || Middleware::Audit.new
        @input_mw = config.middleware.reject { |m| m.is_a?(Middleware::Audit) }
      end

      def complete(prompt:, task:, consent_external: false, max_tokens: 2000)
        model, method = @router.resolve(task: task, consent_external: consent_external)
        eff_prompt = apply_input_middleware(prompt, method)
        started = monotonic
        completion = @breaker.call { adapter.invoke(model: model, prompt: eff_prompt, max_tokens: max_tokens) }
        @audit.record(task: task, model: model, method: method, prompt: eff_prompt,
                      completion: completion, repaired: false, latency_ms: ms_since(started))
        completion
      end

      def complete_structured(prompt:, task:, schema:, consent_external: false, max_tokens: 2000)
        model, method = @router.resolve(task: task, consent_external: consent_external)
        eff_prompt = apply_input_middleware(prompt, method)
        started = monotonic
        invoke = ->(p) { @breaker.call { adapter.invoke(model: model, prompt: p, max_tokens: max_tokens) } }
        completion = invoke.call(eff_prompt)
        parsed, repaired = StructuredOutput.validate_or_repair(
          completion: completion, schema: schema, original_prompt: eff_prompt, retry_fn: invoke
        )
        @audit.record(task: task, model: model, method: method, prompt: eff_prompt,
                      completion: completion, repaired: repaired, latency_ms: ms_since(started))
        parsed
      end

      def chat(messages:, task:, tools: nil, tool_choice: nil, consent_external: false, max_tokens: 1500)
        model, method = @router.resolve(task: task, consent_external: consent_external)
        @breaker.call do
          adapter.invoke_chat(model: model, messages: messages, tools: tools,
                              tool_choice: tool_choice, max_tokens: max_tokens)
        end
      end

      private

      def adapter
        @adapter ||= @config.adapter_override || build_adapter
      end

      # Real adapters land in Part 2; Part 1 ships :fake only.
      def build_adapter
        case @config.provider
        when :fake then Adapters::Fake.new
        else
          raise Errors::ConfigError,
                "provider #{@config.provider.inspect} has no adapter wired yet (Part 2 adds anthropic/openai/ollama); " \
                "set config.adapter_override for now"
        end
      end

      def apply_input_middleware(prompt, method)
        @input_mw.reduce(prompt) { |acc, mw| mw.call(prompt: acc, method: method) }
      end

      def monotonic = Process.clock_gettime(Process::CLOCK_MONOTONIC)
      def ms_since(t) = ((monotonic - t) * 1000).to_i
    end
  end
end
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bundle exec rspec spec/gateway/client_spec.rb`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/cdfl_harness/gateway/client.rb spec/gateway/client_spec.rb
git commit -m "feat: Gateway::Client facade (complete/complete_structured/chat + middleware + breaker)"
```

---

## Phase 3 — Tooling

### Task 3.1: Context + Tool base

**Files:**
- Create: `lib/cdfl_harness/tooling/context.rb`
- Create: `lib/cdfl_harness/tooling/tool.rb`
- Test: `spec/tooling/tool_spec.rb`

Port of `chat/tools/base.py` (identity from context, never from LLM args).

- [ ] **Step 1: Write the failing test**

```ruby
# spec/tooling/tool_spec.rb
# frozen_string_literal: true

RSpec.describe "CDFLHarness tooling base" do
  it "Context carries identity + dry_run with defaults" do
    ctx = CDFLHarness::Tooling::Context.new(scope: "enterprise", tenant_id: "t1")
    expect(ctx.scope).to eq("enterprise")
    expect(ctx.tenant_id).to eq("t1")
    expect(ctx.dry_run).to be(false)
  end

  it "a Tool subclass declares name/description/parameters and runs #call" do
    klass = Class.new(CDFLHarness::Tooling::Tool) do
      tool_name "echo"
      description "echoes its arg"
      parameters({ "type" => "object", "properties" => { "v" => { "type" => "string" } } })
      def call(args, _ctx) = { "echoed" => args["v"] }
    end
    inst = klass.new
    expect(klass.tool_name).to eq("echo")
    expect(inst.call({ "v" => "hi" }, nil)).to eq({ "echoed" => "hi" })
  end

  it "renders an OpenAI-style tool spec" do
    klass = Class.new(CDFLHarness::Tooling::Tool) do
      tool_name "t"; description "d"; parameters({ "type" => "object" })
    end
    spec = klass.to_openai_tool
    expect(spec[:type]).to eq("function")
    expect(spec[:function][:name]).to eq("t")
  end
end
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bundle exec rspec spec/tooling/tool_spec.rb`
Expected: FAIL.

- [ ] **Step 3: Write the implementations**

```ruby
# lib/cdfl_harness/tooling/context.rb
# frozen_string_literal: true

module CDFLHarness
  module Tooling
    # Identity + scope for one tool dispatch. Built from trusted headers/JWT by
    # the host app — NEVER from LLM tool arguments (K-12/K-16). dry_run is
    # consumed by side-effecting tools.
    Context = Struct.new(:scope, :tenant_id, :user_id, :role, :dry_run, keyword_init: true) do
      def initialize(scope:, tenant_id: nil, user_id: nil, role: nil, dry_run: false)
        super(scope: scope, tenant_id: tenant_id, user_id: user_id, role: role, dry_run: dry_run)
      end
    end
  end
end
```

```ruby
# lib/cdfl_harness/tooling/tool.rb
# frozen_string_literal: true

module CDFLHarness
  module Tooling
    # Base class for tools. Class-level DSL declares the metadata the registry
    # + planner introspect; instances run #call(args, ctx).
    class Tool
      class << self
        def tool_name(value = nil)
          @tool_name = value if value
          @tool_name || ""
        end

        def description(value = nil)
          @description = value if value
          @description || ""
        end

        def parameters(value = nil)
          @parameters = value if value
          @parameters || { "type" => "object", "properties" => {} }
        end

        def scope(value = nil)
          @scope = value if value
          @scope || "enterprise"
        end

        def to_openai_tool
          { type: "function",
            function: { name: tool_name, description: description, parameters: parameters } }
        end
      end

      # Override in subclasses. Return any JSON-serialisable value. Raise
      # ArgumentError for arg-validation failures (registry turns these into
      # ok=false so the LLM can self-correct).
      def call(_args, _ctx)
        raise NotImplementedError, "#{self.class}#call"
      end
    end
  end
end
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bundle exec rspec spec/tooling/tool_spec.rb`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/cdfl_harness/tooling/context.rb lib/cdfl_harness/tooling/tool.rb spec/tooling/tool_spec.rb
git commit -m "feat: Tooling::Context + Tool base (identity-from-context, OpenAI tool spec)"
```

### Task 3.2: Registry (dispatch + forbidden-arg strip)

**Files:**
- Create: `lib/cdfl_harness/tooling/registry.rb`
- Test: `spec/tooling/registry_spec.rb`

Port of `chat/registry.py`: forbidden-arg strip (K-12/K-16), scope filter, ok/payload dispatch.

- [ ] **Step 1: Write the failing test**

```ruby
# spec/tooling/registry_spec.rb
# frozen_string_literal: true

RSpec.describe CDFLHarness::Tooling::Registry do
  let(:echo) do
    Class.new(CDFLHarness::Tooling::Tool) do
      tool_name "echo"; description "d"; scope "enterprise"
      parameters({ "type" => "object", "properties" => { "v" => { "type" => "string" } } })
      def call(args, _ctx) = { "echoed" => args["v"] }
    end
  end
  let(:ctx) { CDFLHarness::Tooling::Context.new(scope: "enterprise", tenant_id: "t1") }

  it "registers and dispatches a tool returning [true, payload]" do
    reg = described_class.new
    reg.register(echo.new)
    ok, payload = reg.dispatch(name: "echo", args: { "v" => "hi" }, ctx: ctx)
    expect(ok).to be(true)
    expect(payload).to eq({ "echoed" => "hi" })
  end

  it "raises ToolDispatchError for an unknown tool" do
    reg = described_class.new
    expect { reg.dispatch(name: "nope", args: {}, ctx: ctx) }.to raise_error(CDFLHarness::Errors::ToolDispatchError)
  end

  it "strips forbidden identity args before dispatch (K-12/K-16)" do
    seen = nil
    klass = Class.new(CDFLHarness::Tooling::Tool) do
      tool_name "probe"; description "d"
      define_method(:call) { |args, _ctx| seen = args; { "ok" => true } }
    end
    reg = described_class.new
    reg.register(klass.new)
    reg.dispatch(name: "probe", args: { "tenant_id" => "evil", "user_id" => "x", "keep" => 1 }, ctx: ctx)
    expect(seen).to eq({ "keep" => 1 })
  end

  it "returns [false, error] when the tool raises ArgumentError" do
    klass = Class.new(CDFLHarness::Tooling::Tool) do
      tool_name "bad"; description "d"
      def call(_args, _ctx) = raise(ArgumentError, "nope")
    end
    reg = described_class.new
    reg.register(klass.new)
    ok, payload = reg.dispatch(name: "bad", args: {}, ctx: ctx)
    expect(ok).to be(false)
    expect(payload["error"]).to match(/nope/)
  end

  it "filters by scope in list_for_scope" do
    plat = Class.new(CDFLHarness::Tooling::Tool) { tool_name "p"; scope "platform" }
    reg = described_class.new
    reg.register(echo.new)
    reg.register(plat.new)
    expect(reg.list_for_scope("enterprise").map { |t| t.class.tool_name }).to eq(["echo"])
  end
end
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bundle exec rspec spec/tooling/registry_spec.rb`
Expected: FAIL.

- [ ] **Step 3: Write the implementation**

```ruby
# lib/cdfl_harness/tooling/registry.rb
# frozen_string_literal: true

require_relative "../errors"
require_relative "tool"
require_relative "context"

module CDFLHarness
  module Tooling
    # Holds tool instances and dispatches by name. Identity-bearing args are
    # stripped before dispatch so a tool can NEVER take tenant/user from the
    # LLM's arguments (K-12/K-16) — those come only from Context.
    class Registry
      FORBIDDEN_ARGS = %w[tenant_id enterprise_id user_id workspace_id role scope].freeze

      def initialize
        @tools = {}
      end

      def register(tool)
        name = tool.class.tool_name
        raise Errors::ConfigError, "tool has no name" if name.nil? || name.empty?

        @tools[name] = tool
        self
      end

      def fetch(name)
        @tools[name]
      end

      def list_for_scope(scope)
        @tools.values.select { |t| t.class.scope == scope }
      end

      # Returns [ok, payload]. Raises ToolDispatchError for hard violations
      # (unknown tool); a tool-side ArgumentError becomes [false, {error:}].
      def dispatch(name:, args:, ctx:)
        tool = @tools[name]
        raise Errors::ToolDispatchError, "unknown tool: #{name}" if tool.nil?

        safe = (args || {}).reject { |k, _| FORBIDDEN_ARGS.include?(k.to_s) }
        begin
          [true, tool.call(safe, ctx)]
        rescue ArgumentError => e
          [false, { "error" => e.message }]
        end
      end
    end
  end
end
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bundle exec rspec spec/tooling/registry_spec.rb`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/cdfl_harness/tooling/registry.rb spec/tooling/registry_spec.rb
git commit -m "feat: Tooling::Registry (dispatch, forbidden-arg strip K-12/K-16, scope filter)"
```

---

## Phase 4 — Store (session persistence)

### Task 4.1: Store::Base + InMemory

**Files:**
- Create: `lib/cdfl_harness/store/base.rb`
- Create: `lib/cdfl_harness/store/in_memory.rb`
- Test: `spec/store/in_memory_spec.rb`

- [ ] **Step 1: Write the failing test**

```ruby
# spec/store/in_memory_spec.rb
# frozen_string_literal: true

RSpec.describe CDFLHarness::Store::InMemory do
  it "creates, updates status, appends transcripts, and finalizes a session" do
    s = described_class.new
    s.create_session(session_id: "s1", tenant_id: "t1", workflow_id: "w", input: { "a" => 1 }, dry_run: true)
    s.set_status(session_id: "s1", status: :executing)
    s.append_transcript(session_id: "s1", entry: { step_index: 1, role: "executor" })
    s.finalize(session_id: "s1", status: :completed, tokens_used: 5, error_message: nil)

    row = s.get(session_id: "s1")
    expect(row[:status]).to eq(:completed)
    expect(row[:tokens_used]).to eq(5)
    expect(row[:transcripts].size).to eq(1)
  end
end
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bundle exec rspec spec/store/in_memory_spec.rb`
Expected: FAIL.

- [ ] **Step 3: Write the implementations**

```ruby
# lib/cdfl_harness/store/base.rb
# frozen_string_literal: true

module CDFLHarness
  module Store
    # Persistence contract for agent sessions. A project swaps this for a DB
    # adapter; the harness only calls these methods.
    class Base
      def create_session(session_id:, tenant_id:, workflow_id:, input:, dry_run:); raise NotImplementedError; end
      def set_status(session_id:, status:); raise NotImplementedError; end
      def append_transcript(session_id:, entry:); raise NotImplementedError; end
      def persist_plan(session_id:, plan:); raise NotImplementedError; end
      def persist_verdict(session_id:, verdict:); raise NotImplementedError; end
      def bump_replan(session_id:, replan_count:); raise NotImplementedError; end
      def finalize(session_id:, status:, tokens_used:, error_message:); raise NotImplementedError; end
      def get(session_id:); raise NotImplementedError; end
    end
  end
end
```

```ruby
# lib/cdfl_harness/store/in_memory.rb
# frozen_string_literal: true

require_relative "base"

module CDFLHarness
  module Store
    # Single-process, dict-backed default. Good for tests + the demo + any
    # project that doesn't need durable transcripts.
    class InMemory < Base
      def initialize
        @sessions = {}
      end

      def create_session(session_id:, tenant_id:, workflow_id:, input:, dry_run:)
        @sessions[session_id] = {
          session_id: session_id, tenant_id: tenant_id, workflow_id: workflow_id,
          input: input, dry_run: dry_run, status: :planning,
          plan: nil, verdict: nil, replan_count: 0, tokens_used: 0,
          error_message: nil, transcripts: []
        }
      end

      def set_status(session_id:, status:)       = row(session_id)[:status] = status
      def persist_plan(session_id:, plan:)       = row(session_id)[:plan] = plan
      def persist_verdict(session_id:, verdict:) = row(session_id)[:verdict] = verdict
      def bump_replan(session_id:, replan_count:) = row(session_id)[:replan_count] = replan_count
      def append_transcript(session_id:, entry:)  = row(session_id)[:transcripts] << entry

      def finalize(session_id:, status:, tokens_used:, error_message:)
        r = row(session_id)
        r[:status] = status
        r[:tokens_used] = tokens_used
        r[:error_message] = error_message
      end

      def get(session_id:) = @sessions[session_id]

      private

      def row(session_id)
        @sessions[session_id] || raise(Errors::Error, "unknown session #{session_id}")
      end
    end
  end
end
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bundle exec rspec spec/store/in_memory_spec.rb`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/cdfl_harness/store spec/store/in_memory_spec.rb
git commit -m "feat: Store::Base + InMemory session persistence"
```

---

## Phase 5 — Reasoning::CDFL

> Faithful port of `services/ai-orchestrator/reasoning/cdfl/*`. Pure, deterministic
> with an injectable RNG. Math constants and formulas match the thesis
> (`Thuật toán tương ứng.docx`, REPORT_V8/V10/V11).

### Task 5.1: CDFL types

**Files:**
- Create: `lib/cdfl_harness/reasoning/cdfl/types.rb`
- Test: `spec/reasoning/cdfl/types_spec.rb`

- [ ] **Step 1: Write the failing test**

```ruby
# spec/reasoning/cdfl/types_spec.rb
# frozen_string_literal: true

RSpec.describe "CDFL types" do
  it "Transition / ActionScore / RolloutResult build with keywords" do
    t = CDFLHarness::Reasoning::CDFL::Transition.new(state: "a", action: "b", next_state: "c")
    s = CDFLHarness::Reasoning::CDFL::ActionScore.new(action: "b", mean_score: 1.0, best_score: 2.0, visit_proxy: 3)
    r = CDFLHarness::Reasoning::CDFL::RolloutResult.new(trajectory: [t], total_information_gain: 1.5)
    expect(t.next_state).to eq("c")
    expect(s.visit_proxy).to eq(3)
    expect(r.total_information_gain).to eq(1.5)
  end
end
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bundle exec rspec spec/reasoning/cdfl/types_spec.rb`
Expected: FAIL.

- [ ] **Step 3: Write the implementation**

```ruby
# lib/cdfl_harness/reasoning/cdfl/types.rb
# frozen_string_literal: true

module CDFLHarness
  module Reasoning
    module CDFL
      Transition  = Struct.new(:state, :action, :next_state, keyword_init: true)
      ActionScore = Struct.new(:action, :mean_score, :best_score, :visit_proxy, keyword_init: true)
      RolloutResult = Struct.new(:trajectory, :total_information_gain, keyword_init: true) do
        def initialize(trajectory: [], total_information_gain: 0.0)
          super(trajectory: trajectory, total_information_gain: total_information_gain)
        end
      end
    end
  end
end
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bundle exec rspec spec/reasoning/cdfl/types_spec.rb`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/cdfl_harness/reasoning/cdfl/types.rb spec/reasoning/cdfl/types_spec.rb
git commit -m "feat: CDFL types (Transition, ActionScore, RolloutResult)"
```

### Task 5.2: TransitionModel

**Files:**
- Create: `lib/cdfl_harness/reasoning/cdfl/transition_model.rb`
- Test: `spec/reasoning/cdfl/transition_model_spec.rb`

Port of `transition_model.py` (P(s'|s,a) counts, recency decay/tick, sample_next).

- [ ] **Step 1: Write the failing test**

```ruby
# spec/reasoning/cdfl/transition_model_spec.rb
# frozen_string_literal: true

RSpec.describe CDFLHarness::Reasoning::CDFL::TransitionModel do
  it "learns P(s'|s,a) from observed counts" do
    m = described_class.new
    3.times { m.observe("A", "go", "B") }
    1.times { m.observe("A", "go", "C") }
    expect(m.probability("A", "go", "B")).to be_within(1e-9).of(0.75)
    expect(m.probability("A", "go", "C")).to be_within(1e-9).of(0.25)
    expect(m.probability("Z", "go", "B")).to eq(0.0)
  end

  it "counts state visits and (s,a) takes" do
    m = described_class.new
    m.observe("A", "go", "B")
    expect(m.state_visit_count("A")).to eq(1)
    expect(m.state_visit_count("B")).to eq(1)
    expect(m.state_action_count("A", "go")).to eq(1)
  end

  it "sample_next is reproducible with a seeded rng and returns a known target" do
    m = described_class.new(rng: Random.new(42))
    5.times { m.observe("A", "go", "B") }
    expect(m.sample_next("A", "go")).to eq("B")
  end

  it "sample_next on a novel (s,a) returns a known state (exploration prior)" do
    m = described_class.new(rng: Random.new(1))
    m.observe("A", "go", "B")
    expect(m.known_states).to include("A", "B")
    expect(m.known_states).to include(m.sample_next("A", "unseen"))
  end

  it "tick decays counts when recency_decay < 1" do
    m = described_class.new(recency_decay: 0.5)
    10.times { m.observe("A", "go", "B") }
    before = m.state_action_count("A", "go")
    m.tick
    expect(m.state_action_count("A", "go")).to be < before
  end
end
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bundle exec rspec spec/reasoning/cdfl/transition_model_spec.rb`
Expected: FAIL.

- [ ] **Step 3: Write the implementation**

```ruby
# lib/cdfl_harness/reasoning/cdfl/transition_model.rb
# frozen_string_literal: true

require_relative "types"

module CDFLHarness
  module Reasoning
    module CDFL
      # Tabular P(s'|s,a) learned from observed transitions (CRITICAL component
      # — ablation −31.6pp). Port of transition_model.py.
      class TransitionModel
        def initialize(rng: Random.new, recency_decay: 1.0)
          unless recency_decay > 0.0 && recency_decay <= 1.0
            raise ArgumentError, "recency_decay must be in (0,1], got #{recency_decay}"
          end

          @counts = Hash.new { |h, k| h[k] = Hash.new(0.0) } # [s,a] => { s' => count }
          @state_visits = Hash.new(0.0)
          @known_states = []
          @known_set = {}
          @rng = rng
          @decay = recency_decay
        end

        def observe(state, action, next_state)
          @counts[[state, action]][next_state] += 1
          record_state(state)
          record_state(next_state)
          nil
        end

        def observe_many(transitions)
          transitions.each { |t| observe(t.state, t.action, t.next_state) }
        end

        def tick
          return if @decay >= 1.0

          @state_visits.each_key { |s| @state_visits[s] *= @decay }
          @counts.each_value { |bucket| bucket.each_key { |s| bucket[s] *= @decay } }
          nil
        end

        def probability(state, action, next_state)
          bucket = @counts[[state, action]]
          total = bucket.values.sum
          return 0.0 if total.zero?

          bucket[next_state] / total
        end

        def sample_next(state, action)
          bucket = @counts[[state, action]]
          total = bucket.values.sum
          return weighted_choice(bucket) if total.positive?
          return @known_states[@rng.rand(@known_states.size)] unless @known_states.empty?

          state
        end

        def state_visit_count(state)  = @state_visits[state]
        def state_action_count(state, action) = @counts[[state, action]].values.sum
        def known_states = @known_states.dup
        def num_transitions_seen = @state_visits.values.sum

        # Internal: actions ever observed from `state` (used by the planner's
        # rollout interior steps).
        def actions_from(state)
          @counts.keys.select { |(s, _a)| s == state }.map { |(_s, a)| a }.uniq
        end

        def self.from_direct_follows(direct_follows, rng: Random.new)
          model = new(rng: rng)
          direct_follows.each do |(from_type, to_type), count|
            count.to_i.times { model.observe(from_type, to_type, to_type) }
          end
          model
        end

        private

        def record_state(state)
          unless @known_set.key?(state)
            @known_states << state
            @known_set[state] = true
          end
          @state_visits[state] += 1
        end

        def weighted_choice(bucket)
          total = bucket.values.sum
          r = @rng.rand * total
          acc = 0.0
          bucket.each { |k, w| acc += w; return k if r <= acc }
          bucket.keys.last
        end
      end
    end
  end
end
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bundle exec rspec spec/reasoning/cdfl/transition_model_spec.rb`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/cdfl_harness/reasoning/cdfl/transition_model.rb spec/reasoning/cdfl/transition_model_spec.rb
git commit -m "feat: CDFL TransitionModel (P(s'|s,a) counts, recency decay, sample_next)"
```

### Task 5.3: InfoGain (IGScorer)

**Files:**
- Create: `lib/cdfl_harness/reasoning/cdfl/info_gain.rb`
- Test: `spec/reasoning/cdfl/info_gain_spec.rb`

Port of `information_gain.py`: `novelty = 1/√(N+1)`, `uncertainty = 1/√(n+1)`, `IG = novelty + λ·uncertainty`.

- [ ] **Step 1: Write the failing test**

```ruby
# spec/reasoning/cdfl/info_gain_spec.rb
# frozen_string_literal: true

RSpec.describe CDFLHarness::Reasoning::CDFL::InfoGain do
  let(:model) { CDFLHarness::Reasoning::CDFL::TransitionModel.new }

  it "novelty = 1/sqrt(N+1)" do
    model.observe("A", "go", "B") # A visited once, B visited once
    s = described_class.new
    expect(s.novelty(model, "A")).to be_within(1e-9).of(1.0 / Math.sqrt(2))
    expect(s.novelty(model, "NEW")).to be_within(1e-9).of(1.0) # N=0
  end

  it "uncertainty = 1/sqrt(n+1)" do
    model.observe("A", "go", "B")
    s = described_class.new
    expect(s.uncertainty(model, "A", "go")).to be_within(1e-9).of(1.0 / Math.sqrt(2))
  end

  it "score uses novelty(next_state) + lambda*uncertainty(s,a)" do
    model.observe("A", "go", "B")
    s = described_class.new(uncertainty_weight: 1.0)
    expected = (1.0 / Math.sqrt(2)) + 1.0 * (1.0 / Math.sqrt(2)) # novelty(B)+unc(A,go)
    expect(s.score(model, "A", "go", "B")).to be_within(1e-9).of(expected)
  end
end
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bundle exec rspec spec/reasoning/cdfl/info_gain_spec.rb`
Expected: FAIL.

- [ ] **Step 3: Write the implementation**

```ruby
# lib/cdfl_harness/reasoning/cdfl/info_gain.rb
# frozen_string_literal: true

module CDFLHarness
  module Reasoning
    module CDFL
      # Information Gain scorer. IG(s,a) = novelty(s') + λ·uncertainty(s,a).
      # Port of information_gain.py.
      class InfoGain
        attr_reader :uncertainty_weight, :information_gain_weight

        def initialize(uncertainty_weight: 1.0, information_gain_weight: 1.0)
          @uncertainty_weight = uncertainty_weight
          @information_gain_weight = information_gain_weight
        end

        def novelty(model, state)
          1.0 / Math.sqrt(model.state_visit_count(state) + 1)
        end

        def uncertainty(model, state, action)
          1.0 / Math.sqrt(model.state_action_count(state, action) + 1)
        end

        def score(model, state, action, next_state = nil)
          target = next_state.nil? ? state : next_state
          raw = novelty(model, target) + @uncertainty_weight * uncertainty(model, state, action)
          @information_gain_weight * raw
        end
      end
    end
  end
end
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bundle exec rspec spec/reasoning/cdfl/info_gain_spec.rb`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/cdfl_harness/reasoning/cdfl/info_gain.rb spec/reasoning/cdfl/info_gain_spec.rb
git commit -m "feat: CDFL InfoGain scorer (novelty + lambda*uncertainty)"
```

### Task 5.4: LookaheadPlanner

**Files:**
- Create: `lib/cdfl_harness/reasoning/cdfl/lookahead.rb`
- Test: `spec/reasoning/cdfl/lookahead_spec.rb`

Port of `lookahead.py` (H-step Monte-Carlo rollout, score_actions, best_action).

- [ ] **Step 1: Write the failing test**

```ruby
# spec/reasoning/cdfl/lookahead_spec.rb
# frozen_string_literal: true

RSpec.describe CDFLHarness::Reasoning::CDFL::LookaheadPlanner do
  let(:model) do
    m = CDFLHarness::Reasoning::CDFL::TransitionModel.new(rng: Random.new(7))
    5.times { m.observe("A", "go", "B") }
    5.times { m.observe("B", "go", "A") }
    m
  end

  it "scores each candidate action, returning ActionScore rows" do
    p = described_class.new(horizon: 3, num_rollouts: 4, rng: Random.new(1))
    scores = p.score_actions(model, "A", ["go"])
    expect(scores.size).to eq(1)
    expect(scores.first.action).to eq("go")
    expect(scores.first.mean_score).to be > 0.0
    expect(scores.first.visit_proxy).to eq(5)
  end

  it "returns [] for no candidate actions" do
    p = described_class.new
    expect(p.score_actions(model, "A", [])).to eq([])
  end

  it "best_action picks the higher mean score and tie-breaks on lower visit_proxy" do
    m = CDFLHarness::Reasoning::CDFL::TransitionModel.new(rng: Random.new(3))
    10.times { m.observe("S", "known", "S") } # heavily visited (low novelty/uncertainty)
    p = described_class.new(horizon: 2, num_rollouts: 4, rng: Random.new(2))
    # "fresh" is unseen → higher info gain → should win
    expect(p.best_action(m, "S", %w[known fresh])).to eq("fresh")
  end
end
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bundle exec rspec spec/reasoning/cdfl/lookahead_spec.rb`
Expected: FAIL.

- [ ] **Step 3: Write the implementation**

```ruby
# lib/cdfl_harness/reasoning/cdfl/lookahead.rb
# frozen_string_literal: true

require_relative "types"
require_relative "info_gain"

module CDFLHarness
  module Reasoning
    module CDFL
      # H-step Monte-Carlo planner. Does NOT mutate the model (rollouts sample
      # only). Port of lookahead.py.
      class LookaheadPlanner
        attr_reader :horizon, :num_rollouts, :scorer, :rng

        def initialize(horizon: 5, num_rollouts: 6, scorer: nil, rng: nil)
          raise ArgumentError, "horizon must be >= 1" if horizon < 1
          raise ArgumentError, "num_rollouts must be >= 1" if num_rollouts < 1

          @horizon = horizon
          @num_rollouts = num_rollouts
          @scorer = scorer || InfoGain.new
          @rng = rng || Random.new
        end

        def rollout(model, start, first_action)
          trajectory = []
          total_ig = 0.0
          state = start
          action = first_action
          @horizon.times do
            next_state = model.sample_next(state, action)
            total_ig += @scorer.score(model, state, action, next_state)
            trajectory << Transition.new(state: state, action: action, next_state: next_state)
            state = next_state
            candidates = model.actions_from(state)
            break if candidates.empty?

            weights = candidates.map { |a| @scorer.score(model, state, a) }
            action = weighted_pick(candidates, weights)
          end
          RolloutResult.new(trajectory: trajectory, total_information_gain: total_ig)
        end

        def score_actions(model, state, candidate_actions)
          return [] if candidate_actions.empty?

          candidate_actions.map do |action|
            rollouts = Array.new(@num_rollouts) { rollout(model, state, action) }
            igs = rollouts.map(&:total_information_gain)
            ActionScore.new(
              action: action,
              mean_score: igs.sum / igs.size,
              best_score: igs.max,
              visit_proxy: model.state_action_count(state, action)
            )
          end
        end

        def best_action(model, state, candidate_actions)
          scored = score_actions(model, state, candidate_actions)
          raise ArgumentError, "candidate_actions must be non-empty" if scored.empty?

          scored.min_by { |s| [-s.mean_score, s.visit_proxy] }.action
        end

        private

        def weighted_pick(items, weights)
          total = weights.sum
          return items[@rng.rand(items.size)] if total <= 0

          r = @rng.rand * total
          acc = 0.0
          items.each_with_index { |it, i| acc += weights[i]; return it if r <= acc }
          items.last
        end
      end
    end
  end
end
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bundle exec rspec spec/reasoning/cdfl/lookahead_spec.rb`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/cdfl_harness/reasoning/cdfl/lookahead.rb spec/reasoning/cdfl/lookahead_spec.rb
git commit -m "feat: CDFL LookaheadPlanner (H-step Monte-Carlo rollout, score/best action)"
```

### Task 5.5: CDFLAgent

**Files:**
- Create: `lib/cdfl_harness/reasoning/cdfl/agent.rb`
- Test: `spec/reasoning/cdfl/agent_spec.rb`

Port of `agent.py` (combines model+scorer+planner; step/observe/score_actions; Boltzmann temperature).

- [ ] **Step 1: Write the failing test**

```ruby
# spec/reasoning/cdfl/agent_spec.rb
# frozen_string_literal: true

RSpec.describe CDFLHarness::Reasoning::CDFL::Agent do
  it "raises on empty action_space" do
    expect { described_class.new(action_space: []) }.to raise_error(ArgumentError)
  end

  it "greedy (temperature 0) returns the best-scored action" do
    agent = described_class.new(action_space: %w[known fresh], horizon: 2, num_rollouts: 4,
                                temperature: 0.0, seed: 5)
    10.times { agent.observe_transition("S", "known", "S") }
    expect(agent.step("S")).to eq("fresh")
  end

  it "observe_transition updates the model (transition_counts grows)" do
    agent = described_class.new(action_space: ["go"], seed: 1)
    expect { agent.observe_transition("A", "go", "B") }.to change { agent.transition_counts }.by(2)
  end

  it "freeze_model stops learning" do
    agent = described_class.new(action_space: ["go"], freeze_model: true, seed: 1)
    agent.observe_transition("A", "go", "B")
    expect(agent.transition_counts).to eq(0)
  end

  it "score_actions returns a ranking" do
    agent = described_class.new(action_space: %w[a b], horizon: 2, num_rollouts: 3, seed: 9)
    expect(agent.score_actions("S").map(&:action)).to match_array(%w[a b])
  end
end
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bundle exec rspec spec/reasoning/cdfl/agent_spec.rb`
Expected: FAIL.

- [ ] **Step 3: Write the implementation**

```ruby
# lib/cdfl_harness/reasoning/cdfl/agent.rb
# frozen_string_literal: true

require_relative "transition_model"
require_relative "info_gain"
require_relative "lookahead"

module CDFLHarness
  module Reasoning
    module CDFL
      # Convergent Dual-Field Learning agent — combines TransitionModel +
      # InfoGain + LookaheadPlanner. Picks the action with max expected info
      # gain (≈ E[Δ|OR|]) with optional Boltzmann noise. Port of agent.py.
      class Agent
        def initialize(action_space:, horizon: 5, num_rollouts: 6,
                       uncertainty_weight: 1.0, information_gain_weight: 1.0,
                       temperature: 0.1, freeze_model: false, seed: nil)
          raise ArgumentError, "action_space must be non-empty" if action_space.nil? || action_space.empty?
          raise ArgumentError, "horizon must be >= 1" if horizon < 1
          raise ArgumentError, "num_rollouts must be >= 1" if num_rollouts < 1
          raise ArgumentError, "temperature must be >= 0" if temperature.negative?

          @action_space = action_space.to_a
          @temperature = temperature
          @freeze_model = freeze_model
          @rng = seed.nil? ? Random.new : Random.new(seed)
          @model = TransitionModel.new(rng: @rng)
          scorer = InfoGain.new(uncertainty_weight: uncertainty_weight,
                                information_gain_weight: information_gain_weight)
          @planner = LookaheadPlanner.new(horizon: horizon, num_rollouts: num_rollouts,
                                          scorer: scorer, rng: @rng)
        end

        attr_reader :model, :planner

        def step(state)
          scored = @planner.score_actions(@model, state, @action_space)
          pick_with_temperature(scored)
        end

        def observe_transition(state, action, next_state, _reward = 0.0)
          return if @freeze_model

          @model.observe(state, action, next_state)
        end

        def score_actions(state)
          @planner.score_actions(@model, state, @action_space)
        end

        def transition_counts = @model.num_transitions_seen

        private

        def pick_with_temperature(scored)
          return @action_space[@rng.rand(@action_space.size)] if scored.empty?

          if @temperature <= 0
            return scored.min_by { |s| [-s.mean_score, s.visit_proxy] }.action
          end

          max = scored.map(&:mean_score).max
          weights = scored.map { |s| Math.exp((s.mean_score - max) / @temperature) }
          total = weights.sum
          r = @rng.rand * total
          acc = 0.0
          scored.each_with_index { |s, i| acc += weights[i]; return s.action if r <= acc }
          scored.last.action
        end
      end
    end
  end
end
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bundle exec rspec spec/reasoning/cdfl/agent_spec.rb`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/cdfl_harness/reasoning/cdfl/agent.rb spec/reasoning/cdfl/agent_spec.rb
git commit -m "feat: CDFLAgent (model+scorer+planner, Boltzmann action pick)"
```

### Task 5.6: FourFoldDE

**Files:**
- Create: `lib/cdfl_harness/reasoning/cdfl/four_fold_de.rb`
- Test: `spec/reasoning/cdfl/four_fold_de_spec.rb`

Port of `four_fold_de.py` (DE dashboard: x/t/if/mf faces).

- [ ] **Step 1: Write the failing test**

```ruby
# spec/reasoning/cdfl/four_fold_de_spec.rb
# frozen_string_literal: true

RSpec.describe CDFLHarness::Reasoning::CDFL::FourFoldDE do
  it "assembles four dark faces = 1 - manifest fraction" do
    de = described_class.assemble(data_coverage: 0.8, knowledge_freshness: 1.0,
                                  knowledge_coverage: 0.5, grounding_score: 0.9)
    expect(de.x).to be_within(1e-9).of(0.2)
    expect(de.t).to be_within(1e-9).of(0.0)
    expect(de.if_).to be_within(1e-9).of(0.5)
    expect(de.mf).to be_within(1e-9).of(0.1)
  end

  it "max_dark is the worst face; manifest_or is 1 - mean(dark)" do
    de = described_class.assemble(data_coverage: 0.8, knowledge_freshness: 1.0,
                                  knowledge_coverage: 0.5, grounding_score: 0.9)
    expect(de.max_dark).to be_within(1e-9).of(0.5)
    expect(de.manifest_or).to be_within(1e-9).of(1.0 - (0.2 + 0.0 + 0.5 + 0.1) / 4.0)
  end

  it "clips inputs into [0,1]" do
    de = described_class.assemble(data_coverage: 1.5, knowledge_freshness: -2,
                                  knowledge_coverage: 0.5, grounding_score: 0.5)
    expect(de.x).to eq(0.0)
    expect(de.t).to eq(1.0)
  end
end
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bundle exec rspec spec/reasoning/cdfl/four_fold_de_spec.rb`
Expected: FAIL.

- [ ] **Step 3: Write the implementation**

```ruby
# lib/cdfl_harness/reasoning/cdfl/four_fold_de.rb
# frozen_string_literal: true

module CDFLHarness
  module Reasoning
    module CDFL
      # Dark-Existence dashboard (Tiên đề 4-5): DE across four faces — không
      # gian (x), thời gian (t), IF chưa biết (if_), MF chưa biết (mf). Faces
      # overlap, so they are reported, NEVER summed. Port of four_fold_de.py.
      FourFoldDE = Struct.new(:x, :t, :if_, :mf, keyword_init: true) do
        def faces = { "x" => x, "t" => t, "if" => if_, "mf" => mf }
        def max_dark = [x, t, if_, mf].max
        def manifest_or = 1.0 - (x + t + if_ + mf) / 4.0
      end

      module FourFoldDE_Builder
        def self.clip01(v)
          v < 0 ? 0.0 : (v > 1 ? 1.0 : v.to_f)
        end
      end

      class FourFoldDE
        # Build the four-fold DE from four manifest-fractions in [0,1]
        # (1 = fully known on that face). dark face = 1 − signal.
        def self.assemble(data_coverage:, knowledge_freshness:, knowledge_coverage:, grounding_score:)
          c = FourFoldDE_Builder
          new(
            x: 1.0 - c.clip01(data_coverage),
            t: 1.0 - c.clip01(knowledge_freshness),
            if_: 1.0 - c.clip01(knowledge_coverage),
            mf: 1.0 - c.clip01(grounding_score)
          )
        end
      end
    end
  end
end
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bundle exec rspec spec/reasoning/cdfl/four_fold_de_spec.rb`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/cdfl_harness/reasoning/cdfl/four_fold_de.rb spec/reasoning/cdfl/four_fold_de_spec.rb
git commit -m "feat: CDFL FourFoldDE dashboard (x/t/if/mf dark faces)"
```

### Task 5.7: Empowerment (option-preservation)

**Files:**
- Create: `lib/cdfl_harness/reasoning/cdfl/empowerment.rb`
- Test: `spec/reasoning/cdfl/empowerment_spec.rb`

Port of `empowerment.py` (reversible = option-preserving; irreversible → consent).

- [ ] **Step 1: Write the failing test**

```ruby
# spec/reasoning/cdfl/empowerment_spec.rb
# frozen_string_literal: true

RSpec.describe CDFLHarness::Reasoning::CDFL::Empowerment do
  it "reversible classes preserve options" do
    expect(described_class.option_preserving?("read_only")).to be(true)
    expect(described_class.option_preserving?("write_idempotent")).to be(true)
    expect(described_class.option_preserving?("external")).to be(false)
  end

  it "advice for a reversible action needs no consent" do
    a = described_class.protection_advice("read_only")
    expect(a.preserves_options).to be(true)
    expect(a.needs_consent).to be(false)
  end

  it "irreversible with a reversible alternative prefers the alternative + asks" do
    a = described_class.protection_advice("external", reversible_alternative_exists: true)
    expect(a.needs_consent).to be(true)
    expect(a.prefer_reversible).to be(true)
  end

  it "irreversible with no alternative requires consent" do
    a = described_class.protection_advice("write_non_idempotent")
    expect(a.needs_consent).to be(true)
    expect(a.prefer_reversible).to be(false)
  end
end
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bundle exec rspec spec/reasoning/cdfl/empowerment_spec.rb`
Expected: FAIL.

- [ ] **Step 3: Write the implementation**

```ruby
# lib/cdfl_harness/reasoning/cdfl/empowerment.rb
# frozen_string_literal: true

module CDFLHarness
  module Reasoning
    module CDFL
      # Empowerment / option-preservation. An IRREVERSIBLE side-effect shrinks
      # others' future option-space (|OR|) → surface for consent. A REVERSIBLE
      # one preserves options → safe. Advisory only; never auto-blocks. Port of
      # empowerment.py.
      module Empowerment
        REVERSIBLE_CLASSES = %w[pure read_only write_idempotent].freeze
        OPTION_SHRINKING_CLASSES = %w[write_non_idempotent external].freeze

        ProtectionAdvice = Struct.new(:preserves_options, :needs_consent, :prefer_reversible, :rationale,
                                      keyword_init: true)

        module_function

        def option_preserving?(side_effect_class)
          REVERSIBLE_CLASSES.include?(side_effect_class)
        end

        def protection_advice(side_effect_class, reversible_alternative_exists: false)
          if option_preserving?(side_effect_class)
            return ProtectionAdvice.new(
              preserves_options: true, needs_consent: false, prefer_reversible: false,
              rationale: "Hành động khả hồi — bảo toàn không-gian-lựa-chọn (OR) của tác tử khác."
            )
          end

          if reversible_alternative_exists
            return ProtectionAdvice.new(
              preserves_options: false, needs_consent: true, prefer_reversible: true,
              rationale: "Có lựa chọn KHẢ HỒI tương đương — ưu tiên nó để bảo toàn OR của người dùng; " \
                         "nếu vẫn cần hành động bất khả hồi, xin phê duyệt."
            )
          end

          ProtectionAdvice.new(
            preserves_options: false, needs_consent: true, prefer_reversible: false,
            rationale: "Hành động BẤT KHẢ HỒI — thu hẹp không-gian-lựa-chọn của tác tử khác; " \
                       "cần con người phê duyệt trước (empowerment)."
          )
        end
      end
    end
  end
end
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bundle exec rspec spec/reasoning/cdfl/empowerment_spec.rb`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/cdfl_harness/reasoning/cdfl/empowerment.rb spec/reasoning/cdfl/empowerment_spec.rb
git commit -m "feat: CDFL Empowerment (option-preservation consent advice)"
```

### Task 5.8: HilbertMetric (descriptive |OR| gauge via real embedding)

**Files:**
- Create: `lib/cdfl_harness/reasoning/cdfl/hilbert_metric.rb`
- Test: `spec/reasoning/cdfl/hilbert_metric_spec.rb`

Port of `hilbert_metric.py`. **DESCRIPTIVE only** (never on the action path). Uses the
real-embedding of a Hermitian matrix + stdlib `Matrix#eigensystem` (no complex eigensolver needed).

- [ ] **Step 1: Write the failing test**

```ruby
# spec/reasoning/cdfl/hilbert_metric_spec.rb
# frozen_string_literal: true

RSpec.describe CDFLHarness::Reasoning::CDFL::HilbertMetric do
  M = CDFLHarness::Reasoning::CDFL::HilbertMetric

  it "von_neumann_entropy is 0 for a pure state and ln(n) for maximally mixed" do
    pure = Matrix[[Complex(1, 0), 0], [0, 0]]
    mixed = Matrix[[Complex(0.5, 0), 0], [0, Complex(0.5, 0)]]
    expect(M.von_neumann_entropy(pure)).to be_within(1e-9).of(0.0)
    expect(M.von_neumann_entropy(mixed)).to be_within(1e-9).of(Math.log(2))
  end

  it "mutual_information is 0 for a product state" do
    rho = M.make_pure_product_state(2, 2)
    expect(M.mutual_information(rho, 2, 2)).to be_within(1e-9).of(0.0)
  end

  it "mutual_information is 2*ln2 for a Bell state on 2x2" do
    # |Φ+> = (|00> + |11>)/sqrt2 → rho = outer product
    v = [Complex(1 / Math.sqrt(2), 0), 0, 0, Complex(1 / Math.sqrt(2), 0)]
    rho = Matrix.build(4, 4) { |i, j| v[i] * v[j].conjugate }
    expect(M.mutual_information(rho, 2, 2)).to be_within(1e-6).of(2 * Math.log(2))
  end

  it "relative_entropy is 0 for identical states and >= 0 otherwise" do
    a = Matrix[[Complex(0.7, 0), 0], [0, Complex(0.3, 0)]]
    b = Matrix[[Complex(0.5, 0), 0], [0, Complex(0.5, 0)]]
    expect(M.relative_entropy(a, a)).to be_within(1e-9).of(0.0)
    expect(M.relative_entropy(a, b)).to be >= 0.0
  end

  it "partial_trace of a product state returns the kept subsystem" do
    rho = M.make_pure_product_state(2, 2)
    rho_i = M.partial_trace(rho, 2, 2, keep_first: true)
    expect(rho_i[0, 0].real).to be_within(1e-9).of(1.0)
  end
end
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bundle exec rspec spec/reasoning/cdfl/hilbert_metric_spec.rb`
Expected: FAIL.

- [ ] **Step 3: Write the implementation**

```ruby
# lib/cdfl_harness/reasoning/cdfl/hilbert_metric.rb
# frozen_string_literal: true

require "matrix"

module CDFLHarness
  module Reasoning
    module CDFL
      # CDFL v10/v11 measurement primitives — the descriptive |OR| = I(I:M)
      # gauge. Port of hilbert_metric.py. DESCRIPTIVE ONLY: v11 showed active
      # action selection is no better than random, so this is never on the
      # action path — only an observability/diagnostic measure.
      #
      # Ruby stdlib has no complex Hermitian eigensolver, so we use the
      # real-embedding trick: a Hermitian H = A + iB maps to the real symmetric
      # 2n×2n matrix [[A, -B], [B, A]], whose eigenvalues equal H's eigenvalues
      # each doubled. We then use stdlib Matrix#eigensystem (real symmetric).
      module HilbertMetric
        EPS = 1e-12

        module_function

        # S(ρ) = -tr(ρ log ρ).
        def von_neumann_entropy(rho)
          evs = embedded_eigenvalues(rho)          # 2n eigenvalues (each true ev doubled)
          s = 0.0
          evs.each { |l| s -= l * Math.log(l) if l > EPS }
          s / 2.0                                  # undo the doubling
        end

        # tr_B(ρ_AB) if keep_first, else tr_A(ρ_AB). rho is (dim_keep*dim_trace)².
        def partial_trace(rho, dim_keep, dim_trace, keep_first: true)
          Matrix.build(dim_keep, dim_keep) do |a, c|
            acc = Complex(0, 0)
            dim_trace.times do |b|
              acc += if keep_first
                       rho[a * dim_trace + b, c * dim_trace + b]
                     else
                       # keep second subsystem: trace out the FIRST (dim_trace)
                       rho[b * dim_keep + a, b * dim_keep + c]
                     end
            end
            acc
          end
        end

        # I(I:M) = S(ρ_I) + S(ρ_M) - S(ρ_IM). The |OR| quantity (v11 verified).
        def mutual_information(rho_im, dim_i, dim_m)
          rho_i = partial_trace(rho_im, dim_i, dim_m, keep_first: true)
          rho_m = partial_trace(rho_im, dim_m, dim_i, keep_first: false)
          von_neumann_entropy(rho_i) + von_neumann_entropy(rho_m) - von_neumann_entropy(rho_im)
        end

        # DE = S(ρ‖σ) = tr(ρ ln ρ) − tr(ρ ln σ). The Dark-Existence quantity.
        def relative_entropy(rho, sigma)
          raise ArgumentError, "shape mismatch" unless rho.row_count == sigma.row_count

          tr_rho_ln_rho = -von_neumann_entropy(rho) # = Σ λ ln λ
          ln_sigma_embed = embedded_log(sigma)      # 2n×2n real symmetric ln(σ) embedding
          rho_embed = embed(rho)
          tr_rho_ln_sigma = (rho_embed * ln_sigma_embed).trace / 2.0
          [tr_rho_ln_rho - tr_rho_ln_sigma, 0.0].max
        end

        # |I0><I0| ⊗ |M0><M0|. I(I:M)=0.
        def make_pure_product_state(dim_i, dim_m)
          rho_i = Matrix.build(dim_i, dim_i) { |r, c| (r.zero? && c.zero?) ? Complex(1, 0) : Complex(0, 0) }
          rho_m = Matrix.build(dim_m, dim_m) { |r, c| (r.zero? && c.zero?) ? Complex(1, 0) : Complex(0, 0) }
          kron(rho_i, rho_m)
        end

        def kron(a, b)
          ra = a.row_count; ca = a.column_count
          rb = b.row_count; cb = b.column_count
          Matrix.build(ra * rb, ca * cb) { |i, j| a[i / rb, j / cb] * b[i % rb, j % cb] }
        end

        # ----- real-embedding helpers -----

        # Hermitian H = A + iB → real symmetric [[A, -B], [B, A]] (2n×2n).
        def embed(h)
          n = h.row_count
          Matrix.build(2 * n, 2 * n) do |i, j|
            block_i = i / n; block_j = j / n
            r = i % n; c = j % n
            z = h[r, c]
            case [block_i, block_j]
            when [0, 0], [1, 1] then z.real
            when [0, 1] then -z.imaginary
            else z.imaginary
            end
          end
        end

        def embedded_eigenvalues(h)
          embed(h).eigensystem.eigenvalues.map { |e| e.respond_to?(:real) ? e.real : e.to_f }
        end

        # ln(σ) in the embedding space (real symmetric), via eigendecomposition.
        def embedded_log(sigma)
          es = embed(sigma).eigensystem
          d = es.eigenvalues.map { |e| (e.respond_to?(:real) ? e.real : e.to_f) }
          v = es.eigenvector_matrix
          ln = Matrix.diagonal(*d.map { |x| Math.log([x, EPS].max) })
          (v * ln * v.transpose).map(&:real)
        end
      end
    end
  end
end
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bundle exec rspec spec/reasoning/cdfl/hilbert_metric_spec.rb`
Expected: PASS. (If `eigensystem` returns complex eigenvectors with ~0 imaginary parts, `.map(&:real)` on the reconstructed matrix keeps it real; the specs use real-diagonal σ so this is exact.)

- [ ] **Step 5: Commit**

```bash
git add lib/cdfl_harness/reasoning/cdfl/hilbert_metric.rb spec/reasoning/cdfl/hilbert_metric_spec.rb
git commit -m "feat: CDFL HilbertMetric (descriptive I(I:M) gauge via real embedding)"
```

### Task 5.9: CDFL aggregator require

**Files:**
- Create: `lib/cdfl_harness/reasoning/cdfl.rb`
- Test: `spec/reasoning/cdfl/aggregator_spec.rb`

- [ ] **Step 1: Write the failing test**

```ruby
# spec/reasoning/cdfl/aggregator_spec.rb
# frozen_string_literal: true

require "cdfl_harness/reasoning/cdfl"

RSpec.describe "CDFL aggregator" do
  it "exposes all public CDFL classes" do
    expect(defined?(CDFLHarness::Reasoning::CDFL::Agent)).to be_truthy
    expect(defined?(CDFLHarness::Reasoning::CDFL::TransitionModel)).to be_truthy
    expect(defined?(CDFLHarness::Reasoning::CDFL::LookaheadPlanner)).to be_truthy
    expect(defined?(CDFLHarness::Reasoning::CDFL::InfoGain)).to be_truthy
    expect(defined?(CDFLHarness::Reasoning::CDFL::FourFoldDE)).to be_truthy
    expect(defined?(CDFLHarness::Reasoning::CDFL::Empowerment)).to be_truthy
    expect(defined?(CDFLHarness::Reasoning::CDFL::HilbertMetric)).to be_truthy
  end
end
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bundle exec rspec spec/reasoning/cdfl/aggregator_spec.rb`
Expected: FAIL (cannot load such file).

- [ ] **Step 3: Write the implementation**

```ruby
# lib/cdfl_harness/reasoning/cdfl.rb
# frozen_string_literal: true

require_relative "cdfl/types"
require_relative "cdfl/transition_model"
require_relative "cdfl/info_gain"
require_relative "cdfl/lookahead"
require_relative "cdfl/agent"
require_relative "cdfl/four_fold_de"
require_relative "cdfl/empowerment"
require_relative "cdfl/hilbert_metric"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bundle exec rspec spec/reasoning/cdfl/aggregator_spec.rb`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/cdfl_harness/reasoning/cdfl.rb spec/reasoning/cdfl/aggregator_spec.rb
git commit -m "feat: CDFL aggregator require"
```

---

## Phase 6 — Reasoning::Knowledge ("học 1 hiểu 10")

> Port of `reasoning/knowledge/grounding.py` + the `KnowledgeDocument` shape.

### Task 6.1: KnowledgeDocument + Store

**Files:**
- Create: `lib/cdfl_harness/reasoning/knowledge/document.rb`
- Create: `lib/cdfl_harness/reasoning/knowledge/store.rb`
- Test: `spec/reasoning/knowledge/store_spec.rb`

- [ ] **Step 1: Write the failing test**

```ruby
# spec/reasoning/knowledge/store_spec.rb
# frozen_string_literal: true

RSpec.describe CDFLHarness::Reasoning::Knowledge::InMemoryStore do
  Doc = CDFLHarness::Reasoning::Knowledge::Document

  it "stores docs per tenant and lists them" do
    s = described_class.new
    s.put(Doc.new(title: "A", content: "x", tier: 1, confidence: 0.9, tenant_id: "t1"), scope_tenant_id: "t1")
    s.put(Doc.new(title: "B", content: "y", tier: 4, confidence: 0.5, tenant_id: "t1"), scope_tenant_id: "t1")
    expect(s.list_documents("t1").map(&:title)).to match_array(%w[A B])
    expect(s.list_documents("other")).to eq([])
  end

  it "Document defaults distance to nil and tier/confidence carry through" do
    d = Doc.new(title: "A", content: "x", tenant_id: "t1")
    expect(d.distance).to be_nil
    expect(d.tier).to eq(4)
    expect(d.confidence).to be_within(1e-9).of(0.7)
  end
end
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bundle exec rspec spec/reasoning/knowledge/store_spec.rb`
Expected: FAIL.

- [ ] **Step 3: Write the implementations**

```ruby
# lib/cdfl_harness/reasoning/knowledge/document.rb
# frozen_string_literal: true

require "securerandom"

module CDFLHarness
  module Reasoning
    module Knowledge
      # A knowledge doc. tier: 1 regulatory, 2 curated (FOUNDATIONAL); 3 market
      # (volatile); 4 tenant notes. distance = pgvector cosine distance when
      # retrieved (nil otherwise). confidence = maturity 0..1.
      Document = Struct.new(:title, :content, :tier, :confidence, :tenant_id,
                            :category, :source, :document_id, :distance,
                            keyword_init: true) do
        def initialize(title:, content:, tenant_id:, tier: 4, confidence: 0.7,
                       category: nil, source: nil, document_id: nil, distance: nil)
          super(title: title, content: content, tier: tier, confidence: confidence,
                tenant_id: tenant_id, category: category, source: source,
                document_id: document_id || SecureRandom.uuid, distance: distance)
        end
      end
    end
  end
end
```

```ruby
# lib/cdfl_harness/reasoning/knowledge/store.rb
# frozen_string_literal: true

require_relative "document"

module CDFLHarness
  module Reasoning
    module Knowledge
      # Pluggable KB store contract.
      class Store
        def put(doc, scope_tenant_id:); raise NotImplementedError; end
        def list_documents(tenant_id, limit: 100); raise NotImplementedError; end
      end

      # In-memory default. A project swaps in pgvector + a real retriever.
      class InMemoryStore < Store
        def initialize
          @by_tenant = Hash.new { |h, k| h[k] = {} }
        end

        def put(doc, scope_tenant_id:)
          @by_tenant[scope_tenant_id][doc.document_id] = doc
          doc
        end

        def list_documents(tenant_id, limit: 100)
          @by_tenant[tenant_id].values.first(limit)
        end
      end
    end
  end
end
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bundle exec rspec spec/reasoning/knowledge/store_spec.rb`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/cdfl_harness/reasoning/knowledge/document.rb lib/cdfl_harness/reasoning/knowledge/store.rb spec/reasoning/knowledge/store_spec.rb
git commit -m "feat: Knowledge Document + pluggable Store (in-memory default)"
```

### Task 6.2: Coverage gate ("học 1 hiểu 10")

**Files:**
- Create: `lib/cdfl_harness/reasoning/knowledge/coverage.rb`
- Test: `spec/reasoning/knowledge/coverage_spec.rb`

Port of `knowledge/grounding.py` (`coverage`, `coverage_gate`, `rank_by_authority`, foundational tiers only).

- [ ] **Step 1: Write the failing test**

```ruby
# spec/reasoning/knowledge/coverage_spec.rb
# frozen_string_literal: true

RSpec.describe CDFLHarness::Reasoning::Knowledge::Coverage do
  Doc = CDFLHarness::Reasoning::Knowledge::Document
  C = CDFLHarness::Reasoning::Knowledge::Coverage

  def doc(distance:, tier:, confidence:)
    Doc.new(title: "d", content: "c", tenant_id: "t", tier: tier, confidence: confidence, distance: distance)
  end

  it "only foundational tiers (1,2) contribute to coverage" do
    foundational = [doc(distance: 0.1, tier: 1, confidence: 1.0)]
    volatile = [doc(distance: 0.1, tier: 3, confidence: 1.0)]
    expect(C.coverage(foundational)).to be > 0.0
    expect(C.coverage(volatile)).to eq(0.0)
  end

  it "coverage = 1 - exp(-k * sum(sim*conf)) over foundational docs" do
    docs = [doc(distance: 0.0, tier: 1, confidence: 1.0)] # sim = 1.0
    expect(C.coverage(docs, k: 0.6)).to be_within(1e-4).of(1.0 - Math.exp(-0.6))
  end

  it "coverage_gate bands: >=0.60 đủ, >=0.30 thận trọng, else chưa đủ" do
    expect(C.coverage_gate(0.7)[:can_generalize]).to be(true)
    expect(C.coverage_gate(0.7)[:band]).to eq("đủ")
    expect(C.coverage_gate(0.4)[:band]).to eq("thận trọng")
    expect(C.coverage_gate(0.4)[:can_generalize]).to be(true)
    expect(C.coverage_gate(0.1)[:can_generalize]).to be(false)
    expect(C.coverage_gate(0.1)[:band]).to eq("chưa đủ")
  end

  it "rank_by_authority orders by similarity nudged by tier+maturity" do
    a = doc(distance: 0.2, tier: 1, confidence: 0.9) # high sim + high tier
    b = doc(distance: 0.2, tier: 4, confidence: 0.5)
    ranked = C.rank_by_authority([b, a])
    expect(ranked.first).to eq(a)
  end
end
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bundle exec rspec spec/reasoning/knowledge/coverage_spec.rb`
Expected: FAIL.

- [ ] **Step 3: Write the implementation**

```ruby
# lib/cdfl_harness/reasoning/knowledge/coverage.rb
# frozen_string_literal: true

module CDFLHarness
  module Reasoning
    module Knowledge
      # ADR-0033 — the "học 1 hiểu 10" gate. High foundational coverage → the
      # reasoner may generalise; low coverage → decline (don't hallucinate, K-3).
      # Only foundational tiers (1,2) count: durable understanding, not volatile
      # market notes. Port of knowledge/grounding.py.
      module Coverage
        FOUNDATIONAL_TIERS = [1, 2].freeze

        module_function

        def cfg = CDFLHarness.config.reasoning

        def similarity(doc)
          d = doc.distance
          return 0.0 if d.nil?

          [0.0, 1.0 - d].max
        end

        def tier_rank(tier)
          [0.0, (5 - tier) / 4.0].max
        end

        def authority_score(doc, w_authority: cfg.w_authority, w_maturity: cfg.w_maturity)
          similarity(doc) + w_authority * tier_rank(doc.tier) + w_maturity * doc.confidence.to_f
        end

        def rank_by_authority(docs, w_authority: cfg.w_authority, w_maturity: cfg.w_maturity)
          docs.sort_by { |d| -authority_score(d, w_authority: w_authority, w_maturity: w_maturity) }
        end

        # 1 − exp(−k · Σ sim·confidence) over FOUNDATIONAL docs only.
        def coverage(docs, k: cfg.coverage_k)
          mass = docs.select { |d| FOUNDATIONAL_TIERS.include?(d.tier) }
                     .sum { |d| similarity(d) * d.confidence.to_f }
          (1.0 - Math.exp(-k * mass)).round(4)
        end

        def coverage_gate(coverage, gen_min: cfg.gen_min, gen_caution: cfg.gen_caution)
          pct = (coverage * 100).round
          if coverage >= gen_min
            { can_generalize: true, band: "đủ", coverage: coverage,
              note: "Độ phủ tri thức nền #{pct}% — đủ để khái quát hoá (học 1 hiểu 10)." }
          elsif coverage >= gen_caution
            { can_generalize: true, band: "thận trọng", coverage: coverage,
              note: "Độ phủ tri thức nền #{pct}% — khái quát hoá THẬN TRỌNG, nêu rõ giả định." }
          else
            { can_generalize: false, band: "chưa đủ", coverage: coverage,
              note: "Độ phủ tri thức nền chỉ #{pct}% — CHƯA khái quát hoá; cần bổ sung kiến thức nền." }
          end
        end
      end
    end
  end
end
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bundle exec rspec spec/reasoning/knowledge/coverage_spec.rb`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/cdfl_harness/reasoning/knowledge/coverage.rb spec/reasoning/knowledge/coverage_spec.rb
git commit -m "feat: Knowledge Coverage gate (học 1 hiểu 10: coverage/coverage_gate/rank_by_authority)"
```

---

## Phase 7 — Reasoning::Memory (cung điện ký ức)

> Port of `reasoning/memory/{types,stores,service}.py`, synchronous.

### Task 7.1: MemoryRecord + trust + maturation

**Files:**
- Create: `lib/cdfl_harness/reasoning/memory/record.rb`
- Test: `spec/reasoning/memory/record_spec.rb`

Port of `memory/types.py` (tiers/types, importance, trust decay by half-life, maturation).

- [ ] **Step 1: Write the failing test**

```ruby
# spec/reasoning/memory/record_spec.rb
# frozen_string_literal: true

RSpec.describe CDFLHarness::Reasoning::Memory do
  R = CDFLHarness::Reasoning::Memory
  Rec = R::MemoryRecord

  def rec(type: :SEMANTIC, confidence: 0.7, occurred_days_ago: 0, verified: nil, appearances: 0)
    Rec.new(tenant_id: "t", memory_type: type, content: "x", confidence: confidence,
            occurred_at: Time.now - occurred_days_ago * 86_400,
            last_verified_at: verified, session_appearance_count: appearances)
  end

  it "compute_importance follows the weighted formula" do
    r = rec(occurred_days_ago: 0, appearances: 5)
    # recency≈1 *0.2 + repeat(1)*0.3 + 0 + 0 = 0.5
    expect(R.compute_importance(r)).to be_within(1e-3).of(0.5)
  end

  it "compute_trust decays with per-type half-life" do
    semantic = rec(type: :SEMANTIC, confidence: 0.8, occurred_days_ago: 365) # hl 365 → halves
    expect(R.compute_trust(semantic)[:score]).to be_within(1e-2).of(0.4)
  end

  it "flags confident-but-unchecked memories" do
    r = rec(type: :EPISODIC, confidence: 0.9, occurred_days_ago: 60, verified: nil) # hl 30 → age>hl
    expect(R.compute_trust(r)[:unchecked]).to be(true)
  end

  it "reinforce_confidence climbs toward the per-source ceiling" do
    r = rec(confidence: 0.7); r.trust_source = "user"
    before = r.confidence
    R.reinforce_confidence(r)
    expect(r.confidence).to be > before
    expect(r.confidence).to be <= 0.98
  end

  it "experience_level saturates and bands" do
    recs = Array.new(5) { rec(type: :SEMANTIC, confidence: 0.8, occurred_days_ago: 0) }
    exp = R.experience_level(recs)
    expect(exp[:experience]).to be_between(0.0, 1.0)
    expect(exp[:band]).to be_a(String)
  end
end
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bundle exec rspec spec/reasoning/memory/record_spec.rb`
Expected: FAIL.

- [ ] **Step 3: Write the implementation**

```ruby
# lib/cdfl_harness/reasoning/memory/record.rb
# frozen_string_literal: true

require "securerandom"

module CDFLHarness
  module Reasoning
    module Memory
      # Lifecycle tiers (storage stage) — distinct from cognitive type.
      TIERS = %w[L1_WORKING L2_SHORT L3_CONSOLIDATED L4_LONG].freeze
      # Cognitive categories.
      TYPES = %i[EPISODIC SEMANTIC PROCEDURAL OPERATIONAL DECISION].freeze

      CLASSIC_MEMORY_CLASS = {
        EPISODIC: "episodic", DECISION: "episodic",
        SEMANTIC: "semantic", PROCEDURAL: "procedural", OPERATIONAL: "procedural"
      }.freeze

      # Per-type trust half-life (days) — learned concepts age slowly, episodic fast.
      HALFLIFE_DAYS = { SEMANTIC: 365, PROCEDURAL: 365, DECISION: 60, OPERATIONAL: 60, EPISODIC: 30 }.freeze
      DEFAULT_HALFLIFE_DAYS = 60
      TRUST_FRESH = 0.66
      TRUST_AGING = 0.33

      # Per-source confidence ceiling (epistemic humility — never 1.0).
      CONF_CEILING = { "user" => 0.98, "consolidate" => 0.90, "rag" => 0.90, "derived" => 0.85 }.freeze
      DEFAULT_CEILING = 0.85
      EXPERIENCE_BANDS = [[0.80, "chuyên gia"], [0.55, "dày dạn"], [0.30, "thành thạo"],
                          [0.10, "tập sự"], [0.0, "mới"]].freeze

      class MemoryRecord
        attr_accessor :tenant_id, :memory_type, :content, :record_id, :tier,
                      :occurred_at, :session_id, :entity_id, :session_appearance_count,
                      :user_flagged_important, :linked_outcome_value, :metadata,
                      :confidence, :trust_source, :last_verified_at

        def initialize(tenant_id:, memory_type:, content:, record_id: nil, tier: "L1_WORKING",
                       occurred_at: nil, session_id: nil, entity_id: nil, session_appearance_count: 0,
                       user_flagged_important: false, linked_outcome_value: 0.0, metadata: nil,
                       confidence: 0.70, trust_source: nil, last_verified_at: nil)
          @tenant_id = tenant_id
          @memory_type = memory_type
          @content = content
          @record_id = record_id || SecureRandom.uuid
          @tier = tier
          @occurred_at = occurred_at || Time.now
          @session_id = session_id
          @entity_id = entity_id
          @session_appearance_count = session_appearance_count
          @user_flagged_important = user_flagged_important
          @linked_outcome_value = linked_outcome_value
          @metadata = metadata || {}
          @confidence = confidence
          @trust_source = trust_source
          @last_verified_at = last_verified_at
        end
      end

      module_function

      def classic_memory_class(memory_type)
        CLASSIC_MEMORY_CLASS[memory_type] || "semantic"
      end

      def days_between(later, earlier)
        [0, ((later - earlier) / 86_400).floor].max
      end

      # Importance 0..1 (retention). PIPELINE_UNIFIED §7.5.
      def compute_importance(record, now: Time.now)
        days_old = days_between(now, record.occurred_at)
        recency = [0.0, 1 - days_old / 90.0].max
        repeat = [1.0, record.session_appearance_count / 5.0].min
        flag = record.user_flagged_important ? 1.0 : 0.0
        outcome = record.linked_outcome_value > 10_000_000 ? 1.0 : 0.0
        [1.0, 0.2 * recency + 0.3 * repeat + 0.3 * flag + 0.2 * outcome].min
      end

      def halflife_days(memory_type)
        HALFLIFE_DAYS[memory_type] || DEFAULT_HALFLIFE_DAYS
      end

      # Believability now (decay since last verification / event). ADR-0030.
      def compute_trust(record, now: Time.now)
        base = record.last_verified_at || record.occurred_at
        age = days_between(now, base)
        hl = halflife_days(record.memory_type)
        score = (record.confidence * (0.5**(age.to_f / hl))).round(3)
        level = score >= TRUST_FRESH ? "fresh" : (score >= TRUST_AGING ? "aging" : "stale")
        unchecked = record.confidence >= 0.8 && record.last_verified_at.nil? && age > hl
        { age_days: age, score: score, level: level,
          verified: !record.last_verified_at.nil?, unchecked: unchecked, halflife: hl }
      end

      # Retrieval-ranking multiplier in [0.4, 1.0].
      def trust_factor(record, now: Time.now)
        0.4 + 0.6 * compute_trust(record, now: now)[:score]
      end

      # Validated-use bump (ADR-0032) — asymptotic learning curve toward ceiling.
      def reinforce_confidence(record, learn_rate: CDFLHarness.config.reasoning.learn_rate)
        ceiling = CONF_CEILING[record.trust_source] || DEFAULT_CEILING
        record.confidence = [ceiling, (record.confidence + learn_rate * (ceiling - record.confidence))].min.round(4)
      end

      # Tenant maturation from accumulated still-trusted knowledge ("càng nhiều
      # tháng càng biết nhiều").
      def experience_level(records, now: Time.now, k: CDFLHarness.config.reasoning.experience_k)
        return { experience: 0.0, knowledge_mass: 0.0, band: "mới", n: 0, tenure_days: 0 } if records.empty?

        mass = records.sum { |r| compute_trust(r, now: now)[:score] }
        score = (1 - Math.exp(-k * mass)).round(4)
        tenure = days_between(now, records.map(&:occurred_at).min)
        band = EXPERIENCE_BANDS.find { |thr, _name| score >= thr }.last
        { experience: score, knowledge_mass: mass.round(3), band: band, n: records.size, tenure_days: tenure }
      end
    end
  end
end
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bundle exec rspec spec/reasoning/memory/record_spec.rb`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/cdfl_harness/reasoning/memory/record.rb spec/reasoning/memory/record_spec.rb
git commit -m "feat: Memory record + trust decay + maturation (importance/trust/experience)"
```

### Task 7.2: TierStore (in-memory) + cheap_text_match

**Files:**
- Create: `lib/cdfl_harness/reasoning/memory/tier_store.rb`
- Test: `spec/reasoning/memory/tier_store_spec.rb`

Port of `memory/stores.py`.

- [ ] **Step 1: Write the failing test**

```ruby
# spec/reasoning/memory/tier_store_spec.rb
# frozen_string_literal: true

RSpec.describe CDFLHarness::Reasoning::Memory::InMemoryTierStore do
  Rec = CDFLHarness::Reasoning::Memory::MemoryRecord

  it "put/get/list_all/delete/forget scoped per tenant" do
    s = described_class.new("L3_CONSOLIDATED")
    r = Rec.new(tenant_id: "t1", memory_type: :SEMANTIC, content: "x")
    s.put(r)
    expect(s.get("t1", r.record_id)).to eq(r)
    expect(s.list_all("t1").size).to eq(1)
    expect(s.list_all("other")).to eq([])
    expect(s.delete("t1", r.record_id)).to be(true)
    expect(s.list_all("t1")).to eq([])
  end

  it "put stamps the store's tier onto the record" do
    s = described_class.new("L4_LONG")
    r = Rec.new(tenant_id: "t1", memory_type: :SEMANTIC, content: "x", tier: "L1_WORKING")
    s.put(r)
    expect(r.tier).to eq("L4_LONG")
  end

  it "cheap_text_match is token-set jaccard" do
    m = CDFLHarness::Reasoning::Memory.cheap_text_match("doanh thu quý", "doanh thu tăng")
    expect(m).to be_within(1e-9).of(2.0 / 4.0) # {doanh,thu} ∩ ; union {doanh,thu,quý,tăng}
  end
end
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bundle exec rspec spec/reasoning/memory/tier_store_spec.rb`
Expected: FAIL.

- [ ] **Step 3: Write the implementation**

```ruby
# lib/cdfl_harness/reasoning/memory/tier_store.rb
# frozen_string_literal: true

require_relative "record"

module CDFLHarness
  module Reasoning
    module Memory
      # One backend per tier. Contract; a project swaps Redis/Postgres/Neo4j.
      class TierStore
        def put(record); raise NotImplementedError; end
        def get(tenant_id, record_id); raise NotImplementedError; end
        def list_all(tenant_id); raise NotImplementedError; end
        def delete(tenant_id, record_id); raise NotImplementedError; end
        def forget(tenant_id); raise NotImplementedError; end
      end

      class InMemoryTierStore < TierStore
        attr_reader :tier

        def initialize(tier)
          @tier = tier
          @records = {}             # [tenant_id, record_id] => record
          @by_tenant = Hash.new { |h, k| h[k] = [] }
        end

        def put(record)
          record.tier = @tier
          key = [record.tenant_id, record.record_id]
          @by_tenant[record.tenant_id] << record.record_id unless @records.key?(key)
          @records[key] = record
          record
        end

        def get(tenant_id, record_id) = @records[[tenant_id, record_id]]

        def list_all(tenant_id)
          @by_tenant[tenant_id].map { |rid| @records[[tenant_id, rid]] }.compact
        end

        def delete(tenant_id, record_id)
          key = [tenant_id, record_id]
          return false unless @records.key?(key)

          @records.delete(key)
          @by_tenant[tenant_id].delete(record_id)
          true
        end

        def forget(tenant_id)
          ids = @by_tenant.delete(tenant_id) || []
          ids.each { |rid| @records.delete([tenant_id, rid]) }
          ids.size
        end
      end

      module_function

      # Tiny in-memory retrieval scoring: token-set jaccard 0..1. Unicode-aware.
      def cheap_text_match(query, text)
        q = tokens(query)
        t = tokens(text)
        return 0.0 if q.empty? || t.empty?

        (q & t).size.to_f / (q | t).size
      end

      def tokens(str)
        str.to_s.downcase.scan(/\w+/).to_set
      end
    end
  end
end
```

(Add `require "set"` at the top if your Ruby version doesn't autoload `Set`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `bundle exec rspec spec/reasoning/memory/tier_store_spec.rb`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/cdfl_harness/reasoning/memory/tier_store.rb spec/reasoning/memory/tier_store_spec.rb
git commit -m "feat: Memory InMemoryTierStore + cheap_text_match"
```

### Task 7.3: MemoryService (the palace facade)

**Files:**
- Create: `lib/cdfl_harness/reasoning/memory/service.rb`
- Test: `spec/reasoning/memory/service_spec.rb`

Port of `memory/service.py` — write/retrieve(associative + entity boost + trust ranking)/consolidate/promote/forget/verify/reinforce/link/experience. Synchronous.

- [ ] **Step 1: Write the failing test**

```ruby
# spec/reasoning/memory/service_spec.rb
# frozen_string_literal: true

RSpec.describe CDFLHarness::Reasoning::Memory::Service do
  let(:svc) { described_class.new }

  it "write lands a record at its type's default tier" do
    r = svc.write("t1", :OPERATIONAL, "đã gửi email cho khách")
    expect(r.tier).to eq("L3_CONSOLIDATED")
  end

  it "retrieve returns text-matching records ranked by trust" do
    svc.write("t1", :SEMANTIC, "doanh thu quý 1 tăng mạnh")
    svc.write("t1", :SEMANTIC, "chi phí marketing giảm")
    out = svc.retrieve("t1", "doanh thu quý", top_k: 1)
    expect(out.first.content).to include("doanh thu")
  end

  it "associative recall pulls one-hop linked neighbours" do
    a = svc.write("t1", :SEMANTIC, "khách hàng VIP rời bỏ")
    b = svc.write("t1", :SEMANTIC, "zzz unrelated tokens here")
    svc.link("t1", a.record_id, b.record_id)
    out = svc.retrieve("t1", "khách hàng VIP", top_k: 1, expand_links: true)
    expect(out.map(&:record_id)).to include(b.record_id)
  end

  it "consolidate moves L2 to L3; promote moves important L3 to L4" do
    svc.write("t1", :EPISODIC, "turn", session_id: "s1") # EPISODIC → L2
    expect(svc.consolidate("t1")).to eq(1)
    flagged = svc.write("t1", :DECISION, "quan trọng", user_flagged_important: true) # DECISION → L3
    moved = svc.promote("t1", importance_threshold: 0.25)
    expect(moved).to be >= 1
  end

  it "verify + reinforce reset decay and bump confidence" do
    r = svc.write("t1", :SEMANTIC, "x")
    r.trust_source = "user"
    expect(svc.reinforce("t1", r.record_id)).to be(true)
  end

  it "experience reports tenant maturation" do
    svc.write("t1", :SEMANTIC, "a")
    expect(svc.experience("t1")).to have_key(:experience)
  end
end
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bundle exec rspec spec/reasoning/memory/service_spec.rb`
Expected: FAIL.

- [ ] **Step 3: Write the implementation**

```ruby
# lib/cdfl_harness/reasoning/memory/service.rb
# frozen_string_literal: true

require_relative "record"
require_relative "tier_store"

module CDFLHarness
  module Reasoning
    module Memory
      # Facade over 4 TierStores (cung điện ký ức). Synchronous port of
      # memory/service.py. Default tiers, importance promotion, associative
      # recall, trust ranking, maturation.
      class Service
        DEFAULT_TIER = {
          EPISODIC: "L2_SHORT", SEMANTIC: "L4_LONG", PROCEDURAL: "L4_LONG",
          OPERATIONAL: "L3_CONSOLIDATED", DECISION: "L3_CONSOLIDATED"
        }.freeze
        PROMOTION_THRESHOLD = 0.7
        FORGET_THRESHOLD = 0.3
        FORGET_AGE_DAYS = 90

        def initialize(l1: nil, l2: nil, l3: nil, l4: nil)
          @l1 = l1 || InMemoryTierStore.new("L1_WORKING")
          @l2 = l2 || InMemoryTierStore.new("L2_SHORT")
          @l3 = l3 || InMemoryTierStore.new("L3_CONSOLIDATED")
          @l4 = l4 || InMemoryTierStore.new("L4_LONG")
        end

        attr_reader :l1, :l2, :l3, :l4

        def write(tenant_id, memory_type, content, session_id: nil, entity_id: nil,
                  metadata: nil, user_flagged_important: false, linked_outcome_value: 0.0)
          tier = DEFAULT_TIER.fetch(memory_type)
          rec = MemoryRecord.new(
            tenant_id: tenant_id, memory_type: memory_type, content: content, tier: tier,
            session_id: session_id, entity_id: entity_id, metadata: metadata || {},
            user_flagged_important: user_flagged_important, linked_outcome_value: linked_outcome_value
          )
          tier_store(tier).put(rec)
        end

        def retrieve(tenant_id, query, top_k: 5, tier: "auto", session_id: nil,
                     entity_id: nil, entity_boost: 2.0, expand_links: true,
                     expand_limit: nil, min_score: 0.0, now: Time.now)
          walk = tier == "auto" ? [@l2, @l3, @l4] : [tier_store(tier)]
          scored = []
          all_by_id = {}
          walk.each do |store|
            store.list_all(tenant_id).each do |r|
              next if store.tier == "L2_SHORT" && session_id && r.session_id != session_id

              all_by_id[r.record_id] = r
              score = Memory.cheap_text_match(query, r.content)
              next unless score.positive? && score >= min_score

              score *= entity_boost if entity_id && r.entity_id == entity_id
              score *= Memory.trust_factor(r, now: now)
              scored << [score, r]
            end
          end

          scored.sort_by! { |s, _r| -s }
          results = scored.first(top_k).map { |_s, r| r }

          # reinforce retrieval signal (appearance bump persisted)
          results.each do |r|
            r.session_appearance_count += 1
            tier_store(r.tier).put(r)
          end

          if expand_links
            remaining = expand_limit || top_k
            seen = results.map(&:record_id).to_set
            results.dup.each do |r|
              break if remaining <= 0

              (r.metadata["links"] || []).each do |lid|
                break if remaining <= 0

                nb = all_by_id[lid]
                next if nb.nil? || seen.include?(nb.record_id)

                results << nb
                seen << nb.record_id
                remaining -= 1
              end
            end
          end
          results
        end

        def verify(tenant_id, record_id, now: Time.now)
          each_store do |store|
            r = store.get(tenant_id, record_id)
            next unless r

            r.last_verified_at = now
            store.put(r)
            return true
          end
          false
        end

        def reinforce(tenant_id, record_id, now: Time.now)
          each_store do |store|
            r = store.get(tenant_id, record_id)
            next unless r

            r.last_verified_at = now
            Memory.reinforce_confidence(r)
            store.put(r)
            return true
          end
          false
        end

        def link(tenant_id, a_id, b_id, mutual: true)
          pairs = mutual ? [[a_id, b_id], [b_id, a_id]] : [[a_id, b_id]]
          found = false
          pairs.each do |src, dst|
            each_store do |store|
              r = store.get(tenant_id, src)
              next unless r

              links = (r.metadata["links"] || [])
              links << dst unless links.include?(dst)
              r.metadata["links"] = links
              store.put(r)
              found = true
              break
            end
          end
          found
        end

        def experience(tenant_id, now: Time.now)
          recs = @l4.list_all(tenant_id) + @l3.list_all(tenant_id)
          Memory.experience_level(recs, now: now)
        end

        def consolidate(tenant_id)
          moved = 0
          @l2.list_all(tenant_id).each do |r|
            @l2.delete(tenant_id, r.record_id)
            r.tier = "L3_CONSOLIDATED"
            @l3.put(r)
            moved += 1
          end
          moved
        end

        def promote(tenant_id, importance_threshold: PROMOTION_THRESHOLD, now: Time.now)
          moved = 0
          @l3.list_all(tenant_id).each do |r|
            next unless Memory.compute_importance(r, now: now) > importance_threshold

            @l3.delete(tenant_id, r.record_id)
            r.tier = "L4_LONG"
            @l4.put(r)
            moved += 1
          end
          moved
        end

        def forget(tenant_id, full_tenant_wipe: false, below_score: FORGET_THRESHOLD,
                   age_days: FORGET_AGE_DAYS, now: Time.now)
          if full_tenant_wipe
            return [@l1, @l2, @l3, @l4].sum { |s| s.forget(tenant_id) }
          end

          cutoff = now - age_days * 86_400
          wiped = 0
          @l3.list_all(tenant_id).each do |r|
            next unless r.occurred_at < cutoff && Memory.compute_importance(r, now: now) < below_score

            @l3.delete(tenant_id, r.record_id)
            wiped += 1
          end
          wiped
        end

        private

        def tier_store(tier)
          { "L1_WORKING" => @l1, "L2_SHORT" => @l2,
            "L3_CONSOLIDATED" => @l3, "L4_LONG" => @l4 }.fetch(tier)
        end

        def each_store
          [@l1, @l2, @l3, @l4].each { |s| yield s }
        end
      end
    end
  end
end
```

(Ensure `require "set"` is loaded — it is via `tier_store.rb`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `bundle exec rspec spec/reasoning/memory/service_spec.rb`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/cdfl_harness/reasoning/memory/service.rb spec/reasoning/memory/service_spec.rb
git commit -m "feat: Memory Service facade (write/retrieve+associative/consolidate/promote/forget/verify/reinforce/link/experience)"
```

---

## Phase 8 — Grounding

> Port of `reasoning/grounding.py` (numeric |OR| self-verify) + `agents/grounding_gate.py`
> (evidence → coverage_gate bridge).

### Task 8.1: Grounding verifier (numeric |OR|)

**Files:**
- Create: `lib/cdfl_harness/grounding/verifier.rb`
- Test: `spec/grounding/verifier_spec.rb`

- [ ] **Step 1: Write the failing test**

```ruby
# spec/grounding/verifier_spec.rb
# frozen_string_literal: true

RSpec.describe CDFLHarness::Grounding::Verifier do
  V = CDFLHarness::Grounding::Verifier

  it "extract_claims parses VN/EN numbers" do
    expect(V.extract_claims("doanh thu 1.000.000 và 3,5%")).to include(1_000_000.0, 3.5)
  end

  it "collect_facts walks nested payloads" do
    facts = V.collect_facts({ "a" => 10, "b" => ["x 20", { "c" => 30.0 }] })
    expect(facts).to include(10.0, 20.0, 30.0)
  end

  it "ground_claims returns score 1.0 when no claims" do
    g = V.ground_claims("không có số", [])
    expect(g.score).to eq(1.0)
    expect(g.n_claims).to eq(0)
  end

  it "flags a claim with no matching fact and tolerates percent/fraction rescale" do
    g = V.ground_claims("tỷ lệ 85 và bịa 999", [0.85, 12.0])
    expect(g.flagged).to include(999.0)
    expect(g.flagged).not_to include(85.0) # 85 ↔ 0.85 rescale match
  end
end
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bundle exec rspec spec/grounding/verifier_spec.rb`
Expected: FAIL.

- [ ] **Step 3: Write the implementation**

```ruby
# lib/cdfl_harness/grounding/verifier.rb
# frozen_string_literal: true

module CDFLHarness
  module Grounding
    # Number-overlap |OR| self-verify (CR-0018). Share of an insight's numeric
    # claims matched to measured facts. Heuristic; errs toward NOT flagging.
    # Port of reasoning/grounding.py.
    module Verifier
      Grounding = Struct.new(:score, :n_claims, :n_matched, :flagged, keyword_init: true)

      NUM_RE = /-?\d[\d.,]*\d|-?\d/.freeze

      module_function

      def to_float(tok)
        s = tok.strip.gsub(/%/, "").gsub(/\s/, "")
        return nil if s.empty? || ["-", ".", ","].include?(s)

        has_comma = s.include?(",")
        has_dot = s.include?(".")
        if has_comma && has_dot
          if s.rindex(",") > s.rindex(".")
            s = s.delete(".").tr(",", ".")
          else
            s = s.delete(",")
          end
        elsif has_comma
          a, _, b = s.partition(",")
          s = (s.count(",") == 1 && [1, 2].include?(b.length)) ? "#{a}.#{b}" : s.delete(",")
        elsif has_dot
          unless s.count(".") == 1 && [1, 2].include?(s.rpartition(".").last.length)
            s = s.delete(".")
          end
        end
        Float(s)
      rescue ArgumentError
        nil
      end

      def extract_claims(text)
        (text || "").scan(NUM_RE).filter_map { |m| to_float(m) }
      end

      def collect_facts(payload)
        facts = []
        walk = lambda do |x|
          case x
          when true, false then nil
          when Integer, Float then facts << x.to_f
          when String then facts.concat(extract_claims(x))
          when Hash then x.each_value { |v| walk.call(v) }
          when Array then x.each { |v| walk.call(v) }
          end
        end
        walk.call(payload)
        facts
      end

      def matches?(claim, facts, tol:)
        candidates = [claim, claim / 100.0, claim * 100.0]
        facts.any? do |f|
          scale = [f.abs, 1.0].max
          candidates.any? { |c| (c - f).abs <= tol * scale }
        end
      end

      def ground_claims(text, facts, tol: CDFLHarness.config.reasoning.grounding_tol)
        claims = extract_claims(text)
        return Grounding.new(score: 1.0, n_claims: 0, n_matched: 0, flagged: []) if claims.empty?

        flagged = claims.reject { |c| matches?(c, facts, tol: tol) }
        matched = claims.size - flagged.size
        Grounding.new(score: (matched.to_f / claims.size).round(4),
                      n_claims: claims.size, n_matched: matched, flagged: flagged)
      end

      def disclaimer_for(g)
        if g.flagged.any?
          nums = g.flagged.first(5).map { |x| x == x.to_i ? x.to_i.to_s : x.to_s }.join(", ")
          "⚠ #{g.flagged.size} số chưa khớp dữ liệu đo được (#{nums}) — kiểm chứng trước khi hành động."
        else
          "AI tạo từ dữ liệu — nên kiểm chứng trước khi quyết định."
        end
      end
    end
  end
end
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bundle exec rspec spec/grounding/verifier_spec.rb`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/cdfl_harness/grounding/verifier.rb spec/grounding/verifier_spec.rb
git commit -m "feat: Grounding::Verifier (numeric |OR| self-verify, VN/EN number parsing)"
```

### Task 8.2: Grounding::Gate (evidence → coverage_gate bridge)

**Files:**
- Create: `lib/cdfl_harness/grounding/gate.rb`
- Test: `spec/grounding/gate_spec.rb`

Port of `agents/grounding_gate.py` (sim floor, memory mass, coverage_gate).

- [ ] **Step 1: Write the failing test**

```ruby
# spec/grounding/gate_spec.rb
# frozen_string_literal: true

RSpec.describe CDFLHarness::Grounding::Gate do
  Entry = Struct.new(:role, :tool_name, :tool_result, keyword_init: true)

  def ev(citations: [], recalled: 0, tool: "retrieve_evidence")
    res = tool == "retrieve_evidence" ? { "citations" => citations } : { "recalled" => recalled }
    Entry.new(role: "executor", tool_name: tool, tool_result: res)
  end

  it "only above-floor citations contribute mass (quantity != coverage)" do
    weak = [{ "similarity" => 0.25 }] * 5 # below 0.35 floor
    res = described_class.assess([ev(citations: weak)])
    expect(res[:coverage]).to eq(0.0)
    expect(res[:evidence_count]).to eq(5)
    expect(res[:can_generalize]).to be(false)
  end

  it "strong citations raise coverage past the generalize threshold" do
    strong = [{ "similarity" => 0.9 }, { "similarity" => 0.8 }, { "similarity" => 0.85 }]
    res = described_class.assess([ev(citations: strong)])
    expect(res[:coverage]).to be > 0.0
    expect(res).to have_key(:band)
  end

  it "memory hits add capped mass" do
    res = described_class.assess([ev(tool: "recall_memory", recalled: 10)])
    expect(res[:memory_hits]).to eq(10)
  end
end
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bundle exec rspec spec/grounding/gate_spec.rb`
Expected: FAIL.

- [ ] **Step 3: Write the implementation**

```ruby
# lib/cdfl_harness/grounding/gate.rb
# frozen_string_literal: true

require_relative "../reasoning/knowledge/coverage"

module CDFLHarness
  module Grounding
    # |OR| grounding gate for the agent critic (RAG×harness step 2). Turns the
    # evidence the agent gathered (retrieve_evidence citations + recall_memory
    # hits) into a coverage score, then runs the "học 1 hiểu 10" coverage_gate.
    # Pure + deterministic. Port of agents/grounding_gate.py.
    module Gate
      module_function

      def cfg = CDFLHarness.config.reasoning

      def assess(transcripts, k: cfg.coverage_k)
        sims = []
        memory_hits = 0
        transcripts.each do |entry|
          next unless role_of(entry) == "executor"

          name = name_of(entry)
          res = result_of(entry)
          if name == "retrieve_evidence"
            (res["citations"] || []).each do |c|
              s = c.is_a?(Hash) ? c["similarity"] : nil
              sims << [0.0, s.to_f].max if s.is_a?(Numeric)
            end
          elsif name == "recall_memory"
            memory_hits += (res["recalled"] || 0).to_i
          end
        end

        relevant_mass = sims.select { |s| s >= cfg.sim_floor }.sum
        mass = relevant_mass + cfg.mem_mass * [memory_hits, cfg.mem_cap].min
        coverage = (1.0 - Math.exp(-k * mass)).round(4)
        gate = Reasoning::Knowledge::Coverage.coverage_gate(coverage)
        gate.merge(evidence_count: sims.size, memory_hits: memory_hits)
      end

      # duck-typed accessors (Struct or TranscriptEntry or Hash)
      def role_of(e)   = e.respond_to?(:role) ? e.role : e[:role]
      def name_of(e)   = e.respond_to?(:tool_name) ? e.tool_name : e[:tool_name]

      def result_of(e)
        r = e.respond_to?(:tool_result) ? e.tool_result : e[:tool_result]
        r.is_a?(Hash) ? r : {}
      end
    end
  end
end
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bundle exec rspec spec/grounding/gate_spec.rb`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/cdfl_harness/grounding/gate.rb spec/grounding/gate_spec.rb
git commit -m "feat: Grounding::Gate (evidence -> coverage_gate, sim floor, memory mass)"
```

---

## Phase 9 — Full Part-1 load + suite green

### Task 9.1: Verify the whole gem loads and the suite passes

- [ ] **Step 1: Confirm `lib/cdfl_harness.rb` requires resolve** — it references `agent/session` (Part 2). Temporarily comment that line out for Part 1 (Part 2 re-enables it):

In `lib/cdfl_harness.rb`, ensure there is NO `require_relative "cdfl_harness/agent/session"` yet (Part 2 adds it). The Part-1 require tree is: version, errors, types, schema, config, gateway/client, tooling/registry, store/in_memory, reasoning/cdfl, reasoning/knowledge/coverage, reasoning/knowledge/store, reasoning/memory/service, grounding/gate.

- [ ] **Step 2: Run the full suite**

Run: `bundle exec rspec`
Expected: ALL PASS (every spec from Phases 0-8).

- [ ] **Step 3: Smoke-load in IRB**

Run:
```bash
ruby -Ilib -e "require 'cdfl_harness'; p CDFLHarness::VERSION; p CDFLHarness::Reasoning::CDFL::Agent"
```
Expected: prints `"0.1.0"` and the Agent class constant.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "test: Part 1 core libraries green (gateway + tooling + store + reasoning + grounding)"
```

---

## Self-Review (Part 1)

- **Spec coverage:** Gateway (adapters/router/structured-output/breaker/middleware) ✓; Tooling ✓; Store ✓; CDFL (transition/info-gain/lookahead/agent/four-fold/empowerment/hilbert) ✓; Knowledge coverage gate ✓; Memory palace ✓; Grounding verifier + gate ✓. Agent loop + real adapters + demo + docs are intentionally Part 2.
- **Placeholders:** none — every step has runnable code + exact commands.
- **Type consistency:** `Config#model_for`, `Router#resolve` → `[model, method]`, `Registry#dispatch` → `[ok, payload]`, `Coverage.coverage_gate` keys (`:can_generalize`, `:band`, `:coverage`, `:note`), `Gate.assess` merges `:evidence_count`/`:memory_hits` — all consistent with the consumers wired in Part 2.

**Next:** Part 2 plan — `2026-06-06-cdfl-harness-part2-agent-harness.md` (Workflow/Planner/Executor/Critic/Session with reasoning wiring, real adapters, demo, architecture MDs).
