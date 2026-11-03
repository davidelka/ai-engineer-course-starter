"""Lesson 21: voicekit (ports, fakes, OpenAI adapters over httpx, Hebrew WER, pipeline)."""

import json
import math

import httpx
import pytest

from llmkit import LLM
from mockllm import MockConfig, start_in_thread
from voicekit import (FakeSTT, FakeTTS, Transcript, VoicePipeline, Word, align, cer, normalize_hebrew,
                      reading_feedback, split_sentences, wer)
from voicekit.audio import add_comment, duration_of, pcm_to_wav, read_comment, tone, wav_info
from voicekit.openai_audio import OpenAISpeech, OpenAITranscriber, VoiceError, words_from_logprobs
from voicekit.ports import STT, TTS

SENT = "אני רוצה לקנות כרטיס לאוטובוס לתל אביב"


# ---------------------------------------------------------------- audio helpers
def test_wav_comment_round_trip_and_duration():
    wav = pcm_to_wav(tone(1.5, sample_rate=16_000), 16_000)
    assert wav_info(wav) == (16_000, 1, 1.5)
    tagged = add_comment(wav, SENT)
    assert read_comment(tagged) == SENT
    assert abs(duration_of(tagged) - 1.5) < 1e-6  # the extra chunk does not break the WAV
    assert read_comment(wav) is None
    assert duration_of(b"\x00\x00" * 24_000, "pcm", 24_000) == 1.0


# ---------------------------------------------------------------- fakes
def test_fakes_implement_the_ports():
    assert isinstance(FakeSTT(), STT) and isinstance(FakeTTS(), TTS)


def test_fake_round_trip_is_exact_without_errors():
    speech = FakeTTS().synthesize(SENT)
    assert speech.format == "wav" and speech.duration_s == pytest.approx(len(SENT) / 14, abs=0.3)
    tr = FakeSTT().transcribe(speech.audio, language="he", word_timestamps=True)
    assert tr.text == SENT and wer(SENT, tr.text).rate == 0.0
    assert tr.words[0].start == 0.0 and tr.words[-1].end == pytest.approx(tr.duration_s, abs=0.01)


def test_fake_errors_are_deterministic_and_measurable():
    audio = FakeTTS().synthesize(SENT).audio
    a = FakeSTT(error_rate=0.5, seed=7).transcribe(audio).text
    b = FakeSTT(error_rate=0.5, seed=7).transcribe(audio).text
    assert a == b and a != SENT
    assert 0 < wer(SENT, a).rate <= 1


def test_fake_substitutions_lower_confidence():
    audio = FakeTTS().synthesize("פתח את הספר בפרק שלוש").audio
    tr = FakeSTT(substitutions={"בפרק": "בברק"}).transcribe(audio)
    assert "בברק" in tr.text
    assert min(w.confidence for w in tr.words) < 0.7


# ---------------------------------------------------------------- Hebrew normalization and WER
@pytest.mark.parametrize("raw,norm", [
    ("שָׁלוֹם, עוֹלָם!", "שלומ עולמ"),
    ('צה"ל', "צהל"),
    ("צה״ל", "צהל"),
    ("ג'ירפה", "גירפה"),
    ("בית־ספר", "בית ספר"),  # maqaf
    ("בית-ספר", "בית ספר"),
    ("‏שלום‎  World", "שלומ world"),
    ("יש 3 ילדים.", "יש 3 ילדימ"),
])
def test_normalize_hebrew(raw, norm):
    assert normalize_hebrew(raw) == norm


def test_finals_switch():
    assert normalize_hebrew("מלך", finals=False) == "מלך"
    assert normalize_hebrew("מלך") == normalize_hebrew("מלכ")


def test_wer_counts():
    r = wer("אני רוצה לקנות כרטיס", "אני רוצה כרטיס חדש")
    assert r.rate == pytest.approx(0.5)  # 2 edits / 4 reference words (the split between kinds may vary)
    assert wer("a b c", "a b c d e").insertions == 2
    assert wer("a b c", "").deletions == 3 and wer("a b c", "").rate == 1.0
    assert wer("", "").rate == 0.0 and wer("", "x").rate == 1.0
    assert wer("שָׁלוֹם עוֹלָם", "שלום, עולם").rate == 0.0  # niqqud and comma are not errors
    assert wer("שלום עולם", "שלום, עולם", normalize=None).rate == 0.5


def test_wer_can_exceed_one():
    assert wer("שלום", "שלום שלום שלום").rate == 2.0


def test_cer_is_kind_to_glued_prefixes():
    assert wer("ובבית הספר", "ו בבית הספר").rate == 1.0  # one sub + one insertion, out of 2 words
    assert cer("ובבית הספר", "ו בבית הספר").rate == 0.0


def test_align_prefers_diagonal():
    assert align(["a", "b"], ["a", "c"]) == [("ok", "a", "a"), ("sub", "b", "c")]


# ---------------------------------------------------------------- reading feedback
def test_reading_feedback_statuses():
    tr = Transcript("אני רוצה לקנות קרטיס לאוטובוס", words=[
        Word("אני", confidence=0.95), Word("רוצה", confidence=0.4), Word("לקנות", confidence=0.9),
        Word("קרטיס", confidence=0.5), Word("לאוטובוס", confidence=0.9)])
    fb = reading_feedback(SENT, tr)
    status = [w.status for w in fb.words]
    assert status == ["ok", "unsure", "ok", "heard_as", "ok", "missing", "missing"]
    assert fb.score == pytest.approx(4 / 7)
    assert any("heard" in line for line in fb.lines())


# ---------------------------------------------------------------- OpenAI adapters (no network)
def transport(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def form_fields(request: httpx.Request) -> dict:
    body = request.read().decode("utf-8", "replace")
    out: dict = {}
    for part in body.split("Content-Disposition: form-data; ")[1:]:
        name = part.split('name="', 1)[1].split('"', 1)[0]
        if 'filename="' in part.split("\r\n", 1)[0]:
            out.setdefault(name, []).append("<file>")
            continue
        value = part.split("\r\n\r\n", 1)[1].rsplit("\r\n--", 1)[0]
        out.setdefault(name, []).append(value)
    return out


def test_transcriber_gpt_transcribe_sends_languages_list():
    seen = {}

    def handler(req):
        seen.update(form_fields(req))
        assert req.headers["authorization"] == "Bearer k"
        return httpx.Response(200, json={"text": SENT, "languages": [{"code": "he"}],
                                         "usage": {"type": "duration", "seconds": 3.0}})
    stt = OpenAITranscriber(api_key="k", http=transport(handler))
    audio = FakeTTS().synthesize(SENT).audio
    tr = stt.transcribe(audio, language="he", prompt="Acme")
    assert seen["model"] == ["gpt-transcribe"] and seen["languages[]"] == ["he"] and "language" not in seen
    assert seen["prompt"] == ["Acme"] and seen["file"] == ["<file>"]
    assert tr.text == SENT and tr.language == "he"
    assert tr.cost_usd == pytest.approx(0.0045 * 3 / 60)


def test_transcriber_word_timestamps_need_whisper_1():
    with pytest.raises(ValueError, match="whisper-1"):
        OpenAITranscriber(api_key="k").transcribe(b"x", word_timestamps=True)
    seen = {}

    def handler(req):
        seen.update(form_fields(req))
        return httpx.Response(200, json={"text": "שלום עולם", "language": "hebrew", "duration": 1.2,
                                         "words": [{"word": "שלום", "start": 0.0, "end": 0.5},
                                                   {"word": "עולם", "start": 0.6, "end": 1.1}]})
    tr = OpenAITranscriber("whisper-1", api_key="k", http=transport(handler)).transcribe(
        b"RIFF0000WAVE", language="he", word_timestamps=True)
    assert seen["response_format"] == ["verbose_json"] and seen["timestamp_granularities[]"] == ["word"]
    assert seen["language"] == ["he"]
    assert [(w.text, w.start, w.end) for w in tr.words] == [("שלום", 0.0, 0.5), ("עולם", 0.6, 1.1)]


def test_transcriber_logprobs_become_word_confidence():
    seen = {}
    lp = [{"token": "שלום", "logprob": -0.1}, {"token": " עו", "logprob": -0.5}, {"token": "לם", "logprob": -0.2}]

    def handler(req):
        seen.update(form_fields(req))
        return httpx.Response(200, json={"text": "שלום עולם", "logprobs": lp})
    tr = OpenAITranscriber("gpt-4o-mini-transcribe", api_key="k", logprobs=True,
                           http=transport(handler)).transcribe(b"x")
    assert seen["include[]"] == ["logprobs"]
    assert [w.text for w in tr.words] == ["שלום", "עולם"]
    assert tr.words[1].confidence == pytest.approx(math.exp(-0.7))
    with pytest.raises(ValueError):
        OpenAITranscriber("gpt-transcribe", api_key="k", logprobs=True).transcribe(b"x")
    assert words_from_logprobs([]) == []


def test_transcriber_errors_and_streaming():
    def bad(req):
        return httpx.Response(400, json={"error": {"message": "Invalid file format."}})
    with pytest.raises(VoiceError, match="Invalid file format") as e:
        OpenAITranscriber(api_key="k", http=transport(bad)).transcribe(b"x")
    assert e.value.status == 400

    def sse(req):
        assert "stream" in form_fields(req)
        text = ('data: {"type": "transcript.text.delta", "delta": "שלום "}\n\n'
                'data: {"type": "transcript.text.delta", "delta": "עולם"}\n\n'
                'data: {"type": "transcript.text.done", "text": "שלום עולם"}\n\n')
        return httpx.Response(200, content=text.encode(), headers={"content-type": "text/event-stream"})
    assert "".join(OpenAITranscriber(api_key="k", http=transport(sse)).stream(b"x", language="he")) == "שלום עולם"


def test_speech_request_shape_ttfb_and_cost():
    seen = {}
    pcm = b"\x00\x00" * 24_000 * 2  # 2 seconds

    def handler(req):
        seen.clear()
        seen.update(json.loads(req.read()))
        return httpx.Response(200, content=pcm)
    tts = OpenAISpeech(api_key="k", http=transport(handler))
    sp = tts.synthesize("שלום", instructions="Speak slowly, in clear Israeli Hebrew.", format="pcm")
    assert seen == {"model": "gpt-4o-mini-tts", "input": "שלום", "voice": "marin", "response_format": "pcm",
                    "instructions": "Speak slowly, in clear Israeli Hebrew."}
    assert sp.duration_s == 2.0 and sp.ttfb_s is not None and sp.cost_usd == pytest.approx(0.015 * 2 / 60)
    assert tts.shutdown == "2027-01-06"
    tts1 = OpenAISpeech("tts-1", "alloy", api_key="k", http=transport(handler))
    tts1.synthesize("abcd", instructions="ignored", format="pcm")
    assert seen["model"] == "tts-1" and "instructions" not in seen  # tts-1 has no instructions


# ---------------------------------------------------------------- pipeline
def test_split_sentences():
    done, rest = split_sentences("שלום! מה שלומך? אני")
    assert done == ["שלום!", "מה שלומך?"] and rest == "אני"
    done, rest = split_sentences("אני", final=True)
    assert done == ["אני"] and rest == ""
    long = "מילה " * 60
    done, rest = split_sentences(long)
    assert done and all(len(s) <= 140 for s in done)


@pytest.fixture
def slow_mock():
    srv, url = start_in_thread(MockConfig(ttft=0.25, tps=60, reply=(
        "שלום! אני המורה שלך לעברית. בוא נתרגל משפט קצר על נסיעה באוטובוס. "
        "תגיד אחריי: אני רוצה לקנות כרטיס לאוטובוס.")))
    yield LLM("anthropic:mock-model", api_key="t", base_url=url)
    srv.shutdown()


def test_streaming_speaks_earlier_than_sequential(slow_mock):
    audio = FakeTTS().synthesize(SENT).audio
    pipe = VoicePipeline(FakeSTT(latency_s=0.05), slow_mock, FakeTTS(ttfb_s=0.05, rtf=0.02), system="tutor")
    seq = pipe.turn(audio, streaming=False)
    stream = pipe.turn(audio, streaming=True)
    assert seq.transcript.text == SENT and stream.reply.startswith("שלום!")
    assert len(stream.sentences) >= 3 and len(seq.sentences) == 1
    assert stream.first_audio_s < seq.first_audio_s
    b = stream.budget()
    assert b["stt_s"] < b["first_audio_s"] <= b["total_s"]
    assert stream.audio and seq.audio


def test_local_adapters_explain_missing_dependency():
    import importlib.util
    from voicekit import local
    if importlib.util.find_spec("faster_whisper") is None:
        with pytest.raises(ImportError, match="faster-whisper"):
            local.FasterWhisperSTT()
    assert local.HEBREW_STT_MODEL.startswith("ivrit-ai/")
