"use client";

import { useEffect, useMemo, useState } from "react";
import { useAudioRecorder } from "@/lib/useAudioRecorder";

import {
  transcribeExpenseAudio,
  saveExpense,
  fetchExpenses,
  deleteExpense,
  ParsedExpense,
  Expense,
} from "@/lib/api";

type ProcessingStep =
  | "idle"
  | "recording"
  | "transcribing"
  | "understanding"
  | "ready";

export default function Home() {
  const {
    isRecording,
    isSupported,
    error: micError,
    startRecording,
    stopRecording,
    audioLevel,
    frequencyBars,
  } = useAudioRecorder();

  const [parsed, setParsed] = useState<ParsedExpense | null>(null);
  const [expenses, setExpenses] = useState<Expense[]>([]);

  const [loading, setLoading] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const [heardText, setHeardText] = useState("");

  const [processingStep, setProcessingStep] =
    useState<ProcessingStep>("idle");

  const [deletingId, setDeletingId] = useState<number | null>(null);

  const loadExpenses = async () => {
    try {
      const data = await fetchExpenses();
      setExpenses(data);
    } catch (err) {
      console.log("Error Loading Expenses", err)
    }
  };

  useEffect(() => {
    loadExpenses();
  }, []);


  const today = new Date().toISOString().split("T")[0];

  const todayExpenses = useMemo(() => {
    return expenses.filter((expense) => expense.date === today);
  }, [expenses, today]);

  const todayTotal = useMemo(() => {
    return todayExpenses.reduce(
      (total, expense) => total + Number(expense.amount || 0),
      0
    );
  }, [todayExpenses]);

  const totalSpent = useMemo(() => {
    return expenses.reduce(
      (total, expense) => total + Number(expense.amount || 0),
      0
    );
  }, [expenses]);

  // Dynamically discover categories from actual data.
  const categoryStats = useMemo(() => {
    const map = new Map<string, number>();

    for (const expense of expenses) {
      const category = expense.category?.trim() || "Other";

      map.set(
        category,
        (map.get(category) || 0) + Number(expense.amount || 0)
      );
    }

    return Array.from(map.entries())
      .map(([category, amount]) => ({
        category,
        amount,
      }))
      .sort((a, b) => b.amount - a.amount);
  }, [expenses]);

  // ============================================================
  // LIVE AUDIO-REACTIVE STYLING
  // ============================================================

  // Louder voice -> faster orbit spin (real, not canned). Quiet/idle
  // falls back to a slow ambient rotation so the ring never looks dead.
  const orbitSpinSeconds = isRecording
    ? Math.max(0.6, 4 - audioLevel * 3.4)
    : 16;

  // Ring "breathes" outward proportional to actual mic volume.
  const ringScale = isRecording ? 1 + audioLevel * 0.45 : 1;

  // Mic button glow intensifies with real input level.
  const glowSpread = isRecording ? 20 + audioLevel * 60 : 0;
  const glowOpacity = isRecording ? 0.25 + audioLevel * 0.5 : 0;

  // ============================================================
  // MICROPHONE
  // ============================================================

  async function handleMicClick() {
    if (isRecording) {
      const blob = await stopRecording();

      if (blob) {
        await handleTranscribe(blob);
      }

      return;
    }

    setParsed(null);
    setHeardText("");
    setApiError(null);

    setProcessingStep("recording");

    await startRecording();
  }

  // ============================================================
  // TRANSCRIBE + AI UNDERSTANDING
  // ============================================================

  async function handleTranscribe(blob: Blob) {
    setLoading(true);
    setApiError(null);

    try {
      setProcessingStep("transcribing");

      // Small delay gives the UI a natural pipeline feel.
      await new Promise((resolve) => setTimeout(resolve, 350));

      setProcessingStep("understanding");

      const result = await transcribeExpenseAudio(blob);

      setHeardText(result.raw_text);

      setParsed(result);

      setProcessingStep("ready");
    } catch (e: any) {
      setApiError(
        e?.message || "Unable to understand the expense."
      );

      setProcessingStep("idle");
    } finally {
      setLoading(false);
    }
  }

  // ============================================================
  // SAVE
  // ============================================================

  async function handleSave() {
    if (!parsed || parsed.amount === null) {
      setApiError("Please enter a valid amount.");
      return;
    }

    try {
      setLoading(true);

      await saveExpense(parsed);

      setParsed(null);
      setHeardText("");
      setProcessingStep("idle");

      await loadExpenses();
    } catch {
      setApiError("Failed to save expense.");
    } finally {
      setLoading(false);
    }
  }

  // ============================================================
  // DELETE
  // ============================================================

  async function handleDelete(id: number) {
    try {
      setDeletingId(id);

      await deleteExpense(id);

      await loadExpenses();
    } finally {
      setDeletingId(null);
    }
  }

  // ============================================================
  // PROCESSING LABEL
  // ============================================================

  const processingLabel = {
    idle: "Tap to speak",
    recording: "Listening...",
    transcribing: "Transcribing your voice...",
    understanding: "AI is understanding your expense...",
    ready: "Expense understood",
  }[processingStep];

  // ============================================================
  // RENDER
  // ============================================================

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-icon">◉</div>
          <div>
            <div className="brand-name">
              VoiceSpend
            </div>
            <div className="brand-subtitle">
              AI expense tracker
            </div>
          </div>
        </div>
      </header>
      <section className="hero">
        <div className="hero-copy">
          <h1>
            <span className="hero-line hero-line-one">
              Track spending
            </span>

            <span className="hero-line hero-line-two">
              <span>without typing.</span>
            </span>
          </h1>

          <p className="hero-description">
            Simply speak your expense. Voice Spend intelligently captures, understands, and categorizes every transaction automatically.
          </p>
        </div>

        <div className="voice-panel">
          <div
            className={`voice-orbit ${isRecording ? "active" : ""} ${loading ? "processing" : ""
              }`}
          >
            <div
              className="voice-glow"
              style={{
                boxShadow: `0 0 ${glowSpread}px ${glowSpread * 0.6
                  }px rgba(255, 92, 117, ${glowOpacity})`,
              }}
            />

            <div
              className="orbit-ring ring-one"
              style={{
                transform: `scale(${ringScale})`,
              }}
            />

            <div
              className="orbit-ring ring-two"
              style={{
                animationDuration: `${orbitSpinSeconds}s, 1.5s`,
              }}
            />

            <button
              className={`voice-button ${isRecording ? "recording" : ""}`}
              onClick={handleMicClick}
              disabled={!isSupported || loading}
              aria-label="Record expense"
            >
              {isRecording ? (
                <span className="stop-icon">■</span>
              ) : (
                <span className="mic-icon">⌕</span>
              )}
            </button>
          </div>

          <div className="voice-status">
            {processingLabel}
          </div>

          {isRecording && (
            <div className="sound-wave">
              {frequencyBars.map((level, i) => (
                <span
                  key={i}
                  style={{
                    height: `${8 + level * 26}px`,
                  }}
                />
              ))}
            </div>
          )}
        </div>
      </section>
      {!isSupported && (
        <div className="alert error">
          Your browser does not support microphone recording.
          Try Chrome or Edge over HTTPS or localhost.
        </div>
      )}
      {micError && (
        <div className="alert error">
          {micError}
        </div>
      )}
      {apiError && (
        <div className="alert error">
          <span>⚠</span>
          {apiError}
        </div>
      )}

      {(heardText || processingStep === "transcribing" ||
        processingStep === "understanding") && (
          <section className="transcript-card">
            <div className="transcript-header">
              <div className="section-label">
                LIVE TRANSCRIPT
              </div>
              <div className="ai-badge">
                ✦ AI
              </div>
            </div>
            <div className="transcript-text">
              {heardText
                ? `"${heardText}"`
                : processingStep === "transcribing"
                  ? "Listening to your recording..."
                  : "Understanding what you spent money on..."}
            </div>
          </section>
        )}

      {parsed && (
        <section className="result-card">
          <div className="result-header">
            <div>
              <div className="section-label">
                AI UNDERSTANDING
              </div>
              <h2>
                Expense detected
              </h2>
            </div>
            <div className="confidence">
              <span>●</span>
              Locally analyzed
            </div>
          </div>

          <div className="result-grid">
            <div className="result-field amount-field">
              <label>Amount</label>
              <div className="amount-input">
                <span>₹</span>
                <input
                  type="number"
                  value={parsed.amount ?? ""}
                  onChange={(e) =>
                    setParsed({
                      ...parsed,
                      amount:
                        e.target.value === ""
                          ? null
                          : Number(e.target.value),
                    })
                  }
                />
              </div>
            </div>
            <div className="result-field">
              <label>AI Category</label>
              <div className="dynamic-category">
                <span className="category-spark">
                  ✦
                </span>
                <input
                  value={parsed.category}
                  onChange={(e) =>
                    setParsed({
                      ...parsed,
                      category: e.target.value,
                    })
                  }
                />
              </div>
              <small>
                Dynamically inferred by AI
              </small>
            </div>
            <div className="result-field">
              <label>Description</label>
              <input
                value={parsed.description}
                onChange={(e) =>
                  setParsed({
                    ...parsed,
                    description: e.target.value,
                  })
                }
              />
            </div>
            <div className="result-field">
              <label>Date</label>
              <input
                type="date"
                value={parsed.date}
                onChange={(e) =>
                  setParsed({
                    ...parsed,
                    date: e.target.value,
                  })
                }
              />
            </div>
            <div className="result-field">
              <label>People</label>
              <input
                placeholder="No person detected"
                value={parsed.people ?? ""}
                onChange={(e) =>
                  setParsed({
                    ...parsed,
                    people: e.target.value || null,
                  })
                }
              />
            </div>
          </div>
          <div className="result-actions">
            <button
              className="save-button"
              onClick={handleSave}
              disabled={loading}
            >
              {loading ? "Saving..." : "Save expense"}
              <span>→</span>
            </button>
            <button
              className="discard-button"
              onClick={() => {
                setParsed(null);
                setHeardText("");
                setProcessingStep("idle");
              }}
            >
              Discard
            </button>
          </div>
        </section>
      )}
      <section className="stats-grid">
        <div className="stat-card">
          <div className="stat-icon">₹</div>
          <div>
            <div className="stat-label">
              TODAY
            </div>
            <div className="stat-value">
              ₹{todayTotal.toLocaleString("en-IN")}
            </div>
            <div className="stat-description">
              {todayExpenses.length}{" "}
              {todayExpenses.length === 1
                ? "expense"
                : "expenses"} today
            </div>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon purple">
            #
          </div>
          <div>
            <div className="stat-label">
              TRANSACTIONS
            </div>
            <div className="stat-value">
              {expenses.length}
            </div>
            <div className="stat-description">
              All recorded expenses
            </div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon green">
            ✦
          </div>
          <div>
            <div className="stat-label">
              CATEGORIES
            </div>
            <div className="stat-value">
              {categoryStats.length}
            </div>
            <div className="stat-description">
              AI-discovered categories
            </div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon orange">
            ∑
          </div>
          <div>
            <div className="stat-label">
              TOTAL SPENT
            </div>
            <div className="stat-value">
              ₹{totalSpent.toLocaleString("en-IN")}
            </div>
            <div className="stat-description">
              Across all transactions
            </div>
          </div>
        </div>
      </section>

      {categoryStats.length > 0 && (
        <section className="insights-section">
          <div className="section-heading">
            <div>
              <div className="section-label">
                SPENDING INSIGHTS
              </div>
              <h2>
                Where your money goes
              </h2>
            </div>
          </div>

          <div className="category-list">
            {categoryStats.map(
              ({ category, amount }) => {
                const percentage =
                  totalSpent > 0
                    ? Math.round(
                      (amount / totalSpent) * 100
                    )
                    : 0;
                return (
                  <div
                    className="category-row"
                    key={category}
                  >
                    <div className="category-name">
                      <span className="category-dot" />
                      {category}
                    </div>
                    <div className="category-progress">
                      <div className="progress-track">
                        <div
                          className="progress-fill"
                          style={{
                            width: `${percentage}%`,
                          }}
                        />
                      </div>
                    </div>
                    <div className="category-amount">
                      ₹{amount.toLocaleString("en-IN")}
                    </div>

                    <div className="category-percent">
                      {percentage}%
                    </div>
                  </div>
                );
              }
            )}
          </div>
        </section>
      )}

      <section className="expenses-section">
        <div className="section-heading">
          <div>
            <div className="section-label">
              ACTIVITY
            </div>
            <h2>
              Recent expenses
            </h2>
          </div>
          <div className="live-indicator">
            <span />
            Live
          </div>
        </div>

        {expenses.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">
              ✦
            </div>
            <h3>
              Your spending story starts here
            </h3>
            <p>
              Tap the microphone and tell me what
              you spent money on.
            </p>
          </div>
        ) : (
          <div className="expense-list">
            {expenses.map((expense) => (
              <div
                className="expense-card"
                key={expense.id}
              >
                <div className="expense-category-icon">
                  {getCategoryIcon(expense.category)}
                </div>
                <div className="expense-info">
                  <div className="expense-title">
                    {expense.description}
                  </div>
                  <div className="expense-meta">
                    <span className="category-pill">
                      {expense.category}
                    </span>
                    <span>
                      {expense.date}
                    </span>
                    {expense.people && (
                      <span>
                        with {expense.people}
                      </span>
                    )}
                  </div>
                </div>
                <div className="expense-right">
                  <div className="expense-amount">
                    ₹{Number(expense.amount).toLocaleString("en-IN")}
                  </div>
                  <button
                    className="delete-button"
                    onClick={() =>
                      handleDelete(expense.id)
                    }
                    disabled={
                      deletingId === expense.id
                    }
                    aria-label="Delete expense"
                  >
                    {deletingId === expense.id
                      ? "..."
                      : "×"}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}

function getCategoryIcon(category?: string) {
  const value = category?.toLowerCase() || "";
  if (
    value.includes("food") ||
    value.includes("dining") ||
    value.includes("restaurant")
  ) {
    return "🍜";
  }
  if (
    value.includes("transport") ||
    value.includes("travel") ||
    value.includes("fuel")
  ) {
    return "🚗";
  }
  if (
    value.includes("health") ||
    value.includes("medical")
  ) {
    return "❤️";
  }
  if (
    value.includes("sport") ||
    value.includes("fitness")
  ) {
    return "🏃";
  }
  if (
    value.includes("entertainment") ||
    value.includes("movie")
  ) {
    return "🎬";
  }
  if (
    value.includes("home") ||
    value.includes("rent")
  ) {
    return "🏠";
  }
  if (
    value.includes("pet")
  ) {
    return "🐾";
  }
  if (
    value.includes("electronic") ||
    value.includes("computer")
  ) {
    return "💻";
  }
  return "✦";
}
