import { useEffect, useMemo, useState } from "react";
import { api, type CustomRule } from "../api";
import { SearchSelect, useHouseCatalog, withCurrent } from "./SearchSelect";
import type { Messages } from "../i18n";
import { saveFailMessage, toastSaved, toastSaveFailed } from "../saveToast";
import type { ConversationTurn, Entity } from "../types";
import { useLangOverlay } from "../useLangOverlay";
import { journalHeard } from "./WhyDrawer";
import { teachIntentFromNames } from "./TeachFromMiss";

const CUSTOM_CAP = 64;
const FALLBACK_INTENTS = [
  "HassTurnOn",
  "HassTurnOff",
  "HassToggle",
  "HassGetState",
  "HassSetVolume",
  "HassMediaPause",
  "HassMediaPlay",
  "MassPlayMedia",
  "HassMediaSearchAndPlay",
];

export type LearnMode = "phrase" | "alias";

function isMediaIntent(name: string): boolean {
  return name === "MassPlayMedia" || name === "HassMediaSearchAndPlay";
}

export function LearnAssignPanel({
  turn,
  t,
  onClose,
  onSaved,
}: {
  turn: ConversationTurn;
  t: Messages;
  onClose: () => void;
  onSaved?: () => void;
}) {
  const heard = journalHeard(turn);
  const { overlay, offline, replace } = useLangOverlay();
  const rules = overlay?.custom ?? [];
  const language = overlay?.language ?? {};
  const { entityOptions } = useHouseCatalog();
  const [entities, setEntities] = useState<Entity[]>([]);
  const [intents, setIntents] = useState<string[]>(FALLBACK_INTENTS);
  const [mode, setMode] = useState<LearnMode>("phrase");
  const [phrase, setPhrase] = useState(heard);
  const [intent, setIntent] = useState(
    teachIntentFromNames(turn.last_names ?? []) || FALLBACK_INTENTS[0],
  );
  const [entityId, setEntityId] = useState("");
  const [mediaId, setMediaId] = useState("");
  const [mediaType, setMediaType] = useState("radio");
  const [alias, setAlias] = useState("");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");

  useEffect(() => {
    setPhrase(heard);
    const guess = teachIntentFromNames(turn.last_names ?? []);
    if (guess) setIntent(guess);
    const tokens = (turn.tokens ?? []).filter((tok) => tok.length >= 3);
    setAlias(tokens[tokens.length - 1] || heard.split(/\s+/).slice(-1)[0] || "");
  }, [turn, heard]);

  useEffect(() => {
    api.intents()
      .then((names) => {
        if (!names.length) return;
        const merged = [...new Set([...FALLBACK_INTENTS, ...names])].sort();
        setIntents(merged);
      })
      .catch(() => undefined);
    api.entities()
      .then(setEntities)
      .catch(() => undefined);
  }, []);

  const phraseCount = rules.length;
  const atCap = phraseCount >= CUSTOM_CAP;
  const selectedEntity = useMemo(
    () => entities.find((row) => row.entity_id === entityId),
    [entities, entityId],
  );

  const savePhrase = async () => {
    const clean = phrase.trim().toLowerCase();
    if (!clean) {
      setStatus(t.learnNeedPhrase);
      return;
    }
    if (atCap && !rules.some((row) => row.phrase === clean)) {
      setStatus(t.learnCustomFull);
      return;
    }
    const slots: Record<string, string> = {};
    if (entityId.trim()) slots.entity_id = entityId.trim();
    if (isMediaIntent(intent)) {
      if (mediaId.trim()) slots.media_id = mediaId.trim();
      if (mediaType.trim()) slots.media_type = mediaType.trim();
    }
    const next: CustomRule[] = [
      ...rules.filter((row) => row.phrase !== clean),
      { phrase: clean, intent, slots },
    ];
    setBusy(true);
    try {
      replace(await api.saveLangOverlay({ custom: next, language, label: clean }));
      toastSaved(t);
      setStatus(t.learnSavedPhrase);
      onSaved?.();
    } catch (err) {
      toastSaveFailed(t, err);
      setStatus(saveFailMessage(t, err));
    } finally {
      setBusy(false);
    }
  };

  const saveAlias = async () => {
    const cleanAlias = alias.trim();
    if (!entityId.trim() || !cleanAlias) {
      setStatus(t.learnNeedAlias);
      return;
    }
    const existing = selectedEntity?.aliases ?? [];
    const aliases = [...new Set([...existing, cleanAlias])];
    setBusy(true);
    try {
      await api.tagEntity({ entity_id: entityId.trim(), aliases });
      toastSaved(t);
      setStatus(t.learnSavedAlias);
      onSaved?.();
    } catch (err) {
      toastSaveFailed(t, err);
      setStatus(saveFailMessage(t, err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <aside className="card learn-panel hot">
      <div className="conv-head">
        <h2>{t.learnAssign}</h2>
        <button className="ghost" type="button" onClick={onClose}>{t.close}</button>
      </div>
      <p className="caption">{t.learnAssignHint}</p>
      <div className="learn-filters" style={{ marginTop: 12 }}>
        <button
          type="button"
          className={mode === "phrase" ? "pill hot" : "pill"}
          onClick={() => setMode("phrase")}
        >
          {t.learnAsPhrase}
        </button>
        <button
          type="button"
          className={mode === "alias" ? "pill hot" : "pill"}
          onClick={() => setMode("alias")}
        >
          {t.learnAsAlias}
        </button>
      </div>

      {mode === "phrase" ? (
        <>
          <label>{t.guideSentencesPhrase}</label>
          <input value={phrase} onChange={(ev) => setPhrase(ev.target.value)} />
          <label>{t.guideSentencesIntent}</label>
          <select value={intent} onChange={(ev) => setIntent(ev.target.value)}>
            {intents.map((name) => (
              <option key={name} value={name}>{name}</option>
            ))}
          </select>
          <label>{t.entityId}</label>
          <SearchSelect
            value={entityId}
            options={withCurrent(entityOptions, entityId)}
            onChange={setEntityId}
            placeholder="media_player.marcels_homepod"
          />
          {isMediaIntent(intent) ? (
            <>
              <label>{t.learnMediaId}</label>
              <input
                value={mediaId}
                onChange={(ev) => setMediaId(ev.target.value)}
                placeholder="housetime.fm"
              />
              <label>{t.learnMediaType}</label>
              <select value={mediaType} onChange={(ev) => setMediaType(ev.target.value)}>
                <option value="radio">radio</option>
                <option value="track">track</option>
                <option value="artist">artist</option>
                <option value="album">album</option>
                <option value="playlist">playlist</option>
              </select>
            </>
          ) : null}
          <p className="caption" style={{ marginTop: 12 }}>
            {t.learnCustomCount.replace("{count}", String(phraseCount)).replace("{max}", String(CUSTOM_CAP))}
          </p>
          <div className="row" style={{ marginTop: 12 }}>
            <button className="primary" type="button" disabled={busy || offline || atCap} onClick={() => void savePhrase()}>
              {t.learnSave}
            </button>
          </div>
        </>
      ) : (
        <>
          <label>{t.entityId}</label>
          <SearchSelect
            value={entityId}
            options={withCurrent(entityOptions, entityId)}
            onChange={setEntityId}
            placeholder="media_player.marcels_homepod"
          />
          <label>{t.alias}</label>
          <input value={alias} onChange={(ev) => setAlias(ev.target.value)} />
          <div className="row" style={{ marginTop: 12 }}>
            <button className="primary" type="button" disabled={busy || offline} onClick={() => void saveAlias()}>
              {t.learnSave}
            </button>
          </div>
        </>
      )}
      {status ? <p className="muted" style={{ marginTop: 12 }}>{status}</p> : null}
      {offline ? <p className="muted">{t.engineOffline}</p> : null}
    </aside>
  );
}
