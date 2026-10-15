// TubeForge AI API contract types — mirror of backend serializers. No mock data.
//
// FK relations are serialized as plain UUID strings by DRF (e.g. `channel`,
// not `channel_id`); these types match the backend field names exactly.

export interface ApiErrorBody {
  code: string;
  message: string;
  retryable: boolean;
  correlation_id: string;
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface User {
  id: string;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  date_joined: string;
}

// ── Auth / passkeys ──────────────────────────────────────────
export interface PasskeyInfo {
  id: string;
  name: string;
  created_at: string;
}

// ── Channels ──────────────────────────────────────────────
export interface Channel {
  id: string;
  youtube_channel_id: string | null;
  title: string;
  description: string;
  default_language: string;
  timezone: string;
  brand_config: Record<string, unknown>;
  automation_config: Record<string, unknown>;
  publishing_policy: Record<string, unknown>;
  is_active: boolean;
}

// ── Research ──────────────────────────────────────────────
export interface ResearchRun {
  id: string;
  channel: string;
  query: string;
  parameters: Record<string, unknown>;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface ContentIdea {
  id: string;
  channel: string;
  title: string;
  topic: string;
  format: string;
  priority: number;
  confidence_score: number;
  supporting_evidence: Record<string, unknown> | unknown[];
  status: string;
}

// ── Projects ──────────────────────────────────────────────
export type ProjectStatus = string;

export interface Project {
  id: string;
  channel: string;
  content_idea: string | null;
  title: string;
  brief: string;
  format: string;
  target_duration_seconds: number;
  aspect_ratio: string;
  language: string;
  status: ProjectStatus;
  current_workflow_id: string | null;
  settings: Record<string, unknown>;
}

// Backend GeneratePlanView response shape (heuristic plan; every estimate is
// explicitly labeled as such — see estimated_duration.estimate).
export interface PlanStage {
  name: string;
  order: number;
  requires_approval: boolean;
}

export interface Plan {
  stages: PlanStage[];
  scene_count_estimate: number;
  estimated_duration: {
    estimate: boolean;
    total_minutes: number;
    method: string;
  };
  estimated_cost: {
    estimate: boolean;
    amount_usd: number;
    method: string;
    disclaimer: string;
  };
  models: string[];
  approvals: string[];
}

export interface ScriptVersion {
  id: string;
  project: string;
  version_number: number;
  structured_script: Record<string, unknown> | null;
  rendered_text: string;
  fact_check_status: string;
  approval_status: string;
  created_at: string;
}

export interface Scene {
  id: string;
  project: string;
  position: number;
  script_segment: string;
  visual_prompt: string;
  negative_prompt: string;
  duration_seconds: number | null;
  scene_type: string;
  status: string;
  created_at: string;
}

// ── Workflows ─────────────────────────────────────────────
export const WORKFLOW_STATES = [
  "DRAFT","PLANNING","AWAITING_APPROVAL","QUEUED","RESEARCHING","SCRIPTING",
  "STORYBOARDING","GENERATING_ASSETS","GENERATING_NARRATION","ASSEMBLING",
  "RENDERING","VALIDATING","FINAL_REVIEW","READY_TO_PUBLISH","UPLOADING",
  "SCHEDULED","PUBLISHED","FAILED","CANCELED","PAUSED","BLOCKED_ON_RESOURCES",
  "BLOCKED_ON_APPROVAL",
] as const;
export type WorkflowState = typeof WORKFLOW_STATES[number];

export interface WorkflowRun {
  id: string;
  project: string;
  workflow_type: string;
  temporal_workflow_id: string;
  status: WorkflowState;
  current_stage: string;
  input_snapshot: Record<string, unknown>;
  output_summary: Record<string, unknown>;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface WorkflowEvent {
  id: string;
  event_type: string;
  stage: string | null;
  payload: Record<string, unknown>;
  occurred_at: string;
}

export interface Approval {
  id: string;
  project: string;
  workflow_run: string | null;
  approval_type: string;
  status: string;
  requested_by: string;
  decided_by: string | null;
  decision_reason: string;
  requested_at: string;
  decided_at: string | null;
}

// ── Providers / models / resources ────────────────────────
export interface Provider {
  id: string;
  name: string;
  adapter_type: string;
  deployment_type: string;
  base_url: string;
  capabilities: string[];
  enabled: boolean;
  priority: number;
  health_status: string;
  configuration: Record<string, unknown>;
}

export interface AIModel {
  id: string;
  provider: string;
  model_identifier: string;
  model_version: string;
  task_type: string;
  hardware_requirements: Record<string, unknown> | null;
  quality_profile: string;
  license_metadata: Record<string, unknown> | null;
  enabled: boolean;
}

export interface GenerationJob {
  id: string;
  project: string | null;
  scene: string | null;
  provider: string;
  provider_name: string;
  model: string;
  model_identifier: string;
  task_type: string;
  status: string;
  attempt_count: number;
  estimated_cost: number | null;
  actual_cost: number | null;
  error_code: string | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface ResourceUsageEvent {
  id: string;
  resource_type: string;
  quantity: number;
  unit: string;
  estimated_cost: number | null;
  actual_cost: number | null;
  occurred_at: string;
}

export interface Budget {
  id: string;
  scope_type: string;
  scope_id: string | null;
  limits: Record<string, number>;
  created_at: string;
  updated_at: string;
}

// ── Media ─────────────────────────────────────────────────
export interface Asset {
  id: string;
  project: string | null;
  scene: string | null;
  asset_type: string;
  mime_type: string;
  sha256: string;
  duration_seconds: number | null;
  width: number | null;
  height: number | null;
  source_type: string;
  license_metadata: Record<string, unknown> | null;
  model_metadata: Record<string, unknown> | null;
  status: string;
}

export interface TimelineClip {
  id: string;
  track_id: string;
  asset_id: string | null;
  start_s: number;
  end_s: number;
  offset_s: number;
  label: string;
}

export interface TimelineTrack {
  id: string;
  kind: "video" | "audio" | "caption";
  name: string;
  clips: TimelineClip[];
}

export interface TimelineV1 {
  version: 1;
  tracks: TimelineTrack[];
}

// Backend TimelineVersion row wrapping a TimelineV1 document.
export interface TimelineVersionRow {
  id: string;
  project: string;
  version_number: number;
  timeline_json: TimelineV1;
  render_settings: Record<string, unknown>;
  created_at: string;
}

export interface RenderJob {
  id: string;
  project: string;
  timeline_version: string;
  status: string;
  output_asset: string | null;
  error: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

// ── Publishing ────────────────────────────────────────────
export const UPLOAD_STATES = [
  "DRAFT","VALIDATING","APPROVED","UPLOAD_PENDING","UPLOADING","PROCESSING",
  "SCHEDULED","PUBLISHED","RETRYABLE_FAILURE","PERMANENT_FAILURE",
  "AUTHORIZATION_REQUIRED","QUOTA_BLOCKED","CANCELED",
] as const;
export type UploadState = typeof UPLOAD_STATES[number];

export interface PublicationJob {
  id: string;
  project: string;
  channel: string;
  asset: string | null;
  youtube_video_id: string | null;
  title: string;
  description: string;
  tags: string[];
  visibility: string;
  scheduled_at: string | null;
  status: UploadState;
  attempt_count: number;
  last_error: string | null;
  published_at: string | null;
}

// ── Analytics ─────────────────────────────────────────────
export type MetricSource = "YOUTUBE_API" | "CALCULATED" | "AI_INTERPRETATION" | "FORECAST";

export interface AnalyticsSnapshot {
  id: string;
  channel: string;
  youtube_video_id: string | null;
  metrics: Record<string, number>;
  source: MetricSource;
  captured_at: string;
}

// ── Ops ───────────────────────────────────────────────────
export interface HealthStatus {
  status: string;
  // Backend HealthView returns plain string values: "ok", "not_configured",
  // "unreachable", "error: ...", etc.
  checks: Record<string, string>;
  gpu?: Record<string, unknown> | null;
  cpu_percent?: number | null;
  ram_percent?: number | null;
  disk_percent?: number | null;
  queue_depth?: number | null;
  workflow_failures_24h?: number | null;
  db?: string | null;
  backup?: { status: string; last_run?: string } | null;
  cert_expiry?: string | null;
}

export interface AuditEvent {
  id: string;
  actor: string;
  action: string;
  resource_type: string;
  resource_id: string;
  occurred_at: string;
}

export interface Notification {
  id: string;
  type: string;
  title: string;
  body: string;
  resource_type: string;
  resource_id: string;
  read_at: string | null;
  created_at: string;
}

export interface AutomationRule {
  id: string;
  channel: string;
  name: string;
  trigger_type: string;
  conditions: Record<string, unknown>;
  actions: Record<string, unknown>;
  enabled: boolean;
}

export interface SubscriptionTier {
  id: string;
  name: string;
  display_name: string;
  price_monthly_cents: number;
  price_monthly_usd: number;
  max_projects: number;
  max_storage_gb: number;
  max_api_calls_month: number;
  features: string[];
}

export interface BillingUsage {
  projects_used: number;
  projects_limit: number;
  storage_gb_used: number;
  storage_gb_limit: number;
  api_calls_used: number;
  api_calls_limit: number;
}

export interface UserSubscription {
  id: string;
  tier: SubscriptionTier;
  status: string;
  current_period_start: string | null;
  current_period_end: string | null;
  created_at: string;
  updated_at: string;
}
