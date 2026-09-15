import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Voice Expense Tracker",
  description: "Speak your expenses, get them structured automatically.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
