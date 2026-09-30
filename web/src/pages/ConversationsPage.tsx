import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { Empty } from "../components/common";
import { LearnAssignPanel } from "../components/LearnAssignPanel";
import { SetupHint } from "../components/SetupHint";
import { canTeachFromMiss, isLowConfidence } from "../components/TeachFromMiss";
import { WhyDrawer, canJournalReplay, journalHeard, whyThisBand } from "../components/WhyDrawer";
import type { Messages } from "../i18n";
import { refineBandLabel } from "./ParsePage";
import type { ConversationTurn, RefineBand } from "../types";

type LearnFilter = "misses" | "all" | "ok";

function turnRefineBand(raw: string | null | undefined): RefineBand | null {
  switch (raw) {
    case "status":
    case "command":
    case "prompt":
    case "reject":
      return raw;
    default:
      return null;
  }
}

function asTurns(rows: unknown): ConversationTurn[] {
  if (!Array.isArray(rows)) {
    return [];
  }
  return rows.filter((row): row is ConversationTurn => !!row && typeof row === "object");
}

function turnTitle(turn: ConversationTurn, locale: string | undefined): string {
  const when = turn.ts_ms ? new Date(turn.ts_ms).toLocaleString(locale) : "";
  return [when, turn.decision].filter(Boolean).join(" · ");
}

function turnKey(turn: ConversationTurn, index: number): string {
  return `${turn.conversation_id}-${turn.ts_ms}-${index}`;
}

function matchesFilter(turn: ConversationTurn, filter: LearnFilter): boolean {
  if (filter === "all") return true;
  const miss = canTeachFromMiss(turn);
  if (filter === "misses") return miss;
  return !miss && turn.decision === "execute";
}

export function ConversationsPage({
  t,
  locale,
  onReplay,
}: {
  t: Messages;
  locale: string;
  onReplay: (text: string) => void;
  onTeach?: (heard: string) => void;
}) {
  const [turns, setTurns] = useState<ConversationTurn[] | null>(null);
  const [error, setError] = useState("");
  const [why, setWhy] = useState<ConversationTurn | null>(null);
  const [filter, setFilter] = useState<LearnFilter>("misses");
  const [selected, setSelected] = useState<ConversationTurn | null>(null);

  const load = () => {
    api.conversations()
      .then((rows) => setTurns(asTurns(rows)))
      .catch((err) => {
        setTurns([]);
        setError(String(err));
      });
  };

  useEffect(() => {
    load();
  }, []);

  const items = useMemo(() => {
    const sorted = [...(turns || [])].sort((a, b) => (b.ts_ms || 0) - (a.ts_ms || 0));
    return sorted.filter((turn) => matchesFilter(turn, filter));
  }, [turns, filter]);

  const missCount = useMemo(
    () => (turns || []).filter((turn) => canTeachFromMiss(turn)).length,
    [turns],
  );

  return (
    <div className="page">
      <section className="hero">
        <div>
          <h1>{t.learnTitle}</h1>
          <p className="muted">{t.learnHint}</p>
        </div>
        <button className="ghost" type="button" onClick={load}>{t.learnRefresh}</button>
      </section>

      <div className="learn-filters" style={{ marginBottom: 16 }}>
        <button
          type="button"
          className={filter === "misses" ? "pill hot" : "pill"}
          onClick={() => setFilter("misses")}
        >
          {t.learnFilterMisses}
          {missCount ? ` · ${missCount}` : ""}
        </button>
        <button
          type="button"
          className={filter === "all" ? "pill hot" : "pill"}
          onClick={() => setFilter("all")}
        >
          {t.learnFilterAll}
        </button>
        <button
          type="button"
          className={filter === "ok" ? "pill hot" : "pill"}
          onClick={() => setFilter("ok")}
        >
          {t.learnFilterOk}
        </button>
      </div>

      {error && <div className="card danger">{error}</div>}
      {turns === null && !error && <div className="card">{t.loading}</div>}
      {turns && items.length === 0 && !error && (
        <Empty
          text={filter === "misses" ? t.learnNoMisses : t.noConversations}
          action={(
            <>
              <p className="caption">{t.conversationsEmptyHint}</p>
              <SetupHint t={t} />
            </>
          )}
        />
      )}

      <div className={`learn-layout${selected ? " has-panel" : ""}`}>
        <div className="learn-list">
          {items.map((turn, index) => {
            const heard = journalHeard(turn);
            const refineBand = turnRefineBand(turn.refine_band);
            const active = selected?.ts_ms === turn.ts_ms
              && selected.conversation_id === turn.conversation_id;
            const miss = canTeachFromMiss(turn);
            return (
              <article
                className={`card learn-turn${active ? " selected" : ""}${miss ? " miss" : ""}`}
                key={turnKey(turn, index)}
              >
                <div className="conv-head">
                  <h2>{turnTitle(turn, locale)}</h2>
                  <div className="row">
                    {miss || isLowConfidence(turn.confidence) ? (
                      <span className="chip">{t.learnMissChip}</span>
                    ) : null}
                    <button className="ghost" type="button" onClick={() => setWhy(turn)}>
                      {whyThisBand(t)}
                    </button>
                    <button
                      className="ghost"
                      type="button"
                      onClick={() => onReplay(heard)}
                      disabled={!canJournalReplay(turn)}
                    >
                      {t.replay}
                    </button>
                  </div>
                </div>
                {heard ? <p>{heard}</p> : <p className="muted">—</p>}
                {turn.speech ? (
                  <p className="muted">
                    {turn.speech_source === "chat" ? <span className="chip">{t.speechChat}</span> : null}
                    {turn.speech_source === "refine" ? <span className="chip">{t.speechRefined}</span> : null}
                    {refineBand ? <span className="chip">{refineBandLabel(refineBand, t)}</span> : null}
                    {" "}
                    {turn.speech}
                  </p>
                ) : null}
                {turn.preferred_area ? <p className="caption">{t.heardIn}: {turn.preferred_area}</p> : null}
                <div className="row" style={{ marginTop: 12 }}>
                  <button
                    className="primary"
                    type="button"
                    disabled={!heard.trim()}
                    onClick={() => setSelected(turn)}
                  >
                    {t.learnAssign}
                  </button>
                  <button
                    className="ghost"
                    type="button"
                    disabled={!heard.trim()}
                    onClick={() => onReplay(heard)}
                  >
                    {t.inLab}
                  </button>
                </div>
              </article>
            );
          })}
        </div>
        {selected ? (
          <LearnAssignPanel
            turn={selected}
            t={t}
            onClose={() => setSelected(null)}
            onSaved={() => {
              setSelected(null);
              load();
            }}
          />
        ) : null}
      </div>
      {why && <WhyDrawer turn={why} t={t} onClose={() => setWhy(null)} />}
    </div>
  );
}
