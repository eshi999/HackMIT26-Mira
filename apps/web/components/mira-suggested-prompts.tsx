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
            className="rounded-full border border-line bg-paper/40 px-3 py-2 text-sm text-ivory transition hover:border-brass/50 hover:bg-paper/70"
          >
            {prompt}
          </button>
        ))}
      </div>
    </div>
  );
}
