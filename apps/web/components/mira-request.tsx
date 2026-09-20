"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";

import { MiraSuggestedPrompts } from "@/components/mira-suggested-prompts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  fetchVoiceStatus,
  postExecutiveRequest,
  postVoiceRequest,
  speakMiraResult,
  type ExecutiveResult,
} from "@/lib/api";
import { humanize, statusTone } from "@/lib/display";

export function MiraRequest() {
  const [text, setText] = useState("");
  const [stt, setStt] = useState("demo");
  const [tts, setTts] = useState("demo");
  const [busy, setBusy] = useState(false);
  const [recording, setRecording] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ExecutiveResult | null>(null);
  const recorder = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);

  useEffect(() => {
    fetchVoiceStatus()
      .then((status) => {
        if (!status) return;
        setStt(status.stt);
        setTts(status.tts);
      })
      .catch((err) => {
        console.error("Voice status unavailable", err);
      });
  }, []);

  async function submitTyped(event: FormEvent) {
    event.preventDefault();
    if (!text.trim()) return;

    setBusy(true);
    setError(null);

    const next = await postExecutiveRequest(text.trim());
    setResult(next);

    if (!next) {
      console.error("Typed executive request failed");
      setError("Typed request failed. Check that the API is running on :8000.");
    }

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

        const blob = new Blob(chunks.current, {
          type: media.mimeType || "audio/webm",
        });

        const next = await postVoiceRequest(blob);

        if ("error" in next) {
          console.error("Voice request failed", next.error);
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
    } catch (err) {
      console.error("Microphone blocked", err);
      setError("Microphone is blocked. Type the request instead.");
    }
  }

  async function listen() {
    if (!result) return;

    const spoken = `${result.recommendation.headline}. ${result.recommendation.body}`;
    const audio = await speakMiraResult(spoken);

    if (!audio) {
      console.error("Mira speech playback unavailable");
      setError("Voice playback is not configured. Mira's text result is still on screen.");
      return;
    }

    const url = URL.createObjectURL(audio);
    const player = new Audio(url);
    await player.play();
  }

  const voiceLabel = stt === "live" && tts === "live" ? "Voice ready" : "Voice limited";

  return (
    <Card>
      <CardHeader className="space-y-2">
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-1">
            <CardTitle>Ask Mira</CardTitle>
            <p className="text-sm leading-6 text-mute">Cash, spend, invoices, approvals, or close.</p>
          </div>
          <Badge variant={statusTone(voiceLabel)}>{voiceLabel}</Badge>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {!result && !busy ? <MiraSuggestedPrompts onSelect={setText} /> : null}

        <form onSubmit={submitTyped} className="space-y-3">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <Input
              value={text}
              onChange={(event) => setText(event.target.value)}
              className="flex-1"
              placeholder="Ask Mira a finance question…"
              aria-label="Ask Mira"
              disabled={busy}
            />
            <div className="flex shrink-0 items-center gap-2">
              <Button type="button" size="sm" variant="outline" onClick={toggleMic} disabled={busy}>
                {recording ? "Stop" : "Voice"}
              </Button>
              <Button type="submit" size="sm" disabled={busy || text.trim().length < 3}>
                {busy ? "Asking…" : "Ask"}
              </Button>
            </div>
          </div>
        </form>

        {error ? <p className="text-xs leading-5 text-alert">{error}</p> : null}

        {busy && !result ? (
          <div className="space-y-3 rounded-lg border border-line bg-ink p-4" aria-busy="true">
            <span className="sr-only">Working on your request</span>
            <Skeleton className="h-5 w-48" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-5/6" />
          </div>
        ) : null}

        {result ? (
          <div className="rounded-lg border border-line bg-ink p-4">
            {result.transcript ? <p className="text-xs leading-5 text-mute">Heard: {result.transcript}</p> : null}
            <h3 className="mt-1 font-serif text-xl text-ivory">{result.recommendation.headline}</h3>
            <p className="mt-2 text-sm leading-6 text-mute">{result.recommendation.body}</p>
            <div className="mt-3 flex items-center gap-2">
              <Badge variant="mute">{humanize(result.kind)}</Badge>
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
