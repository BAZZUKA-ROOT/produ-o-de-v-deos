export type Role = "user" | "admin";
export interface User { id: string; name: string; email: string; role: Role; is_active: boolean; quota_mb: number | null; created_at: string; last_login_at: string | null; projects?: number; usage_bytes?: number }

export type AssetKind = "image" | "audio" | "music" | "video" | "logo";
export interface Asset {
  id: string; kind: AssetKind; source: "upload" | "ai" | "generated" | "render" | "system"; name: string; mime: string;
  size_bytes: number; width: number | null; height: number | null; duration: number | null; project_id: string | null;
  in_library: boolean; is_system: boolean; meta: Record<string, unknown>; url: string; download_url: string; created_at: string;
}

export type JobStatus = "queued" | "running" | "completed" | "failed" | "cancelling" | "cancelled";
export type JobKind = "script" | "images" | "narration" | "preview" | "render" | "model_pull";
export interface Job {
  id: string; kind: JobKind; status: JobStatus; progress: number; stage: string; error: string | null;
  result: Record<string, unknown>; attempts: number; project_id: string | null; created_at: string;
  started_at: string | null; finished_at: string | null; logs?: string; user_email?: string | null;
  project_name?: string | null; duration_seconds?: number;
}

export interface Company {
  name: string; segment: string; description: string; product: string; offer: string; audience: string;
  differentials: string; phone: string; whatsapp: string; instagram: string; address: string; website: string;
}

export interface Watermark { enabled: boolean; type: "text" | "image"; text: string; asset_id: string | null; position: string; opacity: number }
export interface EndCard { enabled: boolean; duration: number; show_phone: boolean; show_instagram: boolean; show_address: boolean; headline: string }
export interface ProjectSettings {
  format: string; duration: number; style: string; video_type: string; quality: string;
  music_asset_id: string | null; music_mood: string; music_volume: number;
  narration_enabled: boolean; narration_mode: "tts" | "upload"; narration_asset_id: string | null;
  tts_provider: string | null; voice_gender: "female" | "male"; voice_speed: number;
  subtitles_enabled: boolean; subtitle_style: string; font: string; palette: string[];
  watermark: Watermark; end_card: EndCard; logo_asset_id: string | null; fit_duration: boolean; sfx_enabled: boolean; stage_effects: boolean;
}

export interface Scene {
  id: string; position: number; role: string; title: string; subtitle: string; narration: string; caption_override: string;
  image_prompt: string; duration: number; transition: string; motion: string; text_animation: string; text_position: string;
  fit: string; layout: string; bullets: string; cutout_url: string | null; cutout_usable: boolean; resolved_layout?: string;
  image: Asset | null; narration_audio: Asset | null; narration_duration: number | null; narration_stale?: boolean;
}

export type ProjectStatus = "draft" | "scripting" | "ready" | "processing" | "completed" | "failed" | "cancelled";
export interface ProjectSummary {
  id: string; name: string; status: ProjectStatus; company_name: string | null; format: string; duration: number;
  style: string; video_type: string; scene_count: number; has_video: boolean; thumbnail_url: string | null;
  template_id: string | null; owner_id: string; created_at: string; updated_at: string; owner_email?: string;
}
export interface Script { title?: string; hook?: string; cta?: string; caption?: string; hashtags?: string[]; analysis?: string; engine?: string; narration_full?: string }
export interface Project extends ProjectSummary {
  company: Company; settings: ProjectSettings; script: Script; scenes: Scene[];
  output: Asset | null; preview: Asset | null; thumbnail: Asset | null; music: Asset | null; logo: Asset | null;
  narration_track: Asset | null; active_job: Job | null; jobs: Job[]; template: { id: string; name: string } | null;
}

export interface Caption { start: number; end: number; text: string }
export interface TimelineScene { id: string; start: number; duration: number; trans_out: number; transition: string; narr_start: number | null; narr_duration: number | null; captions: Caption[] }
export interface Timeline { total: number; tempo: number; scenes: TimelineScene[]; end_card_start: number | null; end_card_duration: number; warnings: string[] }

export interface Template {
  id: string; slug: string; category: string; category_label: string; name: string; description: string; style: string;
  video_type: string; palette: string[] | null; font: string | null; scene_count: number; is_active: boolean;
  config?: Record<string, unknown>;
}

export interface Options {
  formats: string[]; durations: number[]; qualities: string[]; styles: Record<string, string>; video_types: Record<string, string>;
  transitions: string[]; motions: string[]; text_animations: string[]; text_positions: string[]; fits: string[];
  voices: Record<string, Record<string, string>>; music_moods: Record<string, string>; subtitle_styles: string[]; fonts: string[]; layouts: string[];
  style_presets: Record<string, { font: string; palette: string[]; music: string; transition: string; motion: string; animation: string }>;
}

export interface Notification { id: string; title: string; message: string; level: string; link: string | null; read: boolean; created_at: string }
export interface Page<T> { items: T[]; total: number; page?: number; page_size?: number }
