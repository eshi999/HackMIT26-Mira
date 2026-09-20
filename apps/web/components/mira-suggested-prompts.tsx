"use client";

const PROMPTS = [
  "What did you catch overnight?",
  "How much cash do we have?",
  "What needs my approval?",
  "What's blocking September close?",
  "What risks should I know about?",
  "Why was the HelixCloud invoice held?",
];

export function MiraSuggestedPrompts({
  onSelect,
}: {
  onSelect: (prompt: string) => void;
}) {
  return (
    <div className="space-y-2">
      <p className="text-xs text-mute">Try asking</p>
      <div className="flex flex-wrap gap-2">
        {PROMPTS.map((prompt) => (
          <button
            key={prompt}
            type="button"
            onClick={() => onSelect(prompt)}
            className="rounded-md border border-line px-3 py-1.5 text-sm text-mute transition-colors hover:text-ivory focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brass/60 focus-visible:ring-offset-2 focus-visible:ring-offset-ink"
          >
            {prompt}
          </button>
        ))}
      </div>
    </div>
  );
}
