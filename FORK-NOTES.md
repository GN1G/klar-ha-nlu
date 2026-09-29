# Fork: Weltfragen → LLM statt Reject

## Problem

Klar hat Welt-/Wissensfragen absichtlich als **OOD → reject** behandelt
(„das habe ich nicht verstanden“), auch wenn unter Settings → LLM ein
Endpoint (z. B. LM Studio) konfiguriert war.

Nur Smalltalk (Witz, Geschichte, Begrüßung) ging auf `decision: chat`.

## Änderung

In `src/parse/chat.rs` erweitert `wants_llm` um:

- Welt-/Ratgeber-Lexikon (`chat_world` / `chat_advice`)
- offene Fragen (`question_starts` / `question_words`)

Damit liefern Sätze wie „Wie hoch ist der Eiffelturm?“ jetzt
`ParseDecision::Chat`. Die HA-Integration ruft daraufhin den Engine-LLM-Pfad
auf (dein LM Studio).

Hausbefehle bleiben unverändert auf der NLU (`looks_like_home` / Household-Route
laufen vorher).

## Deploy auf Home Assistant

Die Engine ist **Rust** — nur die HACS-Python-Dateien zu tauschen reicht nicht.

1. Dieses Repo bauen (Release/Addon wie upstream, gleiche CalVer-Pipeline).
2. Klar-App / Engine mit dem neuen Binary neu starten.
3. LLM in der Klar-UI weiter auf LM Studio zeigen (wie bisher).
4. Im Lab prüfen: „Wie hoch ist der Eiffelturm?“ → `decision: chat`.

Ohne lokalen Rust-Toolchain: Image/Addon aus diesem Fork bauen lassen
(CI im Repo oder `cargo build --release` auf einer Build-Maschine).
