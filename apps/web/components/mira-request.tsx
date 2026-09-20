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
  const [text, setText] = useState("What did you catch overnight?");
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

  const voiceReady = stt === "live" && tts === "live";
  const voiceInputReady = stt === "live";

  async function submitTyped(event: FormEvent) {
    event.preventDefault();

    const request = text.trim();
    if (!request) return;

    setBusy(true);
    setError(null);

    const next = await postExecutiveRequest(request);
    setResult(next);

    if (!next) {
      setError("Mira could not complete that request.");
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
          setError(next.error);
        } else {
          setResult(next);

          if (next.transcript) {
            setText(next.transcript);
          }
        }

        setBusy(false);
      };

      recorder.current = media;
      media.start();
      setRecording(true);
    } catch {
      setError("Microphone access is unavailable. You can still type the request.");
    }
  }

  async function listen() {
    if (!result) return;

    setError(null);

    const spoken = `${result.recommendation.headline}. ${result.recommendation.body}`;
    const audio = await speakMiraResult(spoken);

    if (!audio) {
      setError("Voice playback is unavailable. Mira's verified result remains on screen.");
      return;
    }

    const url = URL.createObjectURL(audio);
    const player = new Audio(url);

    player.onended = () => URL.revokeObjectURL(url);

    try {
      await player.play();
    } catch {
      URL.revokeObjectURL(url);
      setError("Audio playback was blocked by the browser.");
    }
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <CardTitle className="text-base text-ivory">Ask Mira</CardTitle>
            <p className="mt-1 text-xs text-mute">
              Ask about cash, spend, invoices, approvals, or close.
            </p>
          </div>

          <Badge variant={voiceInputReady ? "ledger" : "mute"}>
            {voiceReady
              ? "Voice ready"
              : voiceInputReady
                ? "Voice input ready"
                : "Typed mode"}
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="space-y-3">
        <form
          className="flex flex-col gap-2 sm:flex-row"
          onSubmit={submitTyped}
        >
          <input
            value={text}
            onChange={(event) => setText(event.target.value)}
            className="min-w-0 flex-1 rounded-full border border-line bg-paper px-4 py-2 text-sm text-ivory outline-none placeholder:text-mute focus:border-brass/50"
            placeholder="Ask Mira about the business..."
          />

          <div className="flex gap-2">
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={toggleMic}
              disabled={busy || !voiceInputReady}
            >
              {recording ? "Stop recording" : "Voice"}
            </Button>

            <Button
              type="submit"
              size="sm"
              disabled={busy || text.trim().length < 3}
            >
              {busy ? "Working…" : "Ask"}
            </Button>
          </div>
        </form>

        {error ? <p className="text-xs text-alert">{error}</p> : null}

        {result ? (
          <div className="rounded-xl border border-line bg-paper/70 p-4">
            {result.transcript ? (
              <p className="mb-2 text-xs text-mute">
                Voice transcript · {result.transcript}
              </p>
            ) : null}

            <h3 className="font-serif text-xl text-ivory">
              {result.recommendation.headline}
            </h3>

            <p className="mt-2 text-sm leading-relaxed text-mute">
              {result.recommendation.body}
            </p>

            {tts === "live" ? (
              <div className="mt-3">
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  onClick={listen}
                >
                  Listen
                </Button>
              </div>
            ) : null}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
