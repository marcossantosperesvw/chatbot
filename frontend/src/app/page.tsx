"use client";

import { useState, useEffect } from "react";

export default function Home() {
  const [status, setStatus] = useState<string>("Conectando...");

  useEffect(() => {
    fetch("http://localhost:8000/api/health")
      .then((res) => res.json())
      .then((data) => setStatus(data.message))
      .catch(() => setStatus("Erro ao conectar com o backend."));
  }, []);

  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-slate-900 text-white p-6">
      <div className="bg-slate-800 p-8 rounded-xl border border-slate-700 max-w-md w-full text-center">
        <h1 className="text-3xl font-bold text-indigo-400 mb-4">🎮 Chat Jogos Online</h1>
        <p className="text-slate-300 mb-2">Status da API Backend:</p>
        <div className="bg-slate-950 p-3 rounded font-mono text-sm text-green-400 border border-slate-800">
          {status}
        </div>
      </div>
    </main>
  );
}
