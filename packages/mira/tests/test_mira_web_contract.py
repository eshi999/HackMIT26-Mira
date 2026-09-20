from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

REQUEST_COMPONENT = (
    ROOT
    / "apps"
    / "web"
    / "components"
    / "mira-request.tsx"
)

PROMPTS_COMPONENT = (
    ROOT
    / "apps"
    / "web"
    / "components"
    / "mira-suggested-prompts.tsx"
)


def test_ask_mira_starts_without_fake_user_message() -> None:
    source = REQUEST_COMPONENT.read_text()

    assert 'const [text, setText] = useState("");' in source

    assert (
        'useState("What did you catch overnight?")'
        not in source
    )


def test_suggested_prompts_component_exists() -> None:
    assert PROMPTS_COMPONENT.exists()

    source = PROMPTS_COMPONENT.read_text()

    assert "What did you catch overnight?" in source
    assert "How much cash do we have?" in source
    assert "What needs my approval?" in source
    assert "What's blocking September close?" in source
    assert "What risks should I know about?" in source
    assert "Why was the HelixCloud invoice held?" in source


def test_suggestions_only_fill_input() -> None:
    source = PROMPTS_COMPONENT.read_text()

    assert "onClick={() => onSelect(prompt)}" in source

    # Suggested prompts may fill the text field, but they must
    # never execute a finance request on their own.
    assert "postExecutiveRequest" not in source
    assert "postVoiceRequest" not in source
    assert "fetch(" not in source


def test_request_component_uses_suggestions() -> None:
    source = REQUEST_COMPONENT.read_text()

    assert "MiraSuggestedPrompts" in source
    assert "onSelect={setText}" in source


def test_suggestions_are_only_shown_before_a_result() -> None:
    source = REQUEST_COMPONENT.read_text()

    assert "!result && !busy" in source


def test_typed_request_path_is_still_wired() -> None:
    source = REQUEST_COMPONENT.read_text()

    assert "postExecutiveRequest" in source


def test_voice_request_path_is_still_wired() -> None:
    source = REQUEST_COMPONENT.read_text()

    assert "postVoiceRequest" in source


def test_tts_path_is_still_wired() -> None:
    source = REQUEST_COMPONENT.read_text()

    assert "speakMiraResult" in source
