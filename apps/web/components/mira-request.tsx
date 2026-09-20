"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  fetchVoiceStatus,
  postExecutiveRequest,
  postVoiceRequest,
  speakMiraResult,
  type ExecutiveResult,
} from "@/lib/api";

export function MiraRequest() {
  const [text, setText] = useState("Mira, what did you catch overnight?");
  const [stt, setStt] = useState("demo");
  const [tts, setTts] = useState("demo");
  const [busy, setBusy] = useState(false);
  const [recording, setRecording] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ExecutiveResult | null>(null);
  const recorder = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);

  useEffect(() => {
    fetchVoiceStatus().then((status) => {
      if (!status) return;
      setStt(status.stt);
      setTts(status.tts);
    });
  }, []);

  async function submitTyped(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const next = await postExecutiveRequest(text.trim());
    setResult(next);
    if (!next) setError("Typed request failed. Check that the API is on :8000.");
    setBusy(false);
  }

  async function toggleMic() {
    if (recording) {
      recorder.current?.stop();
      return;
    }
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const media = new MediaRecorder(stream);
      chunks.current = [];
      media.ondataavailable = (event) => {
        if (event.data.size) chunks.current.push(event.data);
      };
      media.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop());
        setRecording(false);
        setBusy(true);
        const blob = new Blob(chunks.current, { type: media.mimeType || "audio/webm" });
        const next = await postVoiceRequest(blob);
        if ("error" in next) {
          setError(next.error);
        } else {
          setResult(next);
          if (next.transcript) setText(next.transcript);
        }
        setBusy(false);
      };
      recorder.current = media;
      media.start();
      setRecording(true);
    } catch {
      setError("Microphone is blocked. Type the request instead.");
    }
  }

  async function listen() {
    if (!result) return;
    const spoken = `${result.recommendation.headline}. ${result.recommendation.body}`;
    const audio = await speakMiraResult(spoken);
    if (!audio) {
      setError("ElevenLabs is not configured. Mira's text result is still on screen.");
      return;
    }
    const url = URL.createObjectURL(audio);
    const player = new Audio(url);
    await player.play();
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center gap-2">
          <CardTitle className="text-base text-mute">Ask Mira</CardTitle>
          <Badge variant={stt === "live" ? "ledger" : "mute"}>Deepgram {stt}</Badge>
          <Badge variant={tts === "live" ? "ledger" : "mute"}>ElevenLabs {tts}</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-xs text-mute">
          Voice and typed input both hit the executive request API. This is not an open chat.
        </p>
        <form className="flex flex-col gap-2 sm:flex-row" onSubmit={submitTyped}>
          <input
            value={text}
            onChange={(event) => setText(event.target.value)}
            className="min-w-0 flex-1 rounded-full border border-line bg-paper px-4 py-2 text-sm text-ivory outline-none placeholder:text-mute focus:border-brass/50"
            placeholder="Run today's finance review."
          />
          <div className="flex gap-2">
            <Button type="button" size="sm" variant="outline" onClick={toggleMic} disabled={busy}>
              {recording ? "Stop" : "Mic"}
            </Button>
            <Button type="submit" size="sm" disabled={busy || text.trim().length < 3}>
              Ask
            </Button>
          </div>
        </form>
        {error ? <p className="text-xs text-alert">{error}</p> : null}
        {result ? (
          <div className="rounded-xl border border-line bg-paper/70 p-4">
            {result.transcript ? (
              <p className="text-[11px] uppercase tracking-[0.16em] text-mute">
                Heard: {result.transcript}
              </p>
            ) : null}
            <h3 className="mt-1 font-serif text-xl text-ivory">{result.recommendation.headline}</h3>
            <p className="mt-2 text-sm leading-relaxed text-mute">{result.recommendation.body}</p>
            <div className="mt-3 flex items-center gap-2">
              <Badge variant="mute">{result.kind}</Badge>
              {tts === "live" ? (
                <Button type="button" size="sm" variant="ghost" onClick={listen}>
                  Listen
                </Button>
              ) : null}
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
