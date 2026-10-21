import type { TutorialVideo } from "../types/chat.ts";

const VIDEO_ID = /^[A-Za-z0-9_-]{11}$/;
// Margem antes do limite de 30 dias; sessões abertas também são limpas periodicamente.
const MAX_METADATA_AGE = 29 * 24 * 60 * 60 * 1000;

export function isTutorialVideo(value: unknown): value is TutorialVideo {
  if (typeof value !== "object" || value === null) return false;
  const item = value as Record<string, unknown>;
  return typeof item.video_id === "string" && VIDEO_ID.test(item.video_id) &&
    typeof item.title === "string" && item.title.trim().length > 0 && Array.from(item.title).length <= 200 &&
    typeof item.channel === "string" && item.channel.trim().length > 0 && Array.from(item.channel).length <= 200 &&
    typeof item.retrieved_at === "string" && Number.isFinite(Date.parse(item.retrieved_at));
}

export function isVideoList(value: unknown): value is TutorialVideo[] | undefined {
  return value === undefined || (Array.isArray(value) && value.length <= 1 && value.every(isTutorialVideo));
}

export function isVideoCurrent(video: TutorialVideo, now = Date.now()): boolean {
  const age = now - Date.parse(video.retrieved_at);
  return age >= -300_000 && age < MAX_METADATA_AGE;
}

export function videoUrls(id: string) {
  if (!VIDEO_ID.test(id)) throw new Error("ID de vídeo inválido.");
  return {
    watch: `https://www.youtube.com/watch?v=${id}`,
    embed: `https://www.youtube-nocookie.com/embed/${id}?autoplay=0&playsinline=1`,
  };
}

export function copyVideo(video: TutorialVideo): TutorialVideo {
  return { video_id: video.video_id, title: video.title, channel: video.channel, retrieved_at: video.retrieved_at };
}
