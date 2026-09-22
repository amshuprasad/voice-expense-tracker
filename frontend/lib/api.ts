const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export interface ParsedExpense {
  raw_text: string;
  amount: number | null;
  category: string;
  description: string;
  date: string;
  people: string | null;
  flagged?: boolean;
}

export interface Expense extends ParsedExpense {
  id: number;
  created_at?: string;
}

export async function transcribeExpenseAudio(
  audioBlob: Blob
): Promise<ParsedExpense> {
  const formData = new FormData();
  formData.append("audio", audioBlob, "clip.webm");

  const res = await fetch(`${API_BASE}/transcribe-expense`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Failed to transcribe" }));
    throw new Error(err.detail || "Failed to transcribe expense");
  }
  return res.json();
}

export async function parseExpenseText(text: string): Promise<ParsedExpense> {
  const res = await fetch(`${API_BASE}/parse-expense`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Failed to parse" }));
    throw new Error(err.detail || "Failed to parse expense");
  }
  return res.json();
}

export async function saveExpense(expense: ParsedExpense): Promise<Expense> {
  const res = await fetch(`${API_BASE}/expenses`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(expense),
  });
  if (!res.ok) throw new Error("Failed to save expense");
  return res.json();
}

export async function fetchExpenses(): Promise<Expense[]> {
  const res = await fetch(`${API_BASE}/expenses`);
  if (!res.ok) throw new Error("Failed to fetch expenses");
  return res.json();
}

export async function deleteExpense(id: number): Promise<void> {
  await fetch(`${API_BASE}/expenses/${id}`, { method: "DELETE" });
}

export interface CategorySummary {
  category: string;
  total: number;
  count: number;
}

export async function fetchSummary(): Promise<CategorySummary[]> {
  const res = await fetch(`${API_BASE}/summary`);
  if (!res.ok) throw new Error("Failed to fetch summary");
  return res.json();
}
