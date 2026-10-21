"use client";

import { useState, useSyncExternalStore } from "react";
import { isTutorialVideo, isVideoCurrent, videoUrls } from "@/lib/videos";
import type { TutorialVideo as Video } from "@/types/chat";

function subscribeClock(onChange: () => void) {
  const timer = window.setInterval(onChange, 60_000);
  return () => window.clearInterval(timer);
}

export function TutorialVideo({ video }: { video: Video }) {
  const [loaded, setLoaded] = useState(false);
  // A validade depende do relógio do navegador; não avaliar Date.now no prerender.
  const current = useSyncExternalStore(subscribeClock,
    () => isTutorialVideo(video) && isVideoCurrent(video), () => false);
  if (!current) return null;
  const urls = videoUrls(video.video_id);
  return (
    <section aria-label={`Tutorial: ${video.title}`} className="w-full max-w-xl overflow-hidden rounded-xl border border-slate-700 bg-slate-950/60">
      <div className="px-4 py-3">
        <p className="text-xs text-slate-400">Tutorial no YouTube · {video.channel}</p>
        <h3 className="mt-1 text-sm font-medium text-slate-100">{video.title}</h3>
      </div>
      {loaded ? (
        <iframe
          src={urls.embed}
          title={`Vídeo do YouTube: ${video.title}`}
          className="aspect-video min-h-[200px] w-full border-0"
          allow="encrypted-media; picture-in-picture; fullscreen"
          allowFullScreen
          referrerPolicy="strict-origin-when-cross-origin"
        />
      ) : (
        <button type="button" onClick={() => setLoaded(true)}
          className="flex min-h-[200px] w-full items-center justify-center bg-slate-900 px-5 py-8 text-sm text-indigo-200 hover:bg-slate-800 focus-visible:outline-2 focus-visible:outline-indigo-300">
          Carregar player do YouTube
        </button>
      )}
      <div className="px-4 py-3 text-xs leading-5 text-slate-400">
        {loaded && <button type="button" onClick={() => setLoaded(false)} className="mr-3 text-indigo-300 underline">Fechar player</button>}
        <a href={urls.watch} target="_blank" rel="noopener noreferrer" className="text-indigo-300 underline">Abrir no YouTube</a>
        <span> · Se o player ficar indisponível, use o link. O YouTube recebe dados ao carregar o player; a reprodução não é automática.</span>
      </div>
    </section>
  );
}
