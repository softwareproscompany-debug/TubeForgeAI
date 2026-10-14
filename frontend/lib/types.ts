// TubeForge AI API contract types — mirror of backend contract. No mock data.

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
  email: string;
  display_name: string;
}

// ── Channels ──────────────────────────────────────────────
export interface Channel {
  id: string;
  youtube_channel_id: string;
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
  channel_id: string;
  query: string;
  parameters: Record<string, unknown>;
  status: string;
  created_at: string;
  completed_at: string | null;
}

export interface ContentIdea {
  id: string;
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
  channel_id: string;
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

export interface PlanStage {
  stage: string;
  description: string;
  model: string | null;
  estimated_duration_s: number | null;
  estimated_cost_usd: number | null;
}

export interface Plan {
  interpreted_goal: string;
  channel_id: string;
  stages: PlanStage[];
  expected_duration_s: number;
  estimated_cost_usd: number;
  models: string[];
  approval_checkpoints: string[];
  resource_requirements: Record<string, unknown>;
}

export interface ScriptVersion {
  id: string;
  project_id: string;
  version: number;
  title: string;
  content: string;
  status: string;
  created_at: string;
}

export interface Scene {
  id: string;
  project_id: string;
  order: number;
  title: string;
  description: string;
  prompt: string | null;
  status: string;
  asset_id: string | null;
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
  project_id: string;
  workflow_type: string;
  temporal_workflow_id: string;
  status: WorkflowState;
  current_stage: string | null;
  created_at: string;
  updated_at: string;
}

export interface WorkflowEvent {
  id: string;
  event_type: string;
  stage: string | null;
  payload: Record<string, unknown>;
  occurred_at: string;
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
  latency_ms?: number | null;
  pricing?: Record<string, unknown> | null;
  concurrency?: number | null;
}

export interface AIModel {
  id: string;
  provider_id: string;
  name: string;
  model_type: string;
  capabilities: string[];
  enabled: boolean;
}

export interface GenerationJob {
  id: string;
  project_id: string | null;
  provider_id: string;
  model_id: string;
  job_type: string;
  status: string;
  progress: number | null;
  failure_reason: string | null;
  retry_count: number;
  created_at: string;
  updated_at: string;
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
  scope: string;
  period: string;
  limit_usd: number;
  spent_usd: number;
}

// ── Media ─────────────────────────────────────────────────
export interface Asset {
  id: string;
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

export interface RenderJob {
  id: string;
  project_id: string;
  status: string;
  output_asset_id: string | null;
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
  youtube_video_id: string | null;
  title: string;
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
  metrics: Record<string, number>;
  source: MetricSource;
  captured_at: string;
}

// ── Ops ───────────────────────────────────────────────────
export interface HealthStatus {
  status: string;
  checks: Record<string, { status: string; detail?: string }>;
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
  title: string;
  body: string;
  severity: string;
  read: boolean;
  created_at: string;
}

export interface AutomationRule {
  id: string;
  channel_id: string;
  name: string;
  trigger: string;
  conditions: Record<string, unknown>;
  actions: Record<string, unknown>;
  enabled: boolean;
}
